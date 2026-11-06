import { ActionButton } from "../components/ActionButton.tsx";
import { Empty } from "../components/Empty.tsx";
import { Info } from "../components/Info.tsx";
import { RangeChart } from "../components/RangeChart.tsx";
import { useApi } from "../lib/api.ts";
import { pct } from "../lib/format.ts";
import { hrefFor, navigate } from "../lib/route.ts";
import type { Calibration, JudgeResult } from "../lib/types.ts";

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

const label = (c: Calibration) => `${c.name}  tag=${c.tag ?? "none"}  split=${c.split ?? "none"}`;
const between = (ci: [number, number]) => `${pct(ci[0])} and ${pct(ci[1])}`;
const rubric = (c: Calibration) => c.judges?.find((j) => j.name === "rubric");

function JudgeBlock({ j }: { j: JudgeResult }) {
  return (
    <div className="row">
      <h3>The {j.name.replace(/_/g, " ")} judge</h3>
      <p>
        It wrongly called {pct(j.fpr)} of replies that were not real successes an attack success. The goal is under {pct(j.fpr_target)}.{" "}
        {j.fpr_ok ? "It meets the goal." : "It misses the goal."}
        <Info name="false-positive-rate" />
      </p>
      {j.fpr_ci && <p>The true false-positive rate is likely between {between(j.fpr_ci)}.</p>}
      <p>
        It caught {pct(j.tpr)} of real successes.
        <Info name="true-positive-rate" />
      </p>
      {j.tpr_ci && <p>The true catch rate is likely between {between(j.tpr_ci)}.</p>}
      <p className="muted">Checked on {j.n} replies.</p>
    </div>
  );
}

function Agreement({ c }: { c: Calibration }) {
  const pairs = Object.entries(c.pairwise_kappa ?? {});
  if (c.fleiss_kappa == null && pairs.length === 0) return null;
  return (
    <section aria-labelledby="h-kappa">
      <h2 id="h-kappa">Agreement between judges</h2>
      {pairs.map(([pair, v]) => (
        <p key={pair}>
          {cap(pair.replace(/_/g, " ").replace("|", " and "))}: κ {v.toFixed(2)}
          <Info name="kappa" />
        </p>
      ))}
      {c.fleiss_kappa != null && (
        <p>
          All judges together: κ {c.fleiss_kappa.toFixed(2)}
          <Info name="kappa" />
        </p>
      )}
    </section>
  );
}

function Compare({ files }: { files: Calibration[] }) {
  const rows = files.filter((c) => !c.error && rubric(c));
  const [a, b] = rows;
  if (!a || !b) return null;
  const ra = rubric(a);
  const rb = rubric(b);
  if (!ra || !rb) return null;
  const name = (c: Calibration) => c.tag ?? c.name;
  return (
    <section aria-labelledby="h-cmp">
      <h2 id="h-cmp">Rubric judge across files</h2>
      <p>
        The rubric judge's false-positive rate is {pct(ra.fpr)} in {name(a)} and {pct(rb.fpr)} in {name(b)}.
      </p>
      <RangeChart
        title="Rubric judge false-positive rate by file"
        yLabel="False-positive rate"
        target={{ value: ra.fpr_target, label: `Goal ${pct(ra.fpr_target)}` }}
        points={rows.map((c) => {
          const j = rubric(c) as JudgeResult;
          return { label: name(c), value: j.fpr, lo: j.fpr_ci?.[0] ?? null, hi: j.fpr_ci?.[1] ?? null };
        })}
      />
    </section>
  );
}

export function JudgePage({ params }: { params: URLSearchParams }) {
  const { data, error } = useApi<Calibration[]>("/api/calibrations");
  const chosen = data?.find((c) => c.id === params.get("file")) ?? data?.[0];
  return (
    <>
      <h1>Judge</h1>
      <ActionButton name="calibrate" body={{}} label="Run calibration" confirm="This loads models and can take several minutes. Start?" />
      {error ? (
        <Empty what={error.message} how="Check that `manthan ui` is running, then reload." />
      ) : data && data.length === 0 ? (
        <Empty
          what="No calibration results yet."
          how={
            <>
              Run <code>manthan calibrate --out data/results/calibration.json</code>, or start the UI with{" "}
              <code>--calibration &lt;file&gt;</code>.
            </>
          }
        />
      ) : data && chosen ? (
        <>
          <div className="picker">
            <label>
              <span className="muted">Calibration file</span>
              <select value={chosen.id} onChange={(e) => navigate(hrefFor("judge", { file: e.target.value }))}>
                {data.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.error ? `${c.name}  (cannot be read)` : label(c)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {chosen.error ? (
            <Empty what={chosen.error} how="Fix or replace this file, or pick another one." />
          ) : (
            <>
              <p className="muted">
                {chosen.source ? `${chosen.source}. ` : ""}Saved {chosen.mtime?.slice(0, 16).replace("T", " ")}.
              </p>
              <section aria-labelledby="h-judges">
                <h2 id="h-judges">False alarms and misses</h2>
                {(chosen.judges ?? []).map((j) => (
                  <JudgeBlock key={j.name} j={j} />
                ))}
              </section>
              <Agreement c={chosen} />
              <Compare files={data} />
            </>
          )}
        </>
      ) : (
        <p className="muted">Loading…</p>
      )}
    </>
  );
}
