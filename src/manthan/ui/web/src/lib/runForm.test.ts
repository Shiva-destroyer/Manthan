import { test } from "node:test";
import assert from "node:assert/strict";
import { errorText, formFromParams, reportTarget, toBody, type RunForm } from "./runForm.ts";

const form = (o: Partial<RunForm> = {}): RunForm => ({ ...formFromParams({}), ...o });
const SEED_ERROR = { error: "The seed must be a whole number from 0 to 2147483647." };

test("toBody seed", () => {
  assert.deepEqual(toBody(form({ seed: "" })), { target: "all", smoke: false, seed: null, skip: [], config: null, verbose: false });
  assert.equal((toBody(form({ seed: "1337" })) as { seed: number }).seed, 1337);
  assert.deepEqual(toBody(form({ seed: "-1" })), SEED_ERROR);
  assert.deepEqual(toBody(form({ seed: "1.5" })), SEED_ERROR);
  assert.deepEqual(toBody(form({ seed: "2147483648" })), SEED_ERROR);
});

test("toBody drops skip unless the target is all", () => {
  assert.deepEqual((toBody(form({ target: "prompt", skip: ["rag"] })) as { skip: string[] }).skip, []);
  assert.deepEqual((toBody(form({ target: "all", skip: ["rag"] })) as { skip: string[] }).skip, ["rag"]);
});

test("formFromParams", () => {
  assert.deepEqual(formFromParams({ target: "prompt", config: "manthan-guard-off.yaml", seed: "7", smoke: "1" }), {
    target: "prompt", smoke: true, seed: "7", skip: [], config: "manthan-guard-off.yaml", verbose: false,
  });
  assert.equal(formFromParams({ target: "nope" }).target, "all");
});

test("errorText 409 keeps the server text", () => {
  const e = errorText(409, { error: "A campaign is already running (started outside this page)" });
  assert.equal(e.text, "A campaign is already running (started outside this page)");
});

test("errorText 412 lists the failing check first", () => {
  const checks = [
    { name: "ram", ok: true, detail: "20 GiB free" },
    { name: "models_unloaded", ok: false, detail: "loaded in Ollama: m" },
  ];
  const e = errorText(412, { error: "Not ready to start a run.", checks });
  assert.equal(e.text, "Not ready to start a run.");
  assert.deepEqual(e.checks.map((c) => c.name), ["models_unloaded", "ram"]);
});

test("errorText 422", () => {
  assert.equal(
    errorText(422, { error: "invalid request", detail: [] }).text,
    "The form has a value the server does not accept. Check the seed and the config file.",
  );
});

test("errorText unknown never shows the body", () => {
  assert.equal(errorText(500, "<html>").text, "The server returned an error (500).");
});

test("reportTarget offers a report only for a run that finished cleanly", () => {
  const run = (exit_code: number | null) => ({ name: "run", pid: 1, started_at: "", exit_code, log_tail: "" });
  const old = [{ id: "old" }];
  assert.equal(reportTarget(run(1), null, old), null); // aborted before it made a campaign: "old" is not its campaign
  assert.equal(reportTarget(run(null), "live", old), null);
  assert.equal(reportTarget(run(0), "mine", old), "mine");
  assert.equal(reportTarget(run(0), null, old), "old");
  assert.equal(reportTarget({ ...run(0), name: "init" }, null, old), null);
});
