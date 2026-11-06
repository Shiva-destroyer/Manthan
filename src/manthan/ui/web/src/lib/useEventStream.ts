import { useEffect, useState } from "react";
import { getJSON } from "./api.ts";
import type { LabEvent } from "./events.ts";
import { streamPlan, type StreamInput, type StreamState } from "./stream.ts";

type View = { events: LabEvent[]; ended: string | null; error: string | null };
const NONE: View = { events: [], ended: null, error: null };

// Fetch what the log holds, then follow the stream from that offset. Every close is ours: the
// browser never reconnects by itself, so a dropped stream is refetched and reopened with a back-off.
export function useEventStream(source: string, cid: string | null, live: boolean): View {
  const [view, setView] = useState<View>(NONE);
  useEffect(() => {
    if (!live || !cid) {
      setView(NONE);
      return;
    }
    let s: StreamState = { events: [], offset: 0, open: false, ended: null, retries: 0 };
    let es: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let dead = false;
    const base = `/api/campaigns/${cid}/events`;
    const q = `source=${encodeURIComponent(source)}`;
    const apply = (i: StreamInput) => {
      const plan = streamPlan(s, i);
      s = plan.state;
      if (plan.close && es) {
        es.close();
        es = null;
      }
      if (plan.refetchInMs !== null) timer = setTimeout(load, plan.refetchInMs);
      setView({ events: s.events, ended: s.ended, error: s.retries > 0 ? "The live connection dropped. Trying again." : null });
    };
    const open = () => {
      es = new EventSource(`${base}/stream?${q}&offset=${s.offset}`);
      es.onmessage = (m) => apply({ type: "message", ev: JSON.parse(m.data) as LabEvent });
      es.addEventListener("end", (m) => apply({ type: "end", status: String((JSON.parse((m as MessageEvent).data) as { status?: unknown }).status ?? "") }));
      es.onerror = () => apply({ type: "error" });
    };
    const load = () => {
      getJSON<{ events: LabEvent[]; offset: number }>(`${base}?${q}&offset=${s.offset}`).then(
        (r) => {
          if (dead) return;
          apply({ type: "fetched", events: r.events, offset: r.offset });
          open();
        },
        () => {
          if (!dead) apply({ type: "error" });
        },
      );
    };
    load();
    return () => {
      dead = true;
      es?.close();
      clearTimeout(timer);
    };
  }, [source, cid, live]);
  return view;
}
