import { useEffect, useState } from "react";
import { LoopDrawing } from "../components/LoopDrawing.tsx";
import { getJSON } from "../lib/api.ts";
import { nounOf, rateSentence } from "../lib/format.ts";
import { type Headline, type HeadlineItem, pickHeadline, trustedForHeadline } from "../lib/headline.ts";
import { hrefFor } from "../lib/route.ts";
import type { Campaign, Results, Settings, Source } from "../lib/types.ts";

// Only the newest campaigns of each source are read, so Home stays quick on a long history.
const PER_SOURCE = 10;

const q = encodeURIComponent;
const orNull = <T,>(p: Promise<T>): Promise<T | null> => p.catch(() => null);

async function loadHeadline(signal: AbortSignal): Promise<Headline | null> {
  const sources = await getJSON<Source[]>("/api/sources", signal);
  const items: HeadlineItem[] = [];
  for (const s of sources) {
    const camps = (await getJSON<Campaign[]>(`/api/campaigns?source=${q(s.id)}`, signal)).slice(0, PER_SOURCE);
    const rows = await Promise.all(
      camps.map(async (campaign) => {
        const backend = s.live ? ((await orNull(getJSON<Settings>(`/api/campaigns/${campaign.id}/settings?source=${q(s.id)}`, signal)))?.backend ?? null) : null;
        if (!trustedForHeadline(s.live, backend)) return null;
        const results = await orNull(getJSON<Results>(`/api/campaigns/${campaign.id}/results?source=${q(s.id)}`, signal));
        return results ? { source: s.id, campaign, results } : null;
      }),
    );
    for (const r of rows) if (r) items.push(r);
  }
  return pickHeadline(items);
}

type State = { loading: true } | { loading: false; headline: Headline | null; error: string | null };

function useHeadline(): State {
  const [state, setState] = useState<State>({ loading: true });
  useEffect(() => {
    const ctl = new AbortController();
    loadHeadline(ctl.signal).then(
      (headline) => setState({ loading: false, headline, error: null }),
      (e: unknown) => {
        if (!ctl.signal.aborted) setState({ loading: false, headline: null, error: e instanceof Error ? e.message : "The server did not answer." });
      },
    );
    return () => ctl.abort();
  }, []);
  return state;
}

function WhatYouGet({ state }: { state: State }) {
  if (state.loading) return <p>Reading the stored results.</p>;
  if (state.error) return <p>The stored results could not be read. {state.error}</p>;
  const h = state.headline;
  if (!h) return <p>No campaign has stored a counted result yet. Run one from the Run page.</p>;
  return (
    <>
      <p>This is the stored result with the most attacks behind it.</p>
      <p className="home-result">{rateSentence(h.rate, nounOf(h.rate.label))}</p>
      <p>
        <a href={hrefFor("results", { source: h.source, campaign: h.cid })}>Open this campaign in Results</a>
        {" or "}
        <a href={hrefFor("lab", { source: h.source, campaign: h.cid })}>watch it in the Virtual Lab</a>.
      </p>
    </>
  );
}

export function HomePage() {
  const state = useHeadline();
  // The first screen opens the same real campaign as "What you get", never the live test runs.
  const at: Record<string, string> = !state.loading && state.headline ? { source: state.headline.source, campaign: state.headline.cid } : {};
  return (
    <div className="home">
      <header className="home-hero">
        <h1>Manthan</h1>
        <p className="home-tagline">Churn the model; separate the poison from the nectar.</p>
        <p>
          Manthan attacks a language model that runs on your own computer. A judge scores each reply, and Manthan
          counts how often the attack works.
        </p>
        <p className="home-actions">
          <a className="button-link button-primary" href={hrefFor("lab", at)}>Watch an attack in the Virtual Lab</a>
          <a className="button-link" href={hrefFor("results", at)}>See the results</a>
        </p>
      </header>
      <div className="home-loop">
        <LoopDrawing />
      </div>
      <section className="home-part">
        <h2>Why</h2>
        <p>A language model can be talked out of its rules. A poisoned file can steer a model that reads it.</p>
        <p>Manthan counts how often that happens, on models that run on your own computer.</p>
      </section>
      <section className="home-part">
        <h2>What it needs</h2>
        <p>Ollama running on this computer, with the models named on the System page.</p>
        <p>Manthan uses local models only and needs no API key. The Run page checks each need before it starts.</p>
      </section>
      <section className="home-part">
        <h2>How it works</h2>
        <p>An attacker model writes a prompt and the target model answers it. A judge scores the answer.</p>
        <p>Manthan stores each score and tries again. Many tries give a count, not a single story.</p>
      </section>
      <section className="home-part home-get">
        <h2>What you get</h2>
        <WhatYouGet state={state} />
      </section>
    </div>
  );
}
