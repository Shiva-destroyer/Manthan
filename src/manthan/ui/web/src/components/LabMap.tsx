import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import tokens from "../design/tokens.json" with { type: "json" };
import type { Badge } from "../lib/events.ts";
import { LABS, type Device, type DeviceId, type Lab } from "../lib/labs.ts";
import type { Packet } from "../lib/packets.ts";
import { vendorOf } from "../lib/vendor.ts";
import { Icon } from "./icons/Icon.tsx";

const BOX_W = 148;
const BOX_H = 76;
const TRIP_MS = tokens.motion.slow_ms;
const TITLE: Record<Lab, string> = { prompt: "Prompt lab", agent: "Agent lab", rag: "RAG lab" };

const press = (act: () => void) => (e: KeyboardEvent) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    act();
  }
};

function PacketDot({ packet, devices, onPacket }: { packet: Packet; devices: Device[]; onPacket(p: Packet): void }) {
  const ref = useRef<SVGGElement>(null);
  const centres = packet.path.map((id) => devices.find((d) => d.id === id)!).map((d) => [d.x, d.y] as const);
  // The dot leaves and enters a box at its edge, so it never covers the model name inside.
  const points = centres.map((c, i) => {
    const other = i === 0 ? centres[1] : i === centres.length - 1 ? centres[i - 1] : null;
    if (!other) return c;
    const dx = other[0] - c[0];
    const dy = other[1] - c[1];
    const t = Math.min((BOX_W / 2 + 12) / (Math.abs(dx) || 1e-9), (BOX_H / 2 + 12) / (Math.abs(dy) || 1e-9), 1);
    return [c[0] + dx * t, c[1] + dy * t] as const;
  });
  const end = points[points.length - 1];
  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const legs = points.slice(1).map((p, i) => Math.hypot(p[0] - points[i][0], p[1] - points[i][1]));
    const total = legs.reduce((a, b) => a + b, 0) || 1;
    let run = 0;
    const frames = points.map((p, i) => {
      if (i > 0) run += legs[i - 1];
      return { transform: `translate(${p[0]}px, ${p[1]}px)`, offset: run / total };
    });
    const anim = el.animate(frames, { duration: TRIP_MS, easing: tokens.motion.ease, fill: "forwards" });
    return () => anim.cancel();
    // points is rebuilt each render from the same packet, so the packet id is the real dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [packet.id]);
  const fill = packet.poison === true ? "var(--color-poison)" : packet.poison === false ? "var(--color-saffron)" : "var(--color-teal)";
  const open = () => onPacket(packet);
  return (
    <g
      ref={ref}
      style={{ transform: `translate(${end[0]}px, ${end[1]}px)` }}
      role="button"
      tabIndex={0}
      aria-label={`Open packet ${packet.seq}`}
      className="lab-packet"
      data-poison={packet.poison === true ? "true" : undefined}
      onClick={open}
      onKeyDown={press(open)}
    >
      <circle r={9} fill={fill} stroke="var(--color-wire)" strokeWidth={1} />
    </g>
  );
}

export function LabMap({
  lab,
  packets,
  current,
  active,
  verdict,
  models,
  ringed,
  onPacket,
  onDevice,
}: {
  lab: Lab;
  packets: Packet[];
  current: number;
  active: { device: DeviceId; since: string | null }[];
  verdict: Badge;
  models: Record<string, string>;
  ringed?: DeviceId | null;
  onPacket(p: Packet): void;
  onDevice(id: DeviceId): void;
}) {
  const { devices, wires } = LABS[lab];
  const at = (id: DeviceId) => devices.find((d) => d.id === id)!;
  const packet = current >= 0 && current < packets.length ? packets[current] : null;
  const glowing = new Set(active.map((a) => a.device));
  return (
    <svg viewBox="0 0 1000 600" role="group" aria-label={TITLE[lab]} className="lab-map">
      <title>{TITLE[lab]}</title>
      {wires.map(([a, b]) => (
        <line key={`${a}-${b}`} x1={at(a).x} y1={at(a).y} x2={at(b).x} y2={at(b).y} stroke="var(--color-wire)" strokeWidth={1} />
      ))}
      {devices.map((d) => {
        const model = d.role ? (models[d.role] ?? null) : null;
        const vendor = model ? vendorOf(model) : null;
        const open = () => onDevice(d.id);
        const since = active.find((a) => a.device === d.id)?.since ?? null;
        return (
          <g key={d.id} role="button" tabIndex={0} aria-label={`${d.label}, open settings`} className="lab-device" onClick={open} onKeyDown={press(open)}>
            {glowing.has(d.id) && (
              <rect
                x={d.x - BOX_W / 2 - 4}
                y={d.y - BOX_H / 2 - 4}
                width={BOX_W + 8}
                height={BOX_H + 8}
                rx={12}
                fill="none"
                stroke="var(--color-ink)"
                strokeWidth={3}
              />
            )}
            {ringed === d.id && (
              <rect x={d.x - BOX_W / 2 - 4} y={d.y - BOX_H / 2 - 4} width={BOX_W + 8} height={BOX_H + 8} rx={12} fill="none" stroke="var(--color-ink)" strokeWidth={3} />
            )}
            <rect x={d.x - BOX_W / 2} y={d.y - BOX_H / 2} width={BOX_W} height={BOX_H} rx={8} fill="var(--color-paper)" stroke="var(--color-wire)" strokeWidth={1} />
            {d.icon ? (
              <Icon name={d.icon} cx={d.x} cy={d.y - 14} size={28} />
            ) : d.role && model === null ? (
              <text x={d.x} y={d.y - 10} textAnchor="middle" className="lab-mono">not recorded</text>
            ) : d.role ? (
              <>
                <text x={d.x} y={d.y - 18} textAnchor="middle" className="lab-mono">{vendor ?? "—"}</text>
                <text x={d.x} y={d.y - 2} textAnchor="middle" className="lab-mono">{model ?? "—"}</text>
              </>
            ) : null}
            <text x={d.x} y={d.y + 26} textAnchor="middle" className="lab-label">{d.label}</text>
            {glowing.has(d.id) && <Elapsed x={d.x} y={d.y + BOX_H / 2 + 20} since={since} />}
            {d.id === "results" && verdict !== null && <VerdictBadge x={d.x} y={d.y - BOX_H / 2 - 16} badge={verdict} />}
          </g>
        );
      })}
      {packet && <PacketDot key={packet.id} packet={packet} devices={devices} onPacket={onPacket} />}
    </svg>
  );
}

// Live runs pass an ISO start time; replays pass null and show a dash.
function Elapsed({ x, y, since }: { x: number; y: number; since: string | null }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (since === null) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [since]);
  const start = since === null ? NaN : Date.parse(since);
  return (
    <text x={x} y={y} textAnchor="middle" className="lab-mono">
      {Number.isNaN(start) ? (
        <>
          <title>Live timers show only while a run is live.</title>—
        </>
      ) : (
        `${Math.max(0, Math.round((now - start) / 1000))} s`
      )}
    </text>
  );
}

// Fades in over the verdict moment, then stays. Poison fill only for ATTACK WORKED.
function VerdictBadge({ x, y, badge }: { x: number; y: number; badge: Exclude<Badge, null> }) {
  const worked = badge === "ATTACK WORKED";
  return (
    <g className="lab-verdict">
      <rect x={x - 62} y={y - 12} width={124} height={24} rx={4} fill={worked ? "var(--color-poison)" : "var(--color-saffron)"} stroke="var(--color-wire)" strokeWidth={1} />
      <text x={x} y={y + 5} textAnchor="middle" className="lab-mono" style={{ fill: worked ? "var(--color-cream)" : "var(--color-ink)" }}>{badge}</text>
    </g>
  );
}
