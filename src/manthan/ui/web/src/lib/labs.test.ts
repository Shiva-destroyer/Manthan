import { test } from "node:test";
import assert from "node:assert/strict";
import { LABS, deviceForRole, type Lab } from "./labs.ts";
import { lookup } from "./glossary.ts";

const labs = Object.keys(LABS) as Lab[];

test("every device has a glossary entry", () => {
  for (const lab of labs) for (const d of LABS[lab].devices) assert.ok(lookup(d.glossary) !== null, `${lab}/${d.id}`);
});

test("devices fit the viewBox", () => {
  for (const lab of labs) {
    const seen = new Set<string>();
    for (const d of LABS[lab].devices) {
      assert.ok(d.x >= 40 && d.x <= 960 && d.y >= 40 && d.y <= 560, `${lab}/${d.id}`);
      const key = `${d.x},${d.y}`;
      assert.ok(!seen.has(key), `${lab}/${d.id} shares a point`);
      seen.add(key);
    }
  }
});

test("wires join devices of the same lab", () => {
  for (const lab of labs) {
    const ids = new Set(LABS[lab].devices.map((d) => d.id));
    for (const [a, b] of LABS[lab].wires) assert.ok(ids.has(a) && ids.has(b), `${lab} ${a}-${b}`);
  }
});

test("deviceForRole", () => {
  assert.equal(deviceForRole("judge", "prompt"), "rubric-judge");
  assert.equal(deviceForRole("target", "agent"), "agent");
  assert.equal(deviceForRole("embed", "rag"), "embedder");
  assert.equal(deviceForRole("attacker", "rag"), null);
});
