import type { LabEvent } from "./events.ts";

export type RunLite = { id: string; objective_id: string; target_label: string };

export const RAG_CHIPS: { label: string; objective: string }[] = [
  { label: "No defence", objective: "rag-qa-baseline" },
  { label: "Retrieval filter", objective: "rag-qa-retrieval_filter" },
  { label: "Prompt guard", objective: "rag-qa-prompt_guard" },
  { label: "Context separation", objective: "rag-qa-context_sep" },
  { label: "Output validator", objective: "rag-qa-output_validator" },
  { label: "All four", objective: "rag-qa-stacked" },
];

export const isGuardRun = (r: RunLite): boolean => r.target_label.endsWith("+guard");

export const isLinked = (events: LabEvent[], r: RunLite): boolean =>
  events.some((e) => e.kind === "guard_pass.link" && e.run_id === r.id);

// The run with the guard on or off for the same attack. A guard_pass.link event names the pair.
// Table replays have none, so the fallback takes the same place among runs of the same objective.
export function guardPair(runs: RunLite[], events: LabEvent[], run: RunLite, wantGuard: boolean): RunLite | null {
  if (isGuardRun(run) === wantGuard) return run;
  const link = events.find(
    (e) => e.kind === "guard_pass.link" && (wantGuard ? e.parent_run_id === run.id : e.run_id === run.id),
  );
  if (link) {
    const id = wantGuard ? link.run_id : link.parent_run_id;
    return runs.find((r) => r.id === id) ?? null;
  }
  const same = runs.filter((r) => r.objective_id === run.objective_id);
  const place = same.filter((r) => isGuardRun(r) === isGuardRun(run)).findIndex((r) => r.id === run.id);
  return same.filter((r) => isGuardRun(r) === wantGuard)[place] ?? null;
}

// Built by hand because the Run page joins the router in Task 10.
export function rerunHref(target: string, seed: number | null, config: string | null): string {
  const p = new URLSearchParams({ target });
  if (config) p.set("config", config);
  if (seed !== null) p.set("seed", String(seed));
  p.set("smoke", "1");
  return `#/run?${p}`;
}
