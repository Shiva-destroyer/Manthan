import { test } from "node:test";
import assert from "node:assert/strict";
import { bytesToGB, formatValue, groupMetrics, rateSentence } from "./format.ts";

test("rateSentence with k, n and a stored range", () => {
  assert.equal(
    rateSentence({ k: 4, n: 15, value: 0.26666666666666666, ci_low: 0.109, ci_high: 0.52 }, "Crescendo"),
    "4 of 15 Crescendo attacks worked (27%). The true rate is likely between 11% and 52%.",
  );
});

test("rateSentence without k, n or a range", () => {
  assert.equal(
    rateSentence({ k: null, n: null, value: 0.333, ci_low: null, ci_high: null }, "Poisoned RAG"),
    "Poisoned RAG attacks worked 33% of the time. No range is stored for this rate.",
  );
});

test("formatValue picks a unit from the name", () => {
  assert.equal(formatValue("peak_ollama_rss_mb", 9899.7), "9,900 MB");
  assert.equal(formatValue("uplift_crescendo", 26.667), "26.7 pts");
  assert.equal(formatValue("inline_vs_authoritative_kappa", 0.416), "κ 0.42");
  assert.equal(formatValue("prompt_leak_rate", 0.75), "75%");
  assert.equal(formatValue("steps_to_exfil", 3.5), "3.50");
  assert.equal(formatValue("agent_lab_docker", 1), "Docker lab");
  assert.equal(formatValue("agent_lab_docker", 0), "Simulated lab");
});

test("bytesToGB", () => {
  assert.equal(bytesToGB(4683087332), "4.7 GB");
});

test("groupMetrics merges repeated rows into one line each", () => {
  const rows = [
    { domain: "agent", name: "pwned", value: 0 },
    { domain: "agent", name: "pwned", value: 0 },
    { domain: "agent", name: "pwned", value: 1 },
    { domain: "rag", name: "prompt_leak_rate", value: 0.75 },
  ];
  assert.deepEqual(groupMetrics(rows), [
    { domain: "agent", name: "pwned", values: [0, 0, 1] },
    { domain: "rag", name: "prompt_leak_rate", values: [0.75] },
  ]);
});
