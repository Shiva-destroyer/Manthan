import { ActionButton } from "../components/ActionButton.tsx";
import { Empty } from "../components/Empty.tsx";
import { Info } from "../components/Info.tsx";
import { Missing } from "../components/Missing.tsx";
import { RangeChart } from "../components/RangeChart.tsx";
import { SourcePicker, useSourceChoice } from "../components/SourcePicker.tsx";
import { useApi } from "../lib/api.ts";
import { formatValue, groupMetrics, nounOf, pct, rateSentence } from "../lib/format.ts";
import { lookup } from "../lib/glossary.ts";
import { hrefFor, navigate } from "../lib/route.ts";
import type { CampaignDetail, Defence, HeatCell, OtherMetric, Rate, Results, Source } from "../lib/types.ts";

const termOf = (name: string) => lookup(name)?.term ?? name;
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

function points(d: Defence): string {
  const n = Math.round(Math.abs(d.dasr) * 100);
  if (n === 0) return "No change";
  return `${d.dasr > 0 ? "Success dropped" : "Success rose"} by ${n} points`;
}

function RatesBlock({ rates }: { rates: Rate[] }) {
  if (rates.length === 0) return null;
  const domains = [...new Set(rates.map((r) => r.domain))];
  return (
    <section aria-labelledby="h-rates">
      <h2 id="h-rates">Attack success</h2>
      <p>
        {rates.length} measured {rates.length === 1 ? "rate" : "rates"} in {domains.length}{" "}
        {domains.length === 1 ? "area" : "areas"}.
      </p>
      {domains.map((d) => (
        <div key={d}>
          <h3>{cap(termOf(d))}</h3>
          {rates
            .filter((r) => r.domain === d)
            .map((r) => (
              <div className="row" key={`${r.name}-${r.target}`}>
                <p>
                  {rateSentence(r, nounOf(r.label))}
                  <Info name={r.name} />
                </p>
                <p className="mono muted">
                  metric={r.name} method={r.method ?? "not stored"} target={r.target ?? "not stored"}
                </p>
              </div>
            ))}
        </div>
      ))}
    </section>
  );
}

function RagBlock({ curve }: { curve: Results["rag_curve"] }) {
  const first = curve[0];
  const last = curve[curve.length - 1];
  if (!first || !last) return null;
  return (
    <section aria-labelledby="h-rag">
      <h2 id="h-rag">Poisoned files</h2>
      <p>
        Success went from {pct(first.value)} with {first.n_poison} poisoned files to {pct(last.value)} with{" "}
        {last.n_poison}.<Info name="asr_n*" />
      </p>
      <RangeChart
        title="Attack success against the number of poisoned files"
        yLabel="Attack success"
        points={curve.map((p) => ({ label: String(p.n_poison), value: p.value, lo: p.ci_low, hi: p.ci_high }))}
      />
    </section>
  );
}

function DefenceBlock({ defences, stacked }: { defences: Defence[]; stacked: Results["stacked"] }) {
  if (defences.length === 0 && !stacked) return null;
  const oracle = defences.filter((d) => d.oracle).length;
  return (
    <section aria-labelledby="h-def">
      <h2 id="h-def">Defences</h2>
      <p>
        {defences.length} {defences.length === 1 ? "defence was" : "defences were"} tested alone
        {oracle > 0 ? `, ${oracle} with a best-case result` : ""}.
      </p>
      <div className="scroll-x">
        <table>
          <thead>
            <tr>
              <th scope="col">Defence</th>
              <th scope="col">Change in success</th>
              <th scope="col">Normal answers right</th>
              <th scope="col">Note</th>
            </tr>
          </thead>
          <tbody>
            {defences.map((d) => (
              <tr key={d.layer}>
                <th scope="row">
                  {termOf(d.layer)}
                  <Info name={d.layer} />
                </th>
                <td>
                  {points(d)}
                  <Info name="dASR_*" />
                </td>
                <td>{d.benign_acc === null ? <Missing why="No normal-answer check was stored for this defence." /> : pct(d.benign_acc)}</td>
                <td>
                  {d.oracle ? (
                    <>
                      Best case: this defence is told which files are poisoned.
                      <Info name="oracle" />
                    </>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {stacked && (
        <p>
          With all defences on, success was {pct(stacked.value)}.<Info name="asr_stacked_defense" />
        </p>
      )}
    </section>
  );
}

// Saffron in four steps by count quartile; the count is always printed in the cell.
function HeatBlock({ cells }: { cells: HeatCell[] }) {
  if (cells.length === 0) return null;
  const owasp = [...new Set(cells.map((c) => c.owasp_id))].sort();
  const atlas = [...new Set(cells.map((c) => c.atlas_id))].sort();
  const count = new Map(cells.map((c) => [`${c.owasp_id}|${c.atlas_id}`, c.count]));
  const sorted = [...cells.map((c) => c.count)].sort((a, b) => a - b);
  const step = (n: number) => {
    const below = sorted.filter((x) => x < n).length / sorted.length;
    return Math.min(3, Math.floor(below * 4));
  };
  const alpha = [0.25, 0.5, 0.75, 1];
  const max = sorted[sorted.length - 1] ?? 0;
  const top = cells.filter((c) => c.count === max);
  return (
    <section aria-labelledby="h-heat">
      <h2 id="h-heat">What was tried</h2>
      <p>
        {top.length === 1 && top[0]
          ? `${top[0].owasp_id} with ${top[0].atlas_id} was tried most often: ${max} attempts.`
          : `${top.length} pairs tie for the most attempts: ${max} each.`}
        <Info name="owasp" />
        <Info name="atlas" />
      </p>
      <div className="scroll-x">
        <table className="heat">
          <thead>
            <tr>
              <th scope="col">OWASP \ ATLAS</th>
              {atlas.map((a) => (
                <th scope="col" key={a} className="mono">
                  {a}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {owasp.map((o) => (
              <tr key={o}>
                <th scope="row" className="mono">
                  {o}
                </th>
                {atlas.map((a) => {
                  const n = count.get(`${o}|${a}`) ?? 0;
                  return n > 0 ? (
                    <td
                      key={a}
                      style={{
                        background: `rgba(227, 168, 74, ${alpha[step(n)]})`,
                        border: "1px solid var(--color-wire)",
                      }}
                    >
                      {n}
                    </td>
                  ) : (
                    <td key={a} className="muted">
                      0
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function OtherBlock({ other }: { other: OtherMetric[] }) {
  if (other.length === 0) return null;
  const groups = groupMetrics(other);
  return (
    <section aria-labelledby="h-other">
      <h2 id="h-other">Other measurements</h2>
      <p>{groups.length} more stored.</p>
      {groups.map((g) => {
        const lo = Math.min(...g.values);
        const hi = Math.max(...g.values);
        const n = g.values.length;
        const shown =
          g.name === "pwned"
            ? `${g.values.filter((v) => v === 1).length} of ${n} trials`
            : lo === hi
              ? formatValue(g.name, lo)
              : `${formatValue(g.name, lo)} to ${formatValue(g.name, hi)}`;
        // A wildcard term such as utility_* reads the same for every attack, so name the attack.
        const id = lookup(g.name)?.id ?? g.name;
        const label = id.endsWith("*")
          ? `${termOf(g.name)} (${g.name.slice(id.length - 1).replace(/_/g, " ")})`
          : termOf(g.name);
        return (
          <p key={`${g.domain}-${g.name}`}>
            {label}: {shown}
            {n > 1 && g.name !== "pwned" && ` (${n} stored values)`}
            <Info name={g.name} /> <span className="mono muted">{g.name}</span>
          </p>
        );
      })}
    </section>
  );
}

function Limits({ r }: { r: Results }) {
  const lines = [
    ...r.defences.filter((d) => d.oracle).map((d) => `${termOf(d.layer)} is a best-case result. A real system would do worse.`),
    ...(r.stacked && r.defences.some((d) => d.oracle)
      ? ["The all-defences result includes best-case defences, so it is a best-case result too."]
      : []),
    ...r.rates
      .filter((x) => x.ci_low === null || x.ci_high === null)
      .map((x) => `${nounOf(x.label)} has no stored range, so it may be less certain than it looks.`),
  ];
  return (
    <aside aria-labelledby="h-limits" className="side">
      <h2 id="h-limits">Honest limits</h2>
      {lines.length === 0 ? <p>Nothing to flag in this campaign.</p> : lines.map((l) => <p key={l}>{l}</p>)}
    </aside>
  );
}

const ASK = "This loads models and can take several minutes. Start?";

// Both actions work on the database the server runs on, so only the live source gets them.
function ActionsBlock({ source, campaign, live }: { source: string; campaign: string; live: boolean }) {
  const detail = useApi<CampaignDetail>(live ? `/api/campaigns/${campaign}?source=${encodeURIComponent(source)}` : null);
  if (!live) return <p className="muted">The report and re-judge buttons work on the live database only.</p>;
  return (
    <section aria-labelledby="h-actions">
      <h2 id="h-actions">Reports and re-judging</h2>
      <ActionButton name="report" body={{ campaign_id: campaign }} label="Make the report" />
      {detail.data && (
        <div className="scroll-x">
          <table>
            <thead>
              <tr>
                <th scope="col">Run</th>
                <th scope="col">Target</th>
                <th scope="col">Status</th>
                <th scope="col">Re-judge</th>
              </tr>
            </thead>
            <tbody>
              {detail.data.runs.filter((r) => !r.objective_id.startsWith("_")).map((r) => (
                <tr key={r.id}>
                  <th scope="row" className="mono">{r.objective_id}</th>
                  <td>{r.target_label}</td>
                  <td>{r.status}</td>
                  <td>
                    <ActionButton name="judge" body={{ run_id: r.id }} label="Judge this run again" confirm={ASK} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

const noResults = (r: Results) =>
  r.rates.length + r.rag_curve.length + r.defences.length + r.heatmap.length + r.other.length === 0 && r.stacked === null;

export function ResultsPage({ params }: { params: URLSearchParams }) {
  const sources = useApi<Source[]>("/api/sources");
  const go = (next: { source: string; campaign: string | null }, replace: boolean) =>
    navigate(hrefFor("results", next.campaign ? { source: next.source, campaign: next.campaign } : { source: next.source }), replace);
  const choice = useSourceChoice(params, go);
  const results = useApi<Results>(
    choice.source && choice.campaign
      ? `/api/campaigns/${choice.campaign}/results?source=${encodeURIComponent(choice.source)}`
      : null,
  );
  const error = choice.error ?? results.error;
  return (
    <>
      <h1>Results</h1>
      {sources.data && <SourcePicker choice={choice} sources={sources.data} go={go} />}
      {error ? (
        <Empty what={error.message} how="Check that `manthan ui` is running and that the database path is right, then reload." />
      ) : choice.campaigns && choice.campaigns.length === 0 ? (
        <Empty what="No campaigns in this database yet." how={<>Start one on the <a href={hrefFor("run", {})}>Run page</a>.</>} />
      ) : results.data && noResults(results.data) ? (
        <Empty what="This campaign has no stored results yet." how="Results appear after a run finishes and its judging step completes." />
      ) : results.data ? (
        <div className="split">
          <div className="main">
            <RatesBlock rates={results.data.rates} />
            <RagBlock curve={results.data.rag_curve} />
            <DefenceBlock defences={results.data.defences} stacked={results.data.stacked} />
            <HeatBlock cells={results.data.heatmap} />
            <OtherBlock other={results.data.other} />
            {choice.source && choice.campaign && (
              <ActionsBlock source={choice.source} campaign={choice.campaign} live={sources.data?.find((x) => x.id === choice.source)?.live === true} />
            )}
          </div>
          <Limits r={results.data} />
        </div>
      ) : (
        <p className="muted">Loading…</p>
      )}
    </>
  );
}
