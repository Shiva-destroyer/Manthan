import type { Dispatch } from "react";
import type { ReplayAction, ReplayState, Speed } from "../lib/replay.ts";

const SPEEDS: Speed[] = [1, 2, 4, 8];

export function ReplayBar({ state, dispatch }: { state: ReplayState; dispatch: Dispatch<ReplayAction> }) {
  return (
    <div className="replay-bar" role="group" aria-label="Replay controls">
      <button type="button" onClick={() => dispatch({ type: "step", by: -1 })}>Step back</button>
      <button type="button" onClick={() => dispatch({ type: state.playing ? "pause" : "play" })}>
        {state.playing ? "Pause" : "Play"}
      </button>
      <button type="button" onClick={() => dispatch({ type: "step", by: 1 })}>Step forward</button>
      <div role="radiogroup" aria-label="Speed">
        {SPEEDS.map((s) => (
          <button key={s} type="button" role="radio" aria-checked={state.speed === s} onClick={() => dispatch({ type: "speed", speed: s })}>
            {s}x
          </button>
        ))}
      </div>
      <input
        type="range"
        aria-label="Position in the run"
        min={-1}
        max={Math.max(state.length - 1, -1)}
        value={state.cursor}
        onChange={(e) => dispatch({ type: "seek", to: Number(e.target.value) })}
      />
    </div>
  );
}
