import { useEffect, useRef, useState } from "react";
import { badgeOf, chapterOf, clampText, describe, durationOf, type Chapter, type LabEvent } from "../lib/events.ts";
import { barPct, filterEvents, toJsonl } from "../lib/eventView.ts";

type View = "Plain" | "Both" | "Technical";
const VIEWS: View[] = ["Plain", "Both", "Technical"];
const TITLE: Record<Chapter, string> = { attack: "Attack", judging: "Judging", "guard pass": "Guard pass", campaign: "Campaign" };
const CLAMP = 280;

export function EventList({
  events, cursor, onPick, campaign,
}: { events: LabEvent[]; cursor: number; onPick(ev: LabEvent): void; campaign?: string }) {
  const [view, setView] = useState<View>("Both");
  const [chapter, setChapter] = useState<Chapter | "all">("all");
  const [onlyResults, setOnlyResults] = useState(false);
  const current = useRef<HTMLLIElement>(null);
  const shown = filterEvents(events, chapter, onlyResults);
  const max = Math.max(0, ...shown.map((e) => durationOf(e) ?? 0));
  const cursorSeq = events[cursor]?.seq ?? -1;
  useEffect(() => {
    current.current?.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  // Chapters show in order of first use.
  const order: Chapter[] = [];
  for (const e of shown) if (!order.includes(chapterOf(e))) order.push(chapterOf(e));

  const download = () => {
    const url = URL.createObjectURL(new Blob([toJsonl(shown)], { type: "application/x-ndjson" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `manthan-${(campaign ?? "events").slice(0, 8)}-events.jsonl`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="event-list" aria-label="Events">
      <div className="event-tools">
        <div role="radiogroup" aria-label="Detail">
          {VIEWS.map((v) => (
            <button key={v} type="button" role="radio" aria-checked={view === v} onClick={() => setView(v)}>{v}</button>
          ))}
        </div>
        <label>
          Chapter{" "}
          <select value={chapter} onChange={(e) => setChapter(e.target.value as Chapter | "all")}>
            <option value="all">All</option>
            {(Object.keys(TITLE) as Chapter[]).map((c) => <option key={c} value={c}>{TITLE[c]}</option>)}
          </select>
        </label>
        <label>
          <input type="checkbox" checked={onlyResults} onChange={(e) => setOnlyResults(e.target.checked)} /> Only results
        </label>
        <button type="button" onClick={download}>Download events (JSONL)</button>
      </div>
      {order.map((c) => (
        <div key={c}>
          <h3>{TITLE[c]}</h3>
          <ol>
            {shown.filter((e) => chapterOf(e) === c).map((e) => {
              const { plain, tech } = describe(e);
              const text = clampText(plain, CLAMP);
              const badge = badgeOf(e);
              const pct = barPct(e, max);
              const now = e.seq === cursorSeq;
              return (
                <li key={e.seq} ref={now ? current : null} aria-current={now ? "step" : undefined} className={e.seq > cursorSeq ? "after-cursor" : undefined}>
                  <button type="button" className="event-row" onClick={() => onPick(e)}>
                    {view !== "Technical" && (
                      <span className="plain">
                        {text.text}
                        {text.clamped && " … Open the packet to read all of it."}
                      </span>
                    )}
                    {view !== "Plain" && <span className="mono muted">{tech}</span>}
                    {badge && <span className={badge === "ATTACK WORKED" ? "badge badge-worked" : "badge badge-held"}>{badge}</span>}
                    {pct !== null && pct > 0 && (
                      <span className="time-bar">
                        <span className="time-fill" style={{ width: `${pct}%` }} />
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ol>
        </div>
      ))}
    </section>
  );
}
