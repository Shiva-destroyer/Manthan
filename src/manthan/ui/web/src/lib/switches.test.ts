import { test } from "node:test";
import assert from "node:assert/strict";
import { guardPair, isLinked, rerunHref, type RunLite } from "./switches.ts";
import type { LabEvent } from "./events.ts";

const run = (id: string, objective_id: string, guard = false): RunLite => ({ id, objective_id, target_label: guard ? "m+guard" : "m" });
const link = (run_id: string, parent_run_id: string): LabEvent => ({ seq: 1, ts: null, t: null, kind: "guard_pass.link", run_id, parent_run_id });

test("guardPair follows guard_pass.link both ways", () => {
  const runs = [run("a", "x"), run("b", "x"), run("c", "x", true), run("d", "x", true)];
  const evs = [link("d", "a"), link("c", "b")];
  assert.equal(guardPair(runs, evs, runs[0], true)?.id, "d");
  assert.equal(guardPair(runs, evs, runs[2], false)?.id, "b");
  assert.equal(isLinked(evs, runs[3]), true);
  assert.equal(isLinked([], runs[3]), false);
});

test("guardPair falls back to the same place among runs of the objective", () => {
  const runs = [run("a", "x"), run("b", "y"), run("c", "x"), run("d", "x", true), run("e", "y", true), run("f", "x", true)];
  assert.equal(guardPair(runs, [], runs[2], true)?.id, "f");
  assert.equal(guardPair(runs, [], runs[4], false)?.id, "b");
});

test("guardPair gives the run itself for its own state and null when no partner", () => {
  const runs = [run("a", "x"), run("b", "y")];
  assert.equal(guardPair(runs, [], runs[0], false)?.id, "a");
  assert.equal(guardPair(runs, [], runs[0], true), null);
});

test("rerunHref", () => {
  assert.equal(rerunHref("prompt", 7, "manthan-guard-off.yaml"), "#/run?target=prompt&config=manthan-guard-off.yaml&seed=7&smoke=1");
  assert.equal(rerunHref("rag", null, null), "#/run?target=rag&smoke=1");
});
