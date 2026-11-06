import { badgeOf, chapterOf, durationOf, type Chapter, type LabEvent } from "./events.ts";

export function filterEvents(events: LabEvent[], chapter: Chapter | "all", onlyResults: boolean): LabEvent[] {
  return events.filter((e) => (chapter === "all" || chapterOf(e) === chapter) && (!onlyResults || badgeOf(e) !== null));
}

export function barPct(ev: LabEvent, max: number): number | null {
  const d = durationOf(ev);
  return d === null || max <= 0 ? null : (d / max) * 100;
}

export const toJsonl = (events: LabEvent[]): string => events.map((e) => JSON.stringify(e) + "\n").join("");
