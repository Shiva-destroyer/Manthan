import { useEffect, useState } from "react";
import { getJSON } from "../lib/api.ts";
import type { Resources } from "../lib/types.ts";
import { Missing } from "./Missing.tsx";

const POLL_MS = 5000;

// `replay` adds a lead-in so nobody reads this laptop's state as the stored run's state.
export function ResourceStrip({ replay }: { replay: boolean }) {
  const [res, setRes] = useState<Resources | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  useEffect(() => {
    const ctl = new AbortController();
    const load = () =>
      getJSON<Resources>("/api/resources", ctl.signal).then(
        (r) => { setRes(r); setFailed(null); },
        (e: unknown) => { if (!ctl.signal.aborted) setFailed(e instanceof Error ? e.message : "The request failed."); },
      );
    load();
    const t = setInterval(load, POLL_MS);
    return () => { ctl.abort(); clearInterval(t); };
  }, []);
  const why = failed ?? "The server did not send this value.";
  const loaded = res?.ollama_ps ? res.ollama_ps.map((m) => m.name ?? "—").join(", ") || "none" : null;
  return (
    <div className="resource-strip" role="group" aria-label="Resources">
      {replay && <span className="muted">This laptop now:</span>}
      <span>Free RAM {res?.free_ram_gb != null ? `${res.free_ram_gb.toFixed(1)} GB` : <Missing why={why} />}</span>
      <span>Loaded models {loaded ?? <Missing why={res?.ollama_error ?? why} />}</span>
      <span>
        Used {res?.used_min != null ? res.used_min.toFixed(0) : <Missing why={failed ?? "No campaign is running on this laptop now."} />} of{" "}
        {res?.budget_min != null ? res.budget_min : <Missing why={why} />} minutes
      </span>
    </div>
  );
}
