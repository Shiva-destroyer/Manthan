import type { LabEvent } from "../lib/events.ts";
import type { Lab } from "../lib/labs.ts";
import { RAG_CHIPS, guardPair, isGuardRun, isLinked, rerunHref, type RunLite } from "../lib/switches.ts";

type Props = {
  lab: Lab;
  runs: RunLite[];
  events: LabEvent[];
  run: RunLite;
  seed: number | null;
  config: string | null;
  onRun: (id: string) => void;
};

// Switches only pick a stored run. "Run this again" links to the Run page and never starts a run.
export function LabSwitches({ lab, runs, events, run, seed, config, onRun }: Props) {
  if (lab === "agent") return <p className="muted">The agent lab has no switch yet. Every run uses the same tools.</p>;
  const guardOn = isGuardRun(run);
  const againConfig = lab === "prompt" && !guardOn ? "manthan-guard-off.yaml" : config;
  return (
    <div className="lab-controls">
      {lab === "prompt" ? (
        <div role="radiogroup" aria-label="Guard">
          {[true, false].map((on) => {
            const pair = guardPair(runs, events, run, on);
            return (
              <button
                key={String(on)}
                type="button"
                role="radio"
                aria-checked={guardOn === on}
                disabled={!pair}
                title={pair ? undefined : `This campaign has no run of this attack ${on ? "through" : "without"} the guard.`}
                onClick={() => pair && onRun(pair.id)}
              >
                Guard {on ? "on" : "off"}
              </button>
            );
          })}
        </div>
      ) : (
        <div role="radiogroup" aria-label="Defence">
          {RAG_CHIPS.map((c) => {
            const target = runs.find((r) => r.objective_id === c.objective);
            return (
              <button
                key={c.objective}
                type="button"
                role="radio"
                aria-checked={run.objective_id === c.objective}
                disabled={!target}
                title={target ? undefined : "This campaign has no stored run for this defence."}
                onClick={() => target && onRun(target.id)}
              >
                {c.label}
              </button>
            );
          })}
        </div>
      )}
      {lab === "prompt" && guardOn && (
        <p className="muted">
          {isLinked(events, run) ? "The same attack was sent again, this time through the guard." : "A run of this attack through the guard."}
        </p>
      )}
      <p>
        <a href={rerunHref(lab, seed, againConfig)}>Run this again</a>{" "}
        <span className="muted">Opens the Run page with these settings. Nothing starts until you press Start run.</span>
      </p>
    </div>
  );
}
