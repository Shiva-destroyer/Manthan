import { test } from "node:test";
import assert from "node:assert/strict";
import type { LabEvent } from "./events.ts";
import { liveRuns, streamPlan, type StreamState } from "./stream.ts";

const ev = (seq: number, o: Partial<LabEvent> = {}): LabEvent => ({ seq, ts: null, t: null, kind: "model.request", ...o });
const START: StreamState = { events: [], offset: 0, open: false, ended: null, retries: 0 };

test("streamPlan closes on end and on error", () => {
  const end = streamPlan(START, { type: "end", status: "ok" });
  assert.equal(end.close, true);
  assert.equal(end.state.ended, "ok");
  const e1 = streamPlan(START, { type: "error" });
  assert.equal(e1.close, true);
  assert.equal(e1.refetchInMs, 2000);
  assert.equal(streamPlan(e1.state, { type: "error" }).refetchInMs, 4000);
});

test("streamPlan caps the retry wait at 30 seconds", () => {
  assert.equal(streamPlan({ ...START, retries: 10 }, { type: "error" }).refetchInMs, 30000);
});

test("streamPlan dedupes a replayed message", () => {
  const s = streamPlan(START, { type: "fetched", events: [ev(1), ev(2), ev(3)], offset: 500 }).state;
  assert.equal(streamPlan(s, { type: "message", ev: ev(3) }).state.events.length, 3);
});

test("streamPlan keeps offset on message", () => {
  const s = streamPlan(START, { type: "fetched", events: [ev(1)], offset: 900 }).state;
  assert.equal(streamPlan(s, { type: "message", ev: ev(2) }).state.offset, 900);
});

test("streamPlan clears the retry count after a fetch", () => {
  const s = streamPlan(START, { type: "error" }).state;
  assert.equal(streamPlan(s, { type: "fetched", events: [], offset: 0 }).state.retries, 0);
});

test("liveRuns lists runs from events, newest last, with saved details when known", () => {
  const events = [
    ev(1, { run_id: "a", domain: "prompt", objective_id: "o1" }),
    ev(2, { run_id: "a", domain: "prompt", objective_id: "o1", kind: "model.reply" }),
    ev(3, { run_id: "a", kind: "run.stored", objective_id: "o1", target_label: "m+guard", status: "completed" }),
    ev(4, { run_id: "b", domain: "prompt", objective_id: "o2" }),
    ev(5, { run_id: "c", domain: "rag", objective_id: "o3" }),
    ev(6, { run_id: "m", kind: "metric.stored" }),
  ];
  assert.deepEqual(liveRuns(events, "cid", "prompt"), [
    { id: "a", campaign_id: "cid", objective_id: "o1", target_label: "m+guard", status: "completed", domain: "prompt" },
    { id: "b", campaign_id: "cid", objective_id: "o2", target_label: "", status: "running", domain: "prompt" },
  ]);
});
