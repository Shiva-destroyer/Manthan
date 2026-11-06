import { useEffect, useReducer, useState } from "react";
import { DevicePanel } from "../components/DevicePanel.tsx";
import { Empty } from "../components/Empty.tsx";
import { EventList } from "../components/EventList.tsx";
import { LabMap } from "../components/LabMap.tsx";
import { LabSwitches } from "../components/LabSwitches.tsx";
import { PacketWindow } from "../components/PacketWindow.tsx";
import { ReplayBar } from "../components/ReplayBar.tsx";
import { ResourceStrip } from "../components/ResourceStrip.tsx";
import { SourcePicker, useSourceChoice } from "../components/SourcePicker.tsx";
import { Tour } from "../components/Tour.tsx";
import { useApi } from "../lib/api.ts";
import { badgeOf, campaignBanner, type LabEvent } from "../lib/events.ts";
import { LABS, deviceForRole, type DeviceId, type Lab } from "../lib/labs.ts";
import { packetsFrom, type Packet } from "../lib/packets.ts";
import { activeCalls, delayMs, replay, type ReplayState } from "../lib/replay.ts";
import { hrefFor, navigate } from "../lib/route.ts";
import { liveRuns } from "../lib/stream.ts";
import { TOUR_STEPS, markTourSeen, pickTourRun, tourCursor, tourSeen } from "../lib/tour.ts";
import { useEventStream } from "../lib/useEventStream.ts";
import type { CampaignDetail, Settings, Source, Turn } from "../lib/types.ts";

const TABS: { id: Lab; label: string }[] = [
  { id: "prompt", label: "Prompt" },
  { id: "agent", label: "Agent" },
  { id: "rag", label: "RAG" },
];
const START: ReplayState = { cursor: -1, playing: false, speed: 1, length: 0 };
const isLab = (v: string | null): v is Lab => v === "prompt" || v === "agent" || v === "rag";
const runLabel = (r: { objective_id: string; target_label: string }) =>
  `${r.objective_id}${r.target_label.endsWith("+guard") ? " (Through the guard)" : ""}`;

export function LabPage({ params }: { params: URLSearchParams }) {
  const sources = useApi<Source[]>("/api/sources");
  const go = (next: { source: string; campaign: string | null }, replace: boolean) =>
    navigate(hrefFor("lab", next.campaign ? { source: next.source, campaign: next.campaign } : { source: next.source }), replace);
  const choice = useSourceChoice(params, go);
  const q = choice.source && choice.campaign ? `${choice.campaign}` : null;
  const src = choice.source ? `source=${encodeURIComponent(choice.source)}` : "";
  const detail = useApi<CampaignDetail>(q ? `/api/campaigns/${q}?${src}` : null);
  const evs = useApi<{ events: LabEvent[]; from_log: boolean }>(q ? `/api/campaigns/${q}/events?${src}` : null);
  const settings = useApi<Settings>(q ? `/api/campaigns/${q}/settings?${src}` : null);

  const domains = detail.data?.campaign.domain.split(",") ?? [];
  const tabParam = params.get("tab");
  const tab: Lab = isLab(tabParam) ? tabParam : (domains.find(isLab) ?? "prompt");
  // Realtime needs a campaign that is still running and has an event log to follow.
  const canLive = detail.data?.campaign.status === "running" && evs.data?.from_log === true;
  const [mode, setMode] = useState<"sim" | "live">("sim");
  const live = canLive && mode === "live";
  const stream = useEventStream(choice.source ?? "", choice.campaign, canLive);
  const all = canLive && stream.events.length > 0 ? stream.events : (evs.data?.events ?? []);
  const runs = canLive && choice.campaign ? liveRuns(all, choice.campaign, tab) : (detail.data?.runs ?? []).filter((r) => r.domain === tab);
  const run = runs.find((r) => r.id === params.get("run")) ?? (live ? runs[runs.length - 1] : runs[0]) ?? null;
  const toolRun = useApi<{ turns: Turn[] }>(tab === "agent" && run ? `/api/runs/${run.id}?${src}` : null);

  const events = run ? all.filter((e) => e.run_id === run.id) : [];
  const packets = packetsFrom(events, tab, run && toolRun.data ? { [run.id]: toolRun.data.turns } : {});

  const [state, dispatch] = useReducer(replay, START);
  useEffect(() => {
    dispatch({ type: "load", length: events.length });
    if (live) dispatch({ type: "seek", to: events.length - 1 });
  }, [events.length, live]);
  useEffect(() => {
    dispatch({ type: "seek", to: -1 });
  }, [run?.id]);
  useEffect(() => {
    if (!state.playing) return;
    const t = setTimeout(() => dispatch({ type: "tick" }), delayMs(events[state.cursor] ?? null, events[state.cursor + 1] ?? events[state.cursor], state.speed));
    return () => clearTimeout(t);
  }, [state.playing, state.cursor, state.speed]);

  // The tour opens once, on a finished campaign that has a plain prompt run with a successful attack.
  const findings = all.flatMap((e) => (e.kind === "finding.stored" && typeof e.run_id === "string" && typeof e.success === "boolean" ? [{ run_id: e.run_id, success: e.success ? 1 : 0 }] : []));
  const tourRun = canLive ? null : pickTourRun(detail.data?.runs ?? [], findings);
  const [tourStep, setTourStep] = useState<number | null>(null);
  const [tourDone, setTourDone] = useState(false);
  useEffect(() => {
    if (!tourRun || tourStep !== null || tourDone || tourSeen()) return;
    markTourSeen();
    setTourStep(0);
    if (tab !== "prompt" || run?.id !== tourRun) {
      navigate(hrefFor("lab", { ...(choice.source ? { source: choice.source } : {}), campaign: choice.campaign ?? "", tab: "prompt", run: tourRun }), true);
    }
  }, [tourRun]);
  const touring = tourStep !== null && run?.id === tourRun;
  const anchor = touring ? TOUR_STEPS[tourStep]!.anchor : null;
  useEffect(() => {
    if (!touring) return;
    const at = tourCursor(TOUR_STEPS[tourStep]!.anchor, events);
    if (at !== null) dispatch({ type: "seek", to: at });
  }, [tourStep, touring, events.length]);
  const nextStep = () => (tourStep! + 1 < TOUR_STEPS.length ? setTourStep(tourStep! + 1) : endTour());
  const endTour = () => {
    setTourStep(null);
    setTourDone(true);
  };

  const [packet, setPacket] = useState<Packet | null>(null);
  const [device, setDevice] = useState<DeviceId | null>(null);

  // Packets that belong to an event sit at that event's place. Table-made tool packets follow the packet before them.
  const place = new Map(events.map((e, i) => [e, i]));
  let last = -1;
  const pos = packets.map((p) => (last = place.get(p.ev) ?? last));
  let current = -1;
  pos.forEach((at, i) => { if (at <= state.cursor && at >= 0) current = i; });

  const active = activeCalls(events, state.cursor)
    .map((c) => deviceForRole(c.role, tab))
    .filter((d): d is DeviceId => d !== null)
    .map((d) => ({ device: d, since: null }));
  const glow = live && stream.ended === null ? activeCalls(events, events.length - 1).flatMap((c) => {
    const d = deviceForRole(c.role, tab);
    return d ? [{ device: d, since: c.ts }] : [];
  }) : active;
  const verdict = events.slice(0, state.cursor + 1).reverse().find((e) => e.kind === "finding.stored" && badgeOf(e) !== null);
  // Newest model seen for each role at or before the cursor, else the first one in the run.
  const models: Record<string, string> = {};
  for (const e of [...events].reverse()) if (typeof e.role === "string" && typeof e.model === "string") models[e.role] = e.model;
  for (const e of events.slice(0, state.cursor + 1)) if (typeof e.role === "string" && typeof e.model === "string") models[e.role] = e.model;
  // Stored runs have no model events, but each run row keeps the target model name.
  if (!models.target && run?.target_label) models.target = run.target_label.replace(/\+guard$/, "");
  const shown = device ? LABS[tab].devices.find((d) => d.id === device) : undefined;
  const banner = campaignBanner(detail.data?.campaign.status ?? null, canLive ? stream.ended : null);
  const error = choice.error ?? detail.error ?? evs.error;
  const tabHref = (t: Lab) => hrefFor("lab", { ...(choice.source ? { source: choice.source } : {}), ...(choice.campaign ? { campaign: choice.campaign } : {}), tab: t });

  return (
    <>
      <h1>Virtual Lab</h1>
      <ResourceStrip replay={!live} />
      {sources.data && <SourcePicker choice={choice} sources={sources.data} go={go} />}
      {error ? (
        <Empty what={error.message} how="Check that `manthan ui` is running and that the database path is right, then reload." />
      ) : choice.campaigns && choice.campaigns.length === 0 ? (
        <Empty what="No campaigns in this database yet." how={<>Start one on the <a href={hrefFor("run", {})}>Run page</a>.</>} />
      ) : !detail.data || !evs.data ? (
        <p className="muted">Loading…</p>
      ) : (
        <>
          {banner && <p className="banner" role="status">{banner}</p>}
          {live && stream.error && <p className="banner" role="status">{stream.error}</p>}
          <div className="lab-controls">
            <nav aria-label="Labs">
              {TABS.map((t) => (
                <a key={t.id} href={tabHref(t.id)} aria-current={t.id === tab ? "page" : undefined}>{t.label}</a>
              ))}
            </nav>
            <div role="radiogroup" aria-label="Mode">
              <button type="button" role="radio" aria-checked={live} disabled={!canLive || stream.ended !== null} title={canLive && stream.ended === null ? undefined : "This campaign is not running."} onClick={() => setMode("live")}>Realtime</button>
              <button type="button" role="radio" aria-checked={!live} onClick={() => setMode("sim")}>Simulation</button>
            </div>
            <label>
              <span className="muted">Run</span>
              <select
                value={run?.id ?? ""}
                disabled={runs.length === 0}
                onChange={(e) => navigate(hrefFor("lab", { ...(choice.source ? { source: choice.source } : {}), campaign: choice.campaign ?? "", tab, run: e.target.value }))}
              >
                {runs.map((r) => <option key={r.id} value={r.id}>{runLabel(r)}</option>)}
              </select>
            </label>
          </div>
          {runs.length === 0 ? (
            <Empty what="This campaign has no runs in this lab." how="Pick another lab tab." />
          ) : (
            <div className="split">
              <div
                className="main"
                tabIndex={0}
                aria-label="Lab map"
                onKeyDown={(e) => {
                  if (e.key === " " && e.target === e.currentTarget && !live) {
                    e.preventDefault();
                    dispatch({ type: state.playing ? "pause" : "play" });
                  }
                }}
              >
                <LabMap lab={tab} packets={packets} current={current} active={glow} verdict={verdict ? badgeOf(verdict) : null} models={models} ringed={anchor === "events" ? null : anchor} onPacket={setPacket} onDevice={setDevice} />
                {live ? <p className="muted">Pause works in Simulation. A live pause needs a core change.</p> : <ReplayBar state={state} dispatch={dispatch} />}
                {run && (
                  <LabSwitches
                    lab={tab}
                    runs={runs}
                    events={all}
                    run={run}
                    seed={detail.data.campaign.seed}
                    config={settings.data?.config ?? null}
                    onRun={(id) => navigate(hrefFor("lab", { ...(choice.source ? { source: choice.source } : {}), campaign: choice.campaign ?? "", tab, run: id }))}
                  />
                )}
                {shown && (
                  <DevicePanel device={shown} settings={settings.data} events={all} cursor={events[state.cursor]?.seq ?? -1} onClose={() => setDevice(null)} />
                )}
              </div>
              <div className={anchor === "events" ? "side tour-on" : "side"}>
                <EventList
                  events={events}
                  cursor={state.cursor}
                  campaign={choice.campaign ?? undefined}
                  onPick={(ev) => {
                    dispatch({ type: "seek", to: events.indexOf(ev) });
                    const p = packets.find((x) => x.ev === ev);
                    if (p) setPacket(p);
                  }}
                />
              </div>
            </div>
          )}
          {touring && <Tour step={tourStep!} onNext={nextStep} onSkip={endTour} />}
          {packet && <PacketWindow packet={packet} onClose={() => setPacket(null)} />}
        </>
      )}
    </>
  );
}
