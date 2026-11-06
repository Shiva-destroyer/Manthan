import raw from "../design/glossary.json" with { type: "json" };

export type GlossaryEntry = { id: string; term: string; plain: string; technical: string; see: string[] };

const entries: GlossaryEntry[] = raw;

const escape = (s: string) => s.replace(/[.+?^${}()|[\]\\]/g, "\\$&");
const literalLength = (id: string) => id.replace(/\*/g, "").length;
const matches = (id: string, name: string) =>
  id === name || (id.includes("*") && new RegExp(`^${id.split("*").map(escape).join(".*")}$`).test(name));

// An exact id wins. Otherwise the wildcard with the longest literal part; on a tie, the first in the file.
export function lookup(name: string): GlossaryEntry | null {
  let best: GlossaryEntry | null = null;
  for (const e of entries) {
    if (!matches(e.id, name)) continue;
    if (e.id === name) return e;
    if (best === null || literalLength(e.id) > literalLength(best.id)) best = e;
  }
  return best;
}
