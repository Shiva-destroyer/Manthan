export type LabEvent = {
  seq: number;
  ts: string | null;
  t: number | null;
  kind: string;
  source?: "log" | "tables";
  run_id?: string;
  parent_run_id?: string;
  stage?: string;
  domain?: string;
  strategy?: string;
  objective_id?: string;
  trial?: number;
  attack_class?: string;
  defense?: string;
  n_poison?: number;
  [field: string]: unknown;
};
export type Chapter = "attack" | "judging" | "guard pass" | "campaign";
export type Badge = "ATTACK WORKED" | "DEFENCE HELD" | null;

const DASH = "—";

export function mergeEvents(a: LabEvent[], b: LabEvent[]): LabEvent[] {
  const bySeq = new Map<number, LabEvent>();
  for (const e of [...a, ...b]) bySeq.set(e.seq, e);
  return [...bySeq.values()].sort((x, y) => x.seq - y.seq);
}

export function chapterOf(ev: LabEvent): Chapter {
  if (ev.stage === "guard") return "guard pass";
  if (ev.stage === "judging") return ev.parent_run_id ? "guard pass" : "judging";
  if (ev.stage === "attack" || ev.stage === "benign" || ev.stage === "leak") return "attack";
  // Table replays carry no stage, so place their turns and verdicts by kind.
  if (ev.stage === undefined && ev.source === "tables") {
    if (ev.kind === "turn") return "attack";
    if (ev.kind === "verdict") return "judging";
  }
  return "campaign";
}

export function badgeOf(ev: LabEvent): Badge {
  if ((ev.kind === "finding.stored" || ev.kind === "verdict") && typeof ev.success === "boolean") {
    return ev.success ? "ATTACK WORKED" : "DEFENCE HELD";
  }
  return null;
}

export function durationOf(ev: LabEvent): number | null {
  const v = ev.kind === "verdict" ? ev.duration_s : ev.kind === "model.reply" || ev.kind === "turn" ? ev.latency_s : null;
  return typeof v === "number" ? v : null;
}

const BANNERS: Record<string, string> = {
  stopped: "This campaign was stopped before it finished. The events below are all that were saved.",
  error: "This campaign stopped with an error. The events below are all that were saved.",
  incomplete: "This campaign did not finish, and its process is gone. The events below are all that were saved.",
};

// `ended` is the status a live stream closed with. It beats the stored status, which the page loaded once.
export function campaignBanner(status: string | null, ended: string | null = null): string | null {
  status = ended ?? status;
  if (status === null || status === "ok" || status === "running") return null;
  return BANNERS[status] ?? `This campaign has an unknown status: ${status}.`;
}

export function clampText(text: string, max: number): { text: string; clamped: boolean } {
  return text.length > max ? { text: text.slice(0, max), clamped: true } : { text, clamped: false };
}

const show = (v: unknown): string => (typeof v === "string" || typeof v === "number" ? String(v) : DASH);

const REQUEST: Record<string, string> = {
  attacker: "Manthan asked the attacker to write the next message.",
  target: "A message was sent to the target.",
  judge: "The rubric judge received the conversation to score.",
};
const REPLY: Record<string, string> = {
  attacker: "The attacker wrote its next message.",
  target: "The target replied.",
  judge: "The rubric judge gave its score.",
};
const TURN: Record<string, string> = {
  user: "A message was sent to the target.",
  assistant: "The target replied.",
  tool: "The agent called a tool.",
};
const JUDGE_NAME: Record<string, string> = { refusal_baseline: "rule check", rubric: "rubric judge" };

// The agent lab logs its model calls with role "", and its model is the target.
export const roleOf = (ev: LabEvent): string =>
  typeof ev.role === "string" && ev.role ? ev.role : ev.domain === "agent" ? "target" : "";

// Agent replies are message objects; the names of the tools they ask for, if any.
export const toolCallsOf = (ev: LabEvent): { name: string; args: unknown }[] => {
  const calls = (ev.reply as { tool_calls?: unknown } | null)?.tool_calls;
  if (!Array.isArray(calls)) return [];
  return calls.map((c) => ({ name: String(c?.function?.name ?? DASH), args: c?.function?.arguments ?? {} }));
};

function plainOf(ev: LabEvent): string {
  const role = roleOf(ev);
  switch (ev.kind) {
    case "campaign.start":
      return "The campaign started.";
    case "campaign.end":
      return "The campaign ended.";
    case "domain.start":
      return `The ${show(ev.domain)} lab started.`;
    case "domain.end":
      return `The ${show(ev.domain)} lab finished.`;
    case "phase.start":
      return `Models in memory for this step: ${
        Array.isArray(ev.resident) ? ev.resident.map(String).join(", ") : DASH
      }.`;
    case "model.load":
      return `Ollama loaded ${show(ev.model)}.`;
    case "model.unload":
      return `Ollama unloaded ${show(ev.model)}.`;
    case "model.request":
      return REQUEST[role] ?? DASH;
    case "model.reply": {
      const calls = toolCallsOf(ev);
      if (calls.length) return `The agent called ${calls.map((c) => c.name).join(", ")}.`;
      return REPLY[role] ?? DASH;
    }
    case "model.error":
      return `The ${show(ev.role)} model returned an error.`;
    case "guard.score":
      return ev.blocked === true
        ? "The guard blocked this message. Its score was above the threshold."
        : "The guard let this message through.";
    case "guard_pass.link":
      return "The same attack was sent again, this time through the guard.";
    case "rag.retrieved": {
      if (!Array.isArray(ev.docs)) return `The search returned ${DASH} files. ${DASH} of them were poisoned.`;
      const poisoned = ev.docs.filter((d) => (d as { is_poison?: unknown })?.is_poison === true).length;
      return `The search returned ${ev.docs.length} files. ${poisoned} of them were poisoned.`;
    }
    case "verdict": {
      if (typeof ev.success === "boolean") {
        return ev.success ? "The judges decided the attack worked." : "The judges decided the defence held.";
      }
      if (typeof ev.judge_name === "string") {
        return `The ${JUDGE_NAME[ev.judge_name] ?? ev.judge_name} labelled this reply ${show(ev.label)}.`;
      }
      return DASH;
    }
    case "turn":
      return TURN[role] ?? DASH;
    case "run.stored":
      return "The run was saved.";
    case "metric.stored":
      return "A result was saved.";
    case "finding.stored":
      return ev.success === true ? "This attack worked." : ev.success === false ? "This attack did not work." : DASH;
    default:
      return DASH;
  }
}

const TECH_KEYS = [
  "run_id", "stage", "role", "model", "latency_s", "score", "threshold",
  "label", "judge_name", "defense", "n_poison", "name", "value", "status",
] as const;

export function describe(ev: LabEvent): { plain: string; tech: string } {
  const parts = [`kind=${ev.kind}`];
  for (const k of TECH_KEYS) {
    const v = ev[k];
    if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
      parts.push(`${k}=${k === "run_id" ? String(v).slice(0, 8) : v}`);
    }
  }
  return { plain: plainOf(ev), tech: parts.join("  ") };
}
