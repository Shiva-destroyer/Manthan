import { test } from "node:test";
import assert from "node:assert/strict";
import {
  badgeOf,
  campaignBanner,
  chapterOf,
  clampText,
  describe,
  durationOf,
  mergeEvents,
  type LabEvent,
} from "./events.ts";
import mockLog from "./fixtures/mock-log.json" with { type: "json" };
import mockRag from "./fixtures/mock-rag-log.json" with { type: "json" };
import c1b from "./fixtures/c1b-tables.json" with { type: "json" };

const ev = (o: Partial<LabEvent> & { kind: string }): LabEvent => ({ seq: 1, ts: null, t: null, ...o });

test("mergeEvents dedupes by seq and sorts", () => {
  const a = [{ seq: 1 }, { seq: 3 }] as LabEvent[];
  const b = [{ seq: 3 }, { seq: 2 }] as LabEvent[];
  assert.deepEqual(mergeEvents(a, b).map((e) => e.seq), [1, 2, 3]);
});

test("chapterOf", () => {
  assert.equal(chapterOf(ev({ kind: "model.request", stage: "attack" })), "attack");
  assert.equal(chapterOf(ev({ kind: "verdict", stage: "judging" })), "judging");
  assert.equal(chapterOf(ev({ kind: "verdict", stage: "judging", parent_run_id: "x" })), "guard pass");
  assert.equal(chapterOf(ev({ kind: "model.request", stage: "guard" })), "guard pass");
  assert.equal(chapterOf(ev({ kind: "campaign.start" })), "campaign");
});

test("chapterOf table events", () => {
  assert.equal(chapterOf(ev({ kind: "turn", source: "tables" })), "attack");
  assert.equal(chapterOf(ev({ kind: "verdict", source: "tables" })), "judging");
  assert.equal(chapterOf(ev({ kind: "finding.stored", source: "tables" })), "campaign");
});

test("badgeOf", () => {
  assert.equal(badgeOf(ev({ kind: "finding.stored", success: true })), "ATTACK WORKED");
  assert.equal(badgeOf(ev({ kind: "finding.stored", success: false })), "DEFENCE HELD");
  assert.equal(badgeOf(ev({ kind: "verdict", success: true })), "ATTACK WORKED");
  assert.equal(badgeOf(ev({ kind: "verdict", judge_name: "rubric" })), null);
  assert.equal(badgeOf(ev({ kind: "model.reply" })), null);
});

test("describe unknown kind", () => {
  assert.deepEqual(describe(ev({ kind: "x.y" })), { plain: "—", tech: "kind=x.y" });
});

test("describe missing fields", () => {
  assert.equal(describe(ev({ kind: "model.load" })).plain, "Ollama loaded —.");
  assert.equal(describe(ev({ kind: "domain.start" })).plain, "The — lab started.");
  assert.equal(describe(ev({ kind: "rag.retrieved" })).plain, "The search returned — files. — of them were poisoned.");
});

test("describe guard.score", () => {
  const d = describe(ev({ kind: "guard.score", score: 0.97, threshold: 0.5, blocked: true }));
  assert.ok(d.plain.startsWith("The guard blocked"));
  assert.ok(d.tech.includes("score=0.97  threshold=0.5"));
  assert.equal(describe(ev({ kind: "guard.score", blocked: false })).plain, "The guard let this message through.");
});

test("describe table verdict", () => {
  const d = describe(ev({ kind: "verdict", judge_name: "refusal_baseline", label: "refusal" }));
  assert.equal(d.plain, "The rule check labelled this reply refusal.");
  assert.equal(describe(ev({ kind: "verdict", judge_name: "rubric", label: "partial" })).plain, "The rubric judge labelled this reply partial.");
});

test("describe by role and success", () => {
  assert.equal(describe(ev({ kind: "model.request", role: "attacker" })).plain, "Manthan asked the attacker to write the next message.");
  assert.equal(describe(ev({ kind: "model.reply", role: "judge" })).plain, "The rubric judge gave its score.");
  assert.equal(describe(ev({ kind: "turn", role: "tool" })).plain, "The agent called a tool.");
  assert.equal(describe(ev({ kind: "verdict", success: true })).plain, "The judges decided the attack worked.");
  assert.equal(describe(ev({ kind: "finding.stored", success: false })).plain, "This attack did not work.");
  assert.equal(describe(ev({ kind: "phase.start", resident: ["a", "b"] })).plain, "Models in memory for this step: a, b.");
});

test("describe rag.retrieved counts poison", () => {
  const docs = [{ is_poison: true }, { is_poison: false }, { is_poison: true }];
  assert.equal(describe(ev({ kind: "rag.retrieved", docs })).plain, "The search returned 3 files. 2 of them were poisoned.");
});

test("describe tech order and run id", () => {
  const d = describe(ev({ kind: "model.reply", run_id: "0123456789abcdef", stage: "attack", role: "target", model: "m", latency_s: 1.5 }));
  assert.equal(d.tech, "kind=model.reply  run_id=01234567  stage=attack  role=target  model=m  latency_s=1.5");
});

test("durationOf", () => {
  assert.equal(durationOf(ev({ kind: "model.reply", latency_s: 2.5 })), 2.5);
  assert.equal(durationOf(ev({ kind: "verdict", duration_s: 0.4 })), 0.4);
  assert.equal(durationOf(ev({ kind: "turn", latency_s: null })), null);
  assert.equal(durationOf(ev({ kind: "phase.start" })), null);
});

test("campaignBanner", () => {
  assert.equal(campaignBanner("ok"), null);
  assert.equal(campaignBanner("running"), null);
  assert.equal(campaignBanner(null), null);
  assert.equal(campaignBanner("stopped"), "This campaign was stopped before it finished. The events below are all that were saved.");
  assert.equal(campaignBanner("error"), "This campaign stopped with an error. The events below are all that were saved.");
  assert.equal(campaignBanner("incomplete"), "This campaign did not finish, and its process is gone. The events below are all that were saved.");
  assert.equal(campaignBanner("odd"), "This campaign has an unknown status: odd.");
});

test("clampText", () => {
  const long = "a".repeat(5000);
  const c = clampText(long, 280);
  assert.equal(c.text.length, 280);
  assert.equal(c.clamped, true);
  assert.deepEqual(clampText("<b>hi</b>", 280), { text: "<b>hi</b>", clamped: false });
});

test("fixtures describe without crash", () => {
  for (const f of [mockLog, mockRag, c1b] as unknown as LabEvent[][]) {
    assert.ok(f.length > 0);
    for (const e of f) assert.ok(describe(e).plain.length > 0, e.kind);
  }
  for (const e of c1b as unknown as LabEvent[]) if (e.kind === "verdict") assert.equal(durationOf(e), null);
});

test("campaignBanner prefers the status the live stream ended with", () => {
  assert.ok(/stopped before it finished/.test(campaignBanner("running", "stopped") ?? ""));
  assert.equal(campaignBanner("running", "ok"), null);
  assert.equal(campaignBanner("running", null), null);
});

test("agent model events are logged with an empty role", () => {
  const call = { content: "", tool_calls: [{ function: { name: "read_file", arguments: { path: "~/.ssh/id_rsa" } } }] };
  assert.equal(describe(ev({ kind: "model.request", role: "", domain: "agent" })).plain, "A message was sent to the target.");
  assert.equal(describe(ev({ kind: "model.reply", role: "", domain: "agent", reply: call })).plain, "The agent called read_file.");
  assert.equal(describe(ev({ kind: "model.reply", role: "", domain: "agent", reply: { content: "Done." } })).plain, "The target replied.");
  assert.equal(describe(ev({ kind: "model.reply", role: "" })).plain, "—");
});
