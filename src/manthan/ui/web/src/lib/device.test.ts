import { test } from "node:test";
import assert from "node:assert/strict";
import { guardLine, residentAt, systemPromptOf } from "./device.ts";
import type { LabEvent } from "./events.ts";

const ev = (o: Partial<LabEvent> & { kind: string; seq: number }): LabEvent => ({ ts: null, t: null, ...o });
const log = [
  ev({ seq: 1, kind: "phase.start", resident: ["a"] }),
  ev({ seq: 2, kind: "model.request", role: "attacker", messages: [{ role: "system", content: "be sneaky" }, { role: "user", content: "hi" }] }),
  ev({ seq: 3, kind: "phase.start", resident: ["b", "c"] }),
  ev({ seq: 4, kind: "guard.score", score: 0.97, threshold: 0.5, blocked: true }),
  ev({ seq: 5, kind: "guard.score", score: 0.1, threshold: 0.5, blocked: false }),
];

test("systemPromptOf takes the first system message of the first request for the role", () => {
  assert.equal(systemPromptOf(log, "attacker"), "be sneaky");
  assert.equal(systemPromptOf(log, "target"), null);
});

test("residentAt is the last phase.start at or before the cursor seq", () => {
  assert.deepEqual(residentAt(log, 2), ["a"]);
  assert.deepEqual(residentAt(log, 4), ["b", "c"]);
  assert.equal(residentAt(log, 0), null);
});

test("guardLine reads the last guard.score at or before the cursor", () => {
  assert.equal(guardLine(log, 4), "Score 0.97 against a threshold of 0.5. Above the threshold means blocked.");
  assert.equal(guardLine(log, 5), "Score 0.1 against a threshold of 0.5. Above the threshold means blocked.");
  assert.equal(guardLine(log, 3), null);
});
