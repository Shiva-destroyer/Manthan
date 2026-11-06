import { useEffect, useState } from "react";
import { Empty } from "../components/Empty.tsx";
import { Info } from "../components/Info.tsx";
import { type Action, type Failure, post } from "../lib/actions.ts";
import { getJSON, useApi } from "../lib/api.ts";
import { hrefFor } from "../lib/route.ts";
import { CHECK_LINES, formFromParams, reportTarget, toBody, type Check, type RunForm } from "../lib/runForm.ts";
import type { Campaign, Source } from "../lib/types.ts";

function usePoll<T>(path: string | null, ms: number): T | null {
  const [data, setData] = useState<T | null>(null);
  useEffect(() => {
    if (path === null) return;
    let live = true;
    const load = () => {
      getJSON<T>(path).then(
        (d) => {
          if (live) setData(d);
        },
        () => {
          // A failed poll keeps the last answer; the next tick tries again.
        },
      );
    };
    load();
    const t = setInterval(load, ms);
    return () => {
      live = false;
      clearInterval(t);
    };
  }, [path, ms]);
  return data;
}

const last40 = (text: string) => text.split("\n").slice(-40).join("\n");
const TARGETS: RunForm["target"][] = ["prompt", "agent", "rag", "all"];

export function RunPage({ params }: { params: URLSearchParams }) {
  const [form, setForm] = useState<RunForm>(() => formFromParams(Object.fromEntries(params)));
  const [failure, setFailure] = useState<Failure | null>(null);
  const [campaign, setCampaign] = useState<string | null>(null);
  const system = useApi<{ configs: { name: string; text: string; runnable?: boolean }[] }>("/api/system");
  const sources = useApi<Source[]>("/api/sources");
  const live = sources.data?.find((s) => s.live) ?? null;

  const current = usePoll<Action | null>("/api/actions/current", 2000);
  const running = current !== null && current.exit_code === null;
  const preflight = usePoll<{ ok: boolean; checks: Check[] }>(running ? null : "/api/preflight", 5000);
  const campaigns = usePoll<Campaign[]>(current?.name === "run" && live ? `/api/campaigns?source=${encodeURIComponent(live.id)}` : null, 2000);
  const runningCampaign = campaigns?.find((c) => c.status === "running")?.id ?? null;
  useEffect(() => {
    if (runningCampaign) setCampaign(runningCampaign);
  }, [runningCampaign]);

  const set = (patch: Partial<RunForm>) => setForm({ ...form, ...patch });
  const chosen = system.data?.configs.find((c) => c.name === form.config);
  const reportFor = reportTarget(current, campaign, campaigns);
  const labHref = live ? hrefFor("lab", campaign ? { source: live.id, campaign } : { source: live.id }) : null;

  const start = async () => {
    const body = toBody(form);
    if ("error" in body) return setFailure({ text: body.error, checks: [] });
    setFailure(null);
    setCampaign(null);
    const r = await post("/api/actions/run", body);
    if (r.failure) setFailure(r.failure);
  };
  const stop = async () => {
    const r = await post("/api/actions/stop", {});
    setFailure(r.failure);
  };
  const report = async () => {
    if (!reportFor) return;
    const r = await post("/api/actions/report", { campaign_id: reportFor });
    setFailure(r.failure);
  };

  if (system.error) {
    return (
      <>
        <h1>Run</h1>
        <Empty what={system.error.message} how="Check that `manthan ui` is running, then reload." />
      </>
    );
  }
  return (
    <>
      <h1>Run</h1>
      <p className="muted">Start a campaign from here. It uses the config files in the configs folder and never edits them.</p>
      <div className="run-split">
        <form className="run-form" onSubmit={(e) => { e.preventDefault(); void start(); }}>
          <fieldset>
            <legend>Target</legend>
            {TARGETS.map((t) => (
              <label key={t}>
                <input type="radio" name="target" checked={form.target === t} onChange={() => set({ target: t })} /> {t}
              </label>
            ))}
          </fieldset>
          <label>
            <input type="checkbox" checked={form.smoke} onChange={(e) => set({ smoke: e.target.checked })} /> Smoke run (a few trials only) <Info name="smoke" />
          </label>
          <label>
            <span className="muted">Seed (empty uses the config seed) <Info name="seed" /></span>
            <input type="text" inputMode="numeric" value={form.seed} onChange={(e) => set({ seed: e.target.value })} />
          </label>
          <fieldset disabled={form.target !== "all"}>
            <legend>Skip (only when the target is all)</legend>
            {(["prompt", "agent", "rag"] as const).map((d) => (
              <label key={d}>
                <input
                  type="checkbox"
                  checked={form.skip.includes(d)}
                  onChange={(e) => set({ skip: e.target.checked ? [...form.skip, d] : form.skip.filter((s) => s !== d) })}
                />{" "}
                {d}
              </label>
            ))}
          </fieldset>
          <label>
            <span className="muted">Config file</span>
            <select value={form.config} onChange={(e) => set({ config: e.target.value })}>
              <option value="">Default (the config this server started with)</option>
              {(system.data?.configs ?? []).filter((c) => c.runnable !== false).map((c) => (
                <option key={c.name} value={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          {chosen ? <pre className="mono" tabIndex={0} aria-label={`Contents of ${chosen.name}`}>{chosen.text}</pre> : null}
          <label>
            <input type="checkbox" checked={form.verbose} onChange={(e) => set({ verbose: e.target.checked })} /> Verbose log
          </label>
          <button type="submit" disabled={running}>Start run</button>
        </form>
        <div className="run-side">
          <h2>Ready to run</h2>
          {preflight === null ? (
            <p className="muted">{running ? "A run is going, so the checks are paused." : "Loading…"}</p>
          ) : (
            preflight.checks.map((c) => (
              <p key={c.name} className="row">
                <strong>{CHECK_LINES[c.name]?.[c.ok ? "pass" : "fail"] ?? `${c.name} ${c.ok ? "passes" : "fails"}`}</strong>{" "}
                <span className="mono muted">{c.detail}</span>
              </p>
            ))
          )}
          {failure && (
            <div role="alert" className="banner">
              <p>{failure.text}</p>
              {failure.checks.map((c) => (
                <p key={c.name} className="row">
                  {CHECK_LINES[c.name]?.[c.ok ? "pass" : "fail"] ?? c.name} <span className="mono muted">{c.detail}</span>
                </p>
              ))}
            </div>
          )}
          <h2>Progress</h2>
          {current === null ? (
            <p className="muted">Nothing has run from this page yet.</p>
          ) : (
            <>
              <p>
                {current.name === "run" ? "Run" : current.name}{" "}
                {current.exit_code === null ? "is running." : current.exit_code === 0 ? "finished." : `ended with exit code ${current.exit_code}.`}
              </p>
              <div className="run-actions">
                {running && <button type="button" onClick={() => void stop()}>Stop run</button>}
                {current.name === "run" && labHref && <a className="button-link" href={labHref}>Open Virtual Lab</a>}
                {current.name === "run" && !running && reportFor && <button type="button" onClick={() => void report()}>Make the report</button>}
              </div>
              <pre className="mono" tabIndex={0} aria-label="Log, last 40 lines">{last40(current.log_tail)}</pre>
            </>
          )}
        </div>
      </div>
    </>
  );
}
