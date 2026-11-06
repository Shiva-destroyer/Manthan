import type { Action } from "./actions.ts";
type Domain = "prompt" | "agent" | "rag";
export type Check = { name: string; ok: boolean; detail: string };
export type RunForm = {
  target: Domain | "all";
  smoke: boolean;
  seed: string;
  skip: Domain[];
  config: string;
  verbose: boolean;
};
type Body = { target: string; smoke: boolean; seed: number | null; skip: string[]; config: string | null; verbose: boolean };

const TARGETS = ["prompt", "agent", "rag", "all"] as const;
const DOMAINS: Domain[] = ["prompt", "agent", "rag"];

export function formFromParams(p: Record<string, string>): RunForm {
  const target = TARGETS.find((t) => t === p.target) ?? "all";
  const skip = (p.skip ?? "").split(",").filter((s): s is Domain => DOMAINS.some((d) => d === s));
  return { target, smoke: p.smoke === "1", seed: p.seed ?? "", skip, config: p.config ?? "", verbose: p.verbose === "1" };
}

export function toBody(f: RunForm): Body | { error: string } {
  const seed = f.seed.trim();
  if (seed !== "" && !(/^\d+$/.test(seed) && Number(seed) <= 2147483647)) {
    return { error: "The seed must be a whole number from 0 to 2147483647." };
  }
  return {
    target: f.target,
    smoke: f.smoke,
    seed: seed === "" ? null : Number(seed),
    skip: f.target === "all" ? f.skip : [],
    config: f.config === "" ? null : f.config,
    verbose: f.verbose,
  };
}

// Plain lines for the preflight checks. They are not in the glossary yet (owner wording).
export const CHECK_LINES: Record<string, { pass: string; fail: string }> = {
  models_unloaded: { pass: "No model is in memory, so the run starts clean.", fail: "A model is still in memory. Unload it first." },
  ram: { pass: "There is enough free memory.", fail: "There is not enough free memory." },
  no_other_run: { pass: "Nothing else is running.", fail: "Something else is running." },
};

export function errorText(status: number, body: unknown): { text: string; checks: Check[] } {
  const b = typeof body === "object" && body !== null ? (body as { error?: unknown; checks?: unknown }) : {};
  if (status === 409 && typeof b.error === "string") return { text: b.error, checks: [] };
  if (status === 412) {
    const checks = Array.isArray(b.checks) ? (b.checks as Check[]) : [];
    return { text: "Not ready to start a run.", checks: [...checks].sort((x, y) => Number(x.ok) - Number(y.ok)) };
  }
  if (status === 422) {
    return { text: "The form has a value the server does not accept. Check the seed and the config file.", checks: [] };
  }
  return { text: `The server returned an error (${status}).`, checks: [] };
}

// A report is only for a run that finished cleanly. A run that aborted before it made a campaign has none,
// and the newest stored campaign would belong to an older run.
export function reportTarget(current: Action | null, campaign: string | null, campaigns: { id: string }[] | null): string | null {
  if (current === null || current.name !== "run" || current.exit_code !== 0) return null;
  return campaign ?? campaigns?.[0]?.id ?? null;
}
