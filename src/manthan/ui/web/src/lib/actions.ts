import { useSyncExternalStore } from "react";
import { getJSON } from "./api.ts";
import { errorText, type Check } from "./runForm.ts";

export type Action = { name: string; pid: number; started_at: string; exit_code: number | null; log_tail: string };
export type Failure = { text: string; checks: Check[] };

export async function post(path: string, body: unknown): Promise<{ ok: boolean; failure: Failure | null; info: Action | null }> {
  try {
    const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (res.ok) return { ok: true, failure: null, info: (await res.json().catch(() => null)) as Action | null };
    const parsed: unknown = await res.json().catch(() => null);
    return { ok: false, failure: errorText(res.status, parsed), info: null };
  } catch {
    return { ok: false, failure: { text: "The server did not answer. Check that `manthan ui` is still running.", checks: [] }, info: null };
  }
}

// One shared poll for every button on a page: a run list can hold many buttons.
let snapshot: Action | null = null;
let timer: ReturnType<typeof setInterval> | undefined;
const listeners = new Set<() => void>();

export function refreshCurrent(): void {
  getJSON<Action | null>("/api/actions/current").then(
    (d) => {
      snapshot = d;
      listeners.forEach((f) => f());
    },
    () => {
      // A failed poll keeps the last answer; the next tick tries again.
    },
  );
}

function subscribe(f: () => void): () => void {
  listeners.add(f);
  if (listeners.size === 1) {
    refreshCurrent();
    timer = setInterval(refreshCurrent, 2000);
  }
  return () => {
    listeners.delete(f);
    if (listeners.size === 0) clearInterval(timer);
  };
}

export const useCurrentAction = (): Action | null => useSyncExternalStore(subscribe, () => snapshot);

export const lastLines = (text: string, n: number): string => text.split("\n").filter((l) => l !== "").slice(-n).join("\n");
