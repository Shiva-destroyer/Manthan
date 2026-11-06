import { test } from "node:test";
import assert from "node:assert/strict";
import { hrefFor, parseHash } from "./route.ts";

test("empty hash gives the home page", () => {
  assert.equal(parseHash("").page, "home");
});

test("judge hash keeps its params", () => {
  const r = parseHash("#/judge?file=ab");
  assert.equal(r.page, "judge");
  assert.equal(r.params.get("file"), "ab");
});

test("unknown page gives the home page", () => {
  assert.equal(parseHash("#/nope").page, "home");
});

test("hrefFor builds a hash link", () => {
  assert.equal(hrefFor("system", { source: "x" }), "#/system?source=x");
  assert.equal(hrefFor("results", {}), "#/results");
});

test("lab page keeps its params", () => {
  const r = parseHash("#/lab?source=a&campaign=b&tab=rag");
  assert.equal(r.page, "lab");
  assert.equal(r.params.get("tab"), "rag");
  assert.equal(r.params.get("campaign"), "b");
});

test("run page keeps its params", () => {
  const r = parseHash("#/run?target=prompt&seed=7&smoke=1");
  assert.equal(r.page, "run");
  assert.equal(r.params.get("seed"), "7");
});
