import type { Campaign, Rate, Results } from "./types.ts";

// A --db source holds stored results from real runs. The live source also
// holds mock smoke runs, so only a campaign that ran on Ollama counts there.
export function trustedForHeadline(sourceIsLive: boolean, backend: string | null): boolean {
  return !sourceIsLive || backend === "ollama";
}

export type HeadlineItem = { source: string; campaign: Campaign; results: Results };
export type Headline = { source: string; cid: string; rate: Rate };

// The rate with the most attacks behind it. A tie goes to the newer campaign.
export function pickHeadline(items: HeadlineItem[]): Headline | null {
  let best: { h: Headline; created: string } | null = null;
  for (const it of items) {
    for (const rate of it.results.rates) {
      if (rate.k === null || rate.n === null) continue;
      const better =
        best === null ||
        rate.n > (best.h.rate.n ?? 0) ||
        (rate.n === best.h.rate.n && it.campaign.created_at > best.created);
      if (better) best = { h: { source: it.source, cid: it.campaign.id, rate }, created: it.campaign.created_at };
    }
  }
  return best?.h ?? null;
}
