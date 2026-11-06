import { lookup } from "./glossary.ts";

export type RateLike = {
  k: number | null;
  n: number | null;
  value: number;
  ci_low: number | null;
  ci_high: number | null;
};

export const pct = (x: number): string => `${Math.round(x * 100)}%`;

// "TAP attack" -> "TAP", so the sentence reads "4 of 15 TAP attacks worked".
export function nounOf(label: string): string {
  const t = (lookup(label)?.term ?? label).replace(/\s+attack$/i, "");
  return t.charAt(0).toUpperCase() + t.slice(1);
}

// The range is copied from the stored row. This file never computes one.
export function rateSentence(r: RateLike, noun: string): string {
  const head =
    r.k !== null && r.n !== null
      ? `${r.k} of ${r.n} ${noun} attacks worked (${pct(r.value)}).`
      : `${noun} attacks worked ${pct(r.value)} of the time.`;
  const range =
    r.ci_low !== null && r.ci_high !== null
      ? `The true rate is likely between ${pct(r.ci_low)} and ${pct(r.ci_high)}.`
      : "No range is stored for this rate.";
  return `${head} ${range}`;
}

export function formatValue(name: string, v: number): string {
  if (name === "agent_lab_docker") return v === 1 ? "Docker lab" : "Simulated lab";
  if (name.endsWith("_mb")) return `${Math.round(v).toLocaleString("en-GB")} MB`;
  if (name.startsWith("uplift_")) return `${v.toFixed(1)} pts`;
  if (name.includes("kappa")) return `κ ${v.toFixed(2)}`;
  if (v >= 0 && v <= 1) return pct(v);
  return v.toFixed(2);
}

export const bytesToGB = (b: number): string => `${(b / 1e9).toFixed(1)} GB`;

// Some campaigns store one row per trial under the same name; show each name once.
export function groupMetrics<M extends { domain: string; name: string; value: number }>(
  rows: M[],
): { domain: string; name: string; values: number[] }[] {
  const out = new Map<string, { domain: string; name: string; values: number[] }>();
  for (const r of rows) {
    const key = `${r.domain}-${r.name}`;
    const g = out.get(key) ?? { domain: r.domain, name: r.name, values: [] };
    g.values.push(r.value);
    out.set(key, g);
  }
  return [...out.values()];
}
