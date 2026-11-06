import { test } from "node:test";
import assert from "node:assert/strict";
import { vendorOf } from "./vendor.ts";

test("vendorOf maps name prefixes", () => {
  assert.equal(vendorOf("qwen2.5:7b"), "Alibaba");
  assert.equal(vendorOf("phi4-mini"), "Microsoft");
  assert.equal(vendorOf("llama3.2:3b"), "Meta");
  assert.equal(vendorOf("nomic-embed-text"), "Nomic");
  assert.equal(vendorOf("protectai/deberta-v3"), "ProtectAI");
  assert.equal(vendorOf("mistral"), null);
});
