import { useEffect, useRef, useState } from "react";
import { describe, durationOf } from "../lib/events.ts";
import { whyItMatters, type Packet } from "../lib/packets.ts";
import { Missing } from "./Missing.tsx";

const show = (v: unknown) => (typeof v === "string" || typeof v === "number" ? String(v) : null);

// The dialog is modal, so focus stays inside and Escape closes it. The caller keeps the opener to refocus.
export function PacketWindow({ packet, onClose }: { packet: Packet; onClose(): void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [tab, setTab] = useState<"Plain" | "Technical">("Plain");
  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
  }, []);
  const { plain } = describe(packet.ev);
  const rows: [string, string | null][] = [
    ["role", show(packet.ev.role)],
    ["model", show(packet.ev.model)],
    ["latency_s", show(durationOf(packet.ev))],
    ["run_id", show(packet.ev.run_id)],
    ["seq", String(packet.seq)],
    ["ts", show(packet.ev.ts)],
  ];
  return (
    <dialog ref={ref} className="packet-window" aria-label={`Packet ${packet.seq}`} onClose={onClose}>
      <div role="tablist" aria-label="Packet detail">
        {(["Plain", "Technical"] as const).map((t) => (
          <button key={t} type="button" role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>
      <button type="button" onClick={onClose}>Close</button>
      {tab === "Plain" ? (
        <dl>
          <dt>What was sent</dt>
          <dd>{packet.text || "—"}</dd>
          <dt>What happened</dt>
          <dd>{plain}</dd>
          <dt>Why it matters</dt>
          <dd>{whyItMatters(packet)}</dd>
        </dl>
      ) : (
        <>
          <dl className="mono">
            {rows.map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v ?? <Missing why="This event does not carry that field." />}</dd>
              </div>
            ))}
          </dl>
          <pre className="raw">{packet.text}</pre>
        </>
      )}
    </dialog>
  );
}
