import { mergeEvents, type LabEvent } from "./events.ts";
import type { RunRow } from "./types.ts";

export type StreamState = { events: LabEvent[]; offset: number; open: boolean; ended: string | null; retries: number };
export type StreamInput =
  | { type: "fetched"; events: LabEvent[]; offset: number }
  | { type: "message"; ev: LabEvent }
  | { type: "end"; status: string }
  | { type: "error" };

// Stream frames carry `seq`, not a byte offset, so only a fetch moves `offset`.
export function streamPlan(s: StreamState, i: StreamInput): { state: StreamState; close: boolean; refetchInMs: number | null } {
  switch (i.type) {
    case "fetched":
      return { state: { ...s, events: mergeEvents(s.events, i.events), offset: i.offset, open: true, retries: 0 }, close: false, refetchInMs: null };
    case "message":
      return { state: { ...s, events: mergeEvents(s.events, [i.ev]) }, close: false, refetchInMs: null };
    case "end":
      return { state: { ...s, open: false, ended: i.status }, close: true, refetchInMs: null };
    case "error":
      return { state: { ...s, open: false, retries: s.retries + 1 }, close: true, refetchInMs: Math.min(2000 * 2 ** s.retries, 30000) };
  }
}

// The run table is filled when a run ends, so a live campaign builds its run list from the events.
export function liveRuns(events: LabEvent[], campaign: string, domain: string): RunRow[] {
  const runs = new Map<string, RunRow>();
  for (const e of events) {
    if (typeof e.run_id !== "string") continue;
    if (e.kind === "run.stored") {
      const r = runs.get(e.run_id);
      if (r) {
        r.target_label = String(e.target_label ?? "");
        r.status = String(e.status ?? r.status);
      }
    } else if (e.domain === domain && !runs.has(e.run_id)) {
      runs.set(e.run_id, { id: e.run_id, campaign_id: campaign, objective_id: String(e.objective_id ?? ""), target_label: "", status: "running", domain });
    }
  }
  return [...runs.values()];
}
