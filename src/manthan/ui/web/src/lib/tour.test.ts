import { test } from "node:test";
import assert from "node:assert/strict";
import { TOUR_STEPS, pickTourRun, tourCursor, tourSeen } from "./tour.ts";
import type { LabEvent } from "./events.ts";

const run = (id: string, label = "target-a", domain = "prompt") => ({ id, domain, target_label: label });
const ev = (o: Partial<LabEvent> & { kind: string }): LabEvent => ({ seq: 1, ts: null, t: null, ...o });

test("pickTourRun skips guard runs", () => {
  const runs = [run("g", "target-a+guard"), run("p")];
  const findings = [{ run_id: "g", success: 1 }, { run_id: "p", success: 1 }];
  assert.equal(pickTourRun(runs, findings), "p");
});

test("pickTourRun needs a success", () => {
  assert.equal(pickTourRun([run("p")], [{ run_id: "p", success: 0 }]), null);
});

test("pickTourRun ignores other labs", () => {
  assert.equal(pickTourRun([run("r", "target-a", "rag")], [{ run_id: "r", success: 1 }]), null);
});

test("tourSeen survives a throwing storage", () => {
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: { getItem: () => { throw new Error("blocked"); } },
  });
  assert.equal(tourSeen(), false);
});

test("tourCursor finds each anchor in log and table events", () => {
  const log = [ev({ kind: "campaign.start" }), ev({ kind: "model.request", role: "attacker" }), ev({ kind: "model.reply", role: "target" }), ev({ kind: "verdict", role: "judge" }), ev({ kind: "finding.stored", success: true })];
  assert.deepEqual(TOUR_STEPS.map((s) => tourCursor(s.anchor, log)), [1, 2, 3, 4, 4]);
  const tables = [ev({ kind: "run.stored" }), ev({ kind: "turn", role: "user" }), ev({ kind: "turn", role: "assistant" }), ev({ kind: "verdict", judge_name: "rubric" }), ev({ kind: "finding.stored", success: true })];
  assert.deepEqual(TOUR_STEPS.map((s) => tourCursor(s.anchor, tables)), [1, 2, 3, 4, 4]);
  assert.equal(tourCursor("attacker", []), null);
});

test("tour has five steps in map order", () => {
  assert.deepEqual(TOUR_STEPS.map((s) => s.anchor), ["attacker", "target", "rubric-judge", "results", "events"]);
});
