import type { LabEvent } from "./events.ts";

export type Speed = 1 | 2 | 4 | 8;
export type ReplayState = { cursor: number; playing: boolean; speed: Speed; length: number };
export type ReplayAction =
  | { type: "step"; by: 1 | -1 }
  | { type: "play" }
  | { type: "pause" }
  | { type: "seek"; to: number }
  | { type: "speed"; speed: Speed }
  | { type: "tick" }
  | { type: "load"; length: number };

const clamp = (n: number, lo: number, hi: number) => Math.min(Math.max(n, lo), hi);

export function replay(s: ReplayState, a: ReplayAction): ReplayState {
  const last = s.length - 1;
  switch (a.type) {
    case "step":
      return { ...s, cursor: clamp(s.cursor + a.by, -1, last), playing: false };
    case "play":
      if (s.length === 0) return s;
      return { ...s, cursor: s.cursor >= last ? -1 : s.cursor, playing: true };
    case "pause":
      return { ...s, playing: false };
    case "seek":
      return { ...s, cursor: clamp(a.to, -1, last) };
    case "speed":
      return { ...s, speed: a.speed };
    case "tick":
      return s.cursor >= last ? { ...s, playing: false } : { ...s, cursor: s.cursor + 1 };
    case "load":
      return { ...s, length: a.length, cursor: Math.min(s.cursor, a.length - 1) };
  }
}

export function delayMs(prev: LabEvent | null, next: LabEvent, speed: Speed): number {
  if (prev === null || prev.t === null || next.t === null) return 600 / speed;
  return clamp(((next.t - prev.t) * 1000) / speed, 150, 2000);
}

export function activeCalls(
  events: LabEvent[],
  upTo: number,
): { role: string; model: string; ts: string | null; seq: number }[] {
  const open = new Map<string, { role: string; model: string; ts: string | null; seq: number }>();
  for (const e of events.slice(0, upTo + 1)) {
    if (e.kind !== "model.request" && e.kind !== "model.reply") continue;
    const role = String(e.role ?? "");
    const model = String(e.model ?? "");
    const key = `${role}|${model}`;
    if (e.kind === "model.request") open.set(key, { role, model, ts: e.ts, seq: e.seq });
    else open.delete(key);
  }
  return [...open.values()];
}
