import { test } from "node:test";
import assert from "node:assert/strict";
import { pickHeadline, trustedForHeadline } from "./headline.ts";
import type { Campaign, Rate, Results } from "./types.ts";

const camp = (id: string, created_at: string): Campaign => ({
  id, domain: "prompt", config_hash: "h", seed: 1, created_at, label: null, status: "ok",
});
const rate = (k: number | null, n: number | null): Rate => ({
  name: "asr_tap", domain: "prompt", label: "TAP attack", target: null,
  value: 0.5, ci_low: 0.3, ci_high: 0.7, method: "wilson", k, n,
});
const res = (...rates: Rate[]): Results => ({
  rates, rag_curve: [], defences: [], stacked: null, other: [], heatmap: [],
});

test("headline picks largest n", () => {
  const h = pickHeadline([
    { source: "a", campaign: camp("c1", "2026-01-01"), results: res(rate(5, 15)) },
    { source: "a", campaign: camp("c2", "2026-01-02"), results: res(rate(10, 30)) },
  ]);
  assert.equal(h?.cid, "c2");
  assert.equal(h?.rate.n, 30);
});

test("headline tie goes to newest", () => {
  const h = pickHeadline([
    { source: "a", campaign: camp("old", "2026-01-01"), results: res(rate(5, 15)) },
    { source: "a", campaign: camp("new", "2026-02-01"), results: res(rate(6, 15)) },
  ]);
  assert.equal(h?.cid, "new");
});

test("headline needs counts", () => {
  assert.equal(pickHeadline([{ source: "a", campaign: camp("c1", "2026-01-01"), results: res(rate(null, null)) }]), null);
});

test("headline empty", () => {
  assert.equal(pickHeadline([]), null);
});

test("trusted live mock", () => {
  assert.equal(trustedForHeadline(true, "mock"), false);
  assert.equal(trustedForHeadline(true, null), false);
  assert.equal(trustedForHeadline(false, null), true);
  assert.equal(trustedForHeadline(true, "ollama"), true);
});
