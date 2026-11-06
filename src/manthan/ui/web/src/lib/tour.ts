import type { LabEvent } from "./events.ts";

export type Anchor = "attacker" | "target" | "rubric-judge" | "results" | "events";

export const TOUR_STEPS: { anchor: Anchor; text: string }[] = [
  { anchor: "attacker", text: "This is the attacker. It is a model that writes the prompts sent to the target." },
  { anchor: "target", text: "This is the target. It is the model being tested, and it answers each prompt." },
  { anchor: "rubric-judge", text: "This is the rubric judge. It reads the conversation and scores whether the attack worked." },
  { anchor: "results", text: "Each score is stored here. In this run the attack worked." },
  { anchor: "events", text: "This list shows every step in order. Pick a line to jump to that moment, or press Play to watch the whole run." },
];

const KEY = "manthan.tour.seen";

// The first plain prompt run (not through the guard) that has a successful attack.
export function pickTourRun(
  runs: { id: string; domain: string; target_label: string }[],
  findings: { run_id: string; success: number }[],
): string | null {
  const won = new Set(findings.filter((f) => f.success).map((f) => f.run_id));
  return runs.find((r) => r.domain === "prompt" && !r.target_label.endsWith("+guard") && won.has(r.id))?.id ?? null;
}

export function tourSeen(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function markTourSeen(): void {
  try {
    localStorage.setItem(KEY, "1");
  } catch {
    // shortcut: without storage the tour shows on every Lab visit; fine for a one-person tool
  }
}

const MATCH: Record<Exclude<Anchor, "events">, (e: LabEvent) => boolean> = {
  attacker: (e) => e.role === "attacker" || (e.kind === "turn" && e.role === "user"),
  target: (e) => e.role === "target" || (e.kind === "turn" && e.role === "assistant"),
  "rubric-judge": (e) => e.role === "judge" || e.kind === "verdict",
  results: (e) => e.kind === "finding.stored",
};

// Index of the event the replay cursor should show for a step. The events step ends on the last event.
export function tourCursor(anchor: Anchor, events: LabEvent[]): number | null {
  if (events.length === 0) return null;
  if (anchor === "events") return events.length - 1;
  const i = events.findIndex(MATCH[anchor]);
  return i < 0 ? null : i;
}
