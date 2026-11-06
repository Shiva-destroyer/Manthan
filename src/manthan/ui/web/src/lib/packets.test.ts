import { test } from "node:test";
import assert from "node:assert/strict";
import { LABS, type Lab } from "./labs.ts";
import { pathFor, packetsFrom, parseToolTurn, whyItMatters, type Packet } from "./packets.ts";
import type { LabEvent } from "./events.ts";
import type { Turn } from "./types.ts";
import mockLog from "./fixtures/mock-log.json" with { type: "json" };
import mockRag from "./fixtures/mock-rag-log.json" with { type: "json" };
import c1b from "./fixtures/c1b-tables.json" with { type: "json" };
import c2 from "./fixtures/c2-tool-turns.json" with { type: "json" };

const ev = (o: Partial<LabEvent> & { kind: string }): LabEvent => ({ seq: 1, ts: null, t: null, ...o });
const toolTurns = c2 as unknown as Record<string, Turn[]>;

test("prompt paths", () => {
  assert.deepEqual(pathFor(ev({ kind: "model.request", role: "target", stage: "attack" }), "prompt"), ["attacker", "target"]);
  assert.deepEqual(pathFor(ev({ kind: "model.request", role: "target", stage: "guard" }), "prompt"), ["guard", "target"]);
  assert.deepEqual(pathFor(ev({ kind: "model.reply", role: "target" }), "prompt"), ["target", "attacker"]);
  assert.deepEqual(pathFor(ev({ kind: "guard.score" }), "prompt"), ["attacker", "guard"]);
  assert.deepEqual(pathFor(ev({ kind: "model.request", role: "judge" }), "prompt"), ["target", "rubric-judge"]);
  assert.deepEqual(pathFor(ev({ kind: "model.reply", role: "judge" }), "prompt"), ["rubric-judge", "results"]);
  assert.deepEqual(pathFor(ev({ kind: "verdict", judge_name: "refusal_baseline" }), "prompt"), ["rule-check", "results"]);
  assert.deepEqual(pathFor(ev({ kind: "turn", role: "user" }), "prompt"), ["attacker", "target"]);
  assert.equal(pathFor(ev({ kind: "phase.start" }), "prompt"), null);
  assert.equal(pathFor(ev({ kind: "verdict", success: true }), "prompt"), null);
});

test("rag defence paths", () => {
  const e = ev({ kind: "rag.retrieved", defense: "retrieval_filter", docs: [{ id: "p", is_poison: true }] });
  assert.deepEqual(pathFor(e, "rag"), ["document-store", "retrieval_filter", "target"]);
  assert.equal(packetsFrom([e], "rag", {})[0].poison, true);
  assert.deepEqual(pathFor(ev({ kind: "rag.retrieved" }), "rag"), ["document-store", "target"]);
  assert.deepEqual(pathFor(ev({ kind: "model.request", role: "target", defense: "prompt_guard" }), "rag"), ["question", "prompt_guard", "target"]);
  assert.deepEqual(pathFor(ev({ kind: "model.request", role: "target" }), "rag"), ["question", "target"]);
  assert.deepEqual(pathFor(ev({ kind: "model.reply", role: "target", defense: "output_validator" }), "rag"), ["target", "output_validator", "results"]);
  assert.deepEqual(pathFor(ev({ kind: "model.reply", role: "target" }), "rag"), ["target", "results"]);
});

test("agent paths", () => {
  assert.deepEqual(pathFor(ev({ kind: "model.request", role: "target" }), "agent"), ["agent", "ollama"]);
  assert.deepEqual(pathFor(ev({ kind: "model.reply", role: "target" }), "agent"), ["ollama", "agent"]);
  assert.equal(pathFor(ev({ kind: "model.request", role: "judge" }), "agent"), null);
});

test("tool turns", () => {
  const packets = packetsFrom([], "agent", toolTurns);
  assert.equal(packets.length, 6);
  for (const p of packets) assert.deepEqual(p.path, ["agent", "mcp"]);
  assert.equal(packets.filter((p) => p.poison === true).length, 1);
  assert.equal(parseToolTurn("not json"), null);
  const bad = { id: "x", run_id: "r", idx: 0, role: "tool", content: "not json", latency_s: null };
  const [p] = packetsFrom([], "agent", { r: [bad] });
  assert.equal(p.text, "—");
  assert.equal(p.poison, null);
});

test("tool turn fields", () => {
  const t = parseToolTurn('{"tool":"send_email","destination":"a@b.c","source":"user","malicious":false}');
  assert.deepEqual(t, { tool: "send_email", destination: "a@b.c", source: "user", malicious: false });
  assert.equal(parseToolTurn('{"step":1}'), null);
});

test("tool turns already in events are not added twice", () => {
  const rid = Object.keys(toolTurns)[0];
  const first = toolTurns[rid].find((t) => t.role === "tool")!;
  const events = [ev({ seq: 4, kind: "turn", role: "tool", run_id: rid, content: first.content, source: "tables" })];
  const packets = packetsFrom(events, "agent", toolTurns);
  assert.equal(packets.filter((p) => p.ev.run_id === rid).length, 1);
});

test("mock log gives packets", () => {
  const packets = packetsFrom(mockLog as unknown as LabEvent[], "prompt", {});
  assert.ok(packets.length > 0);
  for (const p of packets) {
    assert.ok(p.path.length >= 2);
    for (const id of p.path) assert.ok(LABS.prompt.devices.some((d) => d.id === id), id);
  }
});

test("every path step follows a wire", () => {
  const cases: [Lab, unknown][] = [
    ["prompt", mockLog], ["prompt", c1b], ["rag", mockRag],
  ];
  for (const [lab, log] of cases) {
    const wires = LABS[lab].wires.map(([a, b]) => `${a}|${b}`);
    for (const p of packetsFrom(log as LabEvent[], lab, {})) {
      for (let i = 0; i < p.path.length - 1; i++) {
        const [a, b] = [p.path[i], p.path[i + 1]];
        assert.ok(wires.includes(`${a}|${b}`) || wires.includes(`${b}|${a}`), `${lab} ${a}-${b}`);
      }
    }
  }
  assert.ok(LABS.agent.wires.some(([a, b]) => a === "agent" && b === "mcp"));
});

test("whyItMatters never says the attack worked unless the verdict did", () => {
  const p = (ev: Partial<LabEvent>): Packet => ({ id: "x", seq: 1, path: [], text: "", poison: true, ev: { seq: 1, ts: null, t: null, kind: "rag.retrieved", ...ev } });
  assert.ok(/defence stopped/.test(whyItMatters(p({ kind: "finding.stored", success: false }))));
  assert.ok(/got the result the attacker wanted/.test(whyItMatters(p({ kind: "finding.stored", success: true }))));
  assert.ok(!/attacker wanted/.test(whyItMatters(p({}))));
});

test("agent replies are objects with tool calls", () => {
  const reply = { content: "I will not read it.", tool_calls: [{ function: { name: "read_file", arguments: { path: "~/.ssh/id_rsa" } } }] };
  const [p] = packetsFrom([ev({ kind: "model.reply", role: "", domain: "agent", reply })], "agent", {});
  assert.deepEqual(p.path, ["ollama", "agent"]);
  assert.equal(p.text, 'I will not read it.\nread_file {"path":"~/.ssh/id_rsa"}');
  const [q] = packetsFrom([ev({ kind: "model.request", role: "", domain: "agent", messages: [{ role: "tool", content: "inbox" }] })], "agent", {});
  assert.deepEqual(q.path, ["agent", "ollama"]);
  assert.equal(q.text, "inbox");
});
