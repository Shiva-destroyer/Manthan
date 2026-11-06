import { test } from "node:test";
import assert from "node:assert/strict";
import { activeCalls, delayMs, replay, type ReplayState } from "./replay.ts";
import type { LabEvent } from "./events.ts";

const st = (o: Partial<ReplayState>): ReplayState => ({ cursor: -1, playing: false, speed: 1, length: 3, ...o });
const ev = (o: Partial<LabEvent> & { kind: string }): LabEvent => ({ seq: 1, ts: null, t: null, ...o });

test("step clamps", () => {
  assert.equal(replay(st({}), { type: "step", by: -1 }).cursor, -1);
  let s = st({});
  for (let i = 0; i < 3; i++) s = replay(s, { type: "step", by: 1 });
  assert.equal(s.cursor, 2);
  assert.equal(replay(s, { type: "step", by: 1 }).cursor, 2);
});

test("step pauses", () => {
  assert.equal(replay(st({ playing: true }), { type: "step", by: 1 }).playing, false);
});

test("tick advances and stops at end", () => {
  assert.equal(replay(st({ cursor: 0, playing: true }), { type: "tick" }).cursor, 1);
  const end = replay(st({ cursor: 2, playing: true }), { type: "tick" });
  assert.equal(end.playing, false);
  assert.equal(end.cursor, 2);
});

test("play at the end starts again", () => {
  const s = replay(st({ cursor: 2 }), { type: "play" });
  assert.deepEqual([s.cursor, s.playing], [-1, true]);
  assert.equal(replay(st({ cursor: 0, length: 0 }), { type: "play" }).playing, false);
});

test("seek and speed", () => {
  assert.equal(replay(st({}), { type: "seek", to: 99 }).cursor, 2);
  assert.equal(replay(st({}), { type: "seek", to: -9 }).cursor, -1);
  assert.equal(replay(st({}), { type: "speed", speed: 4 }).speed, 4);
});

test("load keeps cursor", () => {
  assert.equal(replay(st({ cursor: 5, length: 10 }), { type: "load", length: 20 }).cursor, 5);
  assert.equal(replay(st({ cursor: 5, length: 10 }), { type: "load", length: 3 }).cursor, 2);
  assert.equal(replay(st({ cursor: 5, length: 10 }), { type: "load", length: 0 }).cursor, -1);
});

test("delayMs", () => {
  const a = ev({ kind: "x", t: 1.0 });
  const b = ev({ kind: "x", t: 2.0 });
  assert.equal(delayMs(a, b, 1), 1000);
  assert.equal(delayMs(a, b, 8), 150);
  assert.equal(delayMs(ev({ kind: "x" }), ev({ kind: "x" }), 2), 300);
  assert.equal(delayMs(null, b, 1), 600);
  assert.equal(delayMs(a, ev({ kind: "x", t: 61 }), 1), 2000);
});

test("activeCalls", () => {
  const req = ev({ seq: 1, kind: "model.request", role: "target", model: "m", ts: "T" });
  const reply = ev({ seq: 2, kind: "model.reply", role: "target", model: "m" });
  assert.deepEqual(activeCalls([req], 0), [{ role: "target", model: "m", ts: "T", seq: 1 }]);
  assert.deepEqual(activeCalls([req, reply], 1), []);
  assert.equal(activeCalls([req, reply], 0).length, 1);
});
