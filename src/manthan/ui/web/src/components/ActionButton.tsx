import { useState } from "react";
import { lastLines, post, refreshCurrent, useCurrentAction, type Failure } from "../lib/actions.ts";

type Name = "init" | "models_pull" | "calibrate" | "judge" | "report";

export function ActionButton({ name, body, label, confirm }: { name: Name; body: object; label: string; confirm?: string }) {
  const current = useCurrentAction();
  const [mine, setMine] = useState<string | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  const busy = current !== null && current.exit_code === null;

  const click = async () => {
    if (confirm && !window.confirm(confirm)) return;
    const r = await post(`/api/actions/${name}`, body);
    setFailure(r.failure);
    setMine(r.info?.started_at ?? null);
    refreshCurrent();
  };

  const shown = mine !== null && current?.started_at === mine ? current : null;
  return (
    <div className="action">
      <button type="button" disabled={busy} title={busy ? `Another action is running (${current?.name}). Wait for it to end.` : undefined} onClick={() => void click()}>
        {label}
      </button>
      {failure && <span role="alert"> {failure.text}</span>}
      {shown && (
        <>
          <span className="muted">
            {" "}
            {shown.exit_code === null ? "Running." : shown.exit_code === 0 ? "Finished." : `Ended with exit code ${shown.exit_code}.`}
          </span>
          <pre aria-label={`Output of ${label}`}>{lastLines(shown.log_tail, 10) || "No output yet."}</pre>
        </>
      )}
    </div>
  );
}
