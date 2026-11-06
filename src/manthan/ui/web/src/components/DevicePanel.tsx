import type { ReactNode } from "react";
import { guardLine, residentAt, systemPromptOf } from "../lib/device.ts";
import type { LabEvent } from "../lib/events.ts";
import type { Device } from "../lib/labs.ts";
import type { RoleSettings, Settings } from "../lib/types.ts";
import { Info } from "./Info.tsx";
import { Missing } from "./Missing.tsx";

const NO_CONFIG = "No config file in configs/ matches this campaign, so its settings are unknown.";

function Row({ label, plain, value }: { label: string; plain: string; value: ReactNode }) {
  return (
    <div className="device-row">
      <dt>{label}</dt>
      <dd>
        <span>{plain}</span> <span className="mono">{value}</span>
      </dd>
    </div>
  );
}

// `cursor` is the seq of the event being shown, so "loaded" and the guard score follow the replay.
export function DevicePanel({
  device, settings, events, cursor, onClose,
}: { device: Device; settings: Settings | null; events: LabEvent[]; cursor: number; onClose(): void }) {
  const role: RoleSettings | null = device.role ? (settings?.roles[device.role] ?? null) : null;
  const val = <T extends string | number | null | undefined>(v: T, why = NO_CONFIG) =>
    v === null || v === undefined ? <Missing why={why} /> : String(v);
  const resident = residentAt(events, cursor);
  const system = device.role ? systemPromptOf(events, device.role) : null;
  const guard = device.id === "guard" ? guardLine(events, cursor) : null;
  return (
    <aside className="device-panel" aria-label={`${device.label} settings`}>
      <h2>
        {device.label} <Info name={device.glossary} />
      </h2>
      <button type="button" onClick={onClose}>Close</button>
      <dl>
        {role && (
          <>
            <Row label="Model" plain="The model that plays this role." value={val(role.model)} />
            <Row label="Seed" plain="The random seed of the campaign." value={val(settings?.seed)} />
            <Row label="Temperature" plain="How random the answers are." value={val(role.temperature, role.temperature_why ?? NO_CONFIG)} />
            <Row label="Keep-alive" plain="How long Ollama keeps the model in memory." value={val(role.keep_alive)} />
            <Row label="num_predict" plain="The most tokens one answer may have." value={val(role.num_predict)} />
            <Row
              label="Loaded"
              plain="Whether the model was in memory at this step."
              value={role.model && resident ? (resident.includes(role.model) ? "yes" : "no") : <Missing why="No phase.start event came before this step." />}
            />
            <Row
              label="System prompt"
              plain="The first instruction the model got."
              value={system ?? <Missing why="Table replays do not store the system prompt." />}
            />
          </>
        )}
        {device.id === "guard" && (
          <Row
            label="Guard"
            plain={guard ?? "No guard score came before this step."}
            value={settings?.guard ? settings.guard.model : <Missing why={NO_CONFIG} />}
          />
        )}
        {device.id === "embedder" && (
          <Row label="Embedding" plain="Embedding calls are not logged, so this device never lights up." value="" />
        )}
      </dl>
    </aside>
  );
}
