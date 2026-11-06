import { test } from "node:test";
import assert from "node:assert/strict";
import { lookup } from "./glossary.ts";

const cases: [string, string | null][] = [
  ["asr_n1", "asr_n*"],
  ["asr_crescendo", "asr_*"],
  ["benign_acc:prompt_guard", "benign_acc*"],
  ["inline_vs_authoritative_kappa", "*_kappa"],
  ["prompt_leak_rate_defended", "prompt_leak_rate*"],
  ["crescendo", "crescendo"],
  ["zzz", null],
];

for (const [name, id] of cases) {
  test(`lookup ${name}`, () => {
    assert.equal(lookup(name)?.id ?? null, id);
  });
}
