import { test } from "node:test";
import assert from "node:assert/strict";
import { barPct, filterEvents, toJsonl } from "./eventView.ts";
import type { LabEvent } from "./events.ts";

const ev = (o: Partial<LabEvent> & { kind: string; seq: number }): LabEvent => ({ ts: null, t: null, ...o });
const log = [
  ev({ seq: 1, kind: "model.request", stage: "attack", role: "target" }),
  ev({ seq: 2, kind: "model.reply", stage: "attack", role: "target", latency_s: 2 }),
  ev({ seq: 3, kind: "verdict", stage: "judging", success: true, duration_s: 4 }),
  ev({ seq: 4, kind: "campaign.end" }),
];

test("filterEvents by chapter and by results only", () => {
  assert.deepEqual(filterEvents(log, "all", false).map((e) => e.seq), [1, 2, 3, 4]);
  assert.deepEqual(filterEvents(log, "attack", false).map((e) => e.seq), [1, 2]);
  assert.deepEqual(filterEvents(log, "all", true).map((e) => e.seq), [3]);
});

test("barPct is the share of the longest duration, null without one", () => {
  assert.equal(barPct(log[1], 4), 50);
  assert.equal(barPct(log[2], 4), 100);
  assert.equal(barPct(log[0], 4), null);
  assert.equal(barPct(log[1], 0), null);
});

test("toJsonl writes one JSON object per line", () => {
  const lines = toJsonl(log).split("\n").filter(Boolean);
  assert.equal(lines.length, log.length);
  assert.equal(JSON.parse(lines[2]).kind, "verdict");
  assert.equal(toJsonl([]), "");
});
