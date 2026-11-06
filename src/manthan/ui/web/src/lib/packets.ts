import { badgeOf, roleOf, toolCallsOf, type LabEvent } from "./events.ts";
import { LABS, type DeviceId, type Lab } from "./labs.ts";
import type { Turn } from "./types.ts";

export type Packet = {
  id: string;
  seq: number;
  path: DeviceId[];
  text: string;
  poison: boolean | null;
  ev: LabEvent;
};

const str = (v: unknown): string | null => (typeof v === "string" ? v : null);

// "request" is a message going to a model, "reply" is its answer. Log events and table turns share these paths.
function modelPath(role: string, dir: "request" | "reply", ev: LabEvent, lab: Lab): DeviceId[] | null {
  if (role === "judge") return dir === "request" ? ["target", "rubric-judge"] : ["rubric-judge", "results"];
  if (lab === "prompt") {
    if (role === "target" && dir === "request") return [ev.stage === "guard" ? "guard" : "attacker", "target"];
    return role === "target" ? ["target", "attacker"] : null;
  }
  if (lab === "agent") return role === "target" ? (dir === "request" ? ["agent", "ollama"] : ["ollama", "agent"]) : null;
  if (role !== "target") return null;
  const defence = str(ev.defense);
  if (dir === "request") {
    return defence === "prompt_guard" || defence === "context_sep" ? ["question", defence, "target"] : ["question", "target"];
  }
  return defence === "output_validator" ? ["target", "output_validator", "results"] : ["target", "results"];
}

function rawPath(ev: LabEvent, lab: Lab): DeviceId[] | null {
  const role = roleOf(ev);
  switch (ev.kind) {
    case "model.request":
      return modelPath(role, "request", ev, lab);
    case "model.reply":
      return modelPath(role, "reply", ev, lab);
    case "guard.score":
      return ["attacker", "guard"];
    case "verdict":
      if (ev.judge_name === "refusal_baseline") return ["rule-check", "results"];
      return ev.judge_name === "rubric" ? ["rubric-judge", "results"] : null;
    case "turn":
      if (role === "tool") return ["agent", "mcp"];
      if (role === "user") return modelPath("target", "request", ev, lab);
      return role === "assistant" ? modelPath("target", "reply", ev, lab) : null;
    case "rag.retrieved":
      return ev.defense === "retrieval_filter" ? ["document-store", "retrieval_filter", "target"] : ["document-store", "target"];
    default:
      return null;
  }
}

export function pathFor(ev: LabEvent, lab: Lab): DeviceId[] | null {
  const path = rawPath(ev, lab);
  const ids = new Set(LABS[lab].devices.map((x) => x.id));
  return path !== null && path.every((id) => ids.has(id)) ? path : null;
}

export function parseToolTurn(content: string): {
  tool: string;
  destination: string | null;
  source: string | null;
  malicious: boolean | null;
} | null {
  try {
    const o: unknown = JSON.parse(content);
    if (typeof o !== "object" || o === null || typeof (o as { tool?: unknown }).tool !== "string") return null;
    const r = o as Record<string, unknown>;
    return {
      tool: r.tool as string,
      destination: str(r.destination),
      source: str(r.source),
      malicious: typeof r.malicious === "boolean" ? r.malicious : null,
    };
  } catch {
    return null;
  }
}

function textOf(ev: LabEvent): string {
  if (ev.kind === "model.request" && Array.isArray(ev.messages)) {
    return str((ev.messages[ev.messages.length - 1] as { content?: unknown } | undefined)?.content) ?? "—";
  }
  if (ev.kind === "model.reply") {
    if (typeof ev.reply === "string") return ev.reply;
    const lines = [str((ev.reply as { content?: unknown } | null)?.content) ?? ""];
    for (const c of toolCallsOf(ev)) lines.push(`${c.name} ${JSON.stringify(c.args)}`);
    return lines.filter(Boolean).join("\n") || "—";
  }
  if (ev.kind === "rag.retrieved") {
    return Array.isArray(ev.docs) ? ev.docs.map((x) => String((x as { id?: unknown }).id ?? "—")).join(", ") : "—";
  }
  if (ev.kind === "turn" && ev.role === "tool") {
    const t = parseToolTurn(str(ev.content) ?? "");
    return t === null ? "—" : t.destination ? `${t.tool} to ${t.destination}` : t.tool;
  }
  if (ev.kind === "turn") return str(ev.content) ?? "—";
  if (ev.kind === "verdict") return str(ev.label) ?? "—";
  return "—";
}

function poisonOf(ev: LabEvent): boolean | null {
  if (ev.kind === "rag.retrieved" && Array.isArray(ev.docs)) {
    return ev.docs.some((x) => (x as { is_poison?: unknown }).is_poison === true) ? true : null;
  }
  if (ev.kind === "turn" && ev.role === "tool") {
    return parseToolTurn(str(ev.content) ?? "")?.malicious === true ? true : null;
  }
  return null;
}

const packetOf = (ev: LabEvent, path: DeviceId[]): Packet =>
  ({ id: `${ev.source ?? "log"}-${ev.seq}-${ev.run_id ?? ""}`, seq: ev.seq, path, text: textOf(ev), poison: poisonOf(ev), ev });

export function packetsFrom(events: LabEvent[], lab: Lab, toolTurns: Record<string, Turn[]>): Packet[] {
  const out: Packet[] = [];
  for (const ev of events) {
    const path = pathFor(ev, lab);
    if (path) out.push(packetOf(ev, path));
  }
  // Table replays already carry their tool turns, so only runs without one get them from toolTurns.
  const have = new Set(events.filter((e) => e.kind === "turn" && e.role === "tool").map((e) => e.run_id));
  for (const [runId, turns] of Object.entries(toolTurns)) {
    if (have.has(runId)) continue;
    const added: Packet[] = [];
    for (const t of turns) {
      if (t.role !== "tool") continue;
      const ev: LabEvent = { seq: t.idx, ts: null, t: null, kind: "turn", role: "tool", run_id: runId, content: t.content, source: "tables" };
      const path = pathFor(ev, lab);
      if (path) added.push(packetOf(ev, path));
    }
    // After the run's last packet, else at the end.
    let at = out.length;
    for (let i = out.length - 1; i >= 0; i--) if (out[i].ev.run_id === runId) { at = i + 1; break; }
    out.splice(at, 0, ...added);
  }
  return out;
}

export function whyItMatters(p: Packet): string {
  const badge = badgeOf(p.ev);
  if (badge === "DEFENCE HELD") return "The defence stopped the attack at this step.";
  if (badge === "ATTACK WORKED" && p.poison === true) return "A poisoned message got the result the attacker wanted.";
  if (p.poison === true) return "This step carries poisoned content.";
  return "This step moves the conversation forward.";
}
