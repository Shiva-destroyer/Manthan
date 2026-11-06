import { useEffect } from "react";
import { useApi } from "../lib/api.ts";
import type { ApiError } from "../lib/api.ts";
import { trustedForHeadline } from "../lib/headline.ts";
import type { Campaign, Settings, Source } from "../lib/types.ts";

export type Choice = { source: string | null; campaign: string | null; campaigns: Campaign[] | null; error: ApiError | null };

// Reads the source and campaign from the hash params. A missing one defaults to the first live source
// and its newest campaign, and the hash is rewritten so the address always names what is on screen.
export function useSourceChoice(
  params: URLSearchParams,
  go: (next: { source: string; campaign: string | null }, replace: boolean) => void,
): Choice {
  const sources = useApi<Source[]>("/api/sources");
  const source = params.get("source") ?? (sources.data ? (sources.data.find((s) => s.live) ?? sources.data[0])?.id : null) ?? null;
  const list = useApi<Campaign[]>(source ? `/api/campaigns?source=${encodeURIComponent(source)}` : null);
  const campaign = params.get("campaign") ?? list.data?.[0]?.id ?? null;
  useEffect(() => {
    if (source && list.data && (params.get("source") !== source || params.get("campaign") !== campaign)) {
      go({ source, campaign }, true);
    }
  });
  return { source, campaign, campaigns: list.data, error: sources.error ?? list.error };
}

const stamp = (c: Campaign) => `${c.created_at.slice(0, 16).replace("T", " ")}  ${c.id.slice(0, 8)}${c.label ? `  ${c.label}` : ""}`;

export function SourcePicker({
  choice,
  sources,
  go,
}: {
  choice: Choice;
  sources: Source[];
  go: (next: { source: string; campaign: string | null }, replace: boolean) => void;
}) {
  const live = sources.find((s) => s.id === choice.source)?.live === true;
  const settings = useApi<Settings>(live && choice.campaign ? `/api/campaigns/${choice.campaign}/settings?source=${encodeURIComponent(choice.source!)}` : null);
  const untrusted = settings.data && !trustedForHeadline(live, settings.data.backend);
  return (
    <>
    <div className="picker">
      <label>
        <span className="muted">Database</span>
        <select value={choice.source ?? ""} onChange={(e) => go({ source: e.target.value, campaign: null }, false)}>
          {sources.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
              {s.live ? " (live)" : ""}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span className="muted">Campaign</span>
        <select
          value={choice.campaign ?? ""}
          disabled={!choice.campaigns?.length}
          onChange={(e) => choice.source && go({ source: choice.source, campaign: e.target.value }, false)}
        >
          {(choice.campaigns ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {stamp(c)}
            </option>
          ))}
        </select>
      </label>
    </div>
    {untrusted && (
      <p className="banner" role="status">
        This campaign has no Ollama run on record, so it may be a test run with stand-in models. Do not read its numbers as real results.
      </p>
    )}
    </>
  );
}
