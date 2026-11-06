import { useEffect, useState } from "react";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { signal });
  if (!res.ok) {
    let message = `The request failed (status ${res.status}).`;
    try {
      const body = await res.json();
      const text = body?.detail ?? body?.error;
      if (typeof text === "string") message = text;
    } catch {
      // keep the default message
    }
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

type State<T> = { path: string | null; data: T | null; error: ApiError | null; loading: boolean };

// The cleanup aborts the earlier request, and a result is only used for the path it was asked for,
// so a fast switch never shows the old answer.
export function useApi<T>(path: string | null): { data: T | null; error: ApiError | null; loading: boolean } {
  const [state, setState] = useState<State<T>>({ path, data: null, error: null, loading: path !== null });
  useEffect(() => {
    if (path === null) return;
    const ctl = new AbortController();
    setState({ path, data: null, error: null, loading: true });
    getJSON<T>(path, ctl.signal).then(
      (data) => setState({ path, data, error: null, loading: false }),
      (e: unknown) => {
        if (ctl.signal.aborted) return;
        const error =
          e instanceof ApiError ? e : new ApiError(0, "The server did not answer. Check that `manthan ui` is still running.");
        setState({ path, data: null, error, loading: false });
      },
    );
    return () => ctl.abort();
  }, [path]);
  return state.path === path ? state : { data: null, error: null, loading: path !== null };
}
