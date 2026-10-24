"use client";

import { useCallback, useEffect, useRef } from "react";
import { useTrace } from "@/components/foothold/use-trace";
import { isAbortError, isApiError, isOfflineError, streamSSE } from "@/lib/api";
import type { TraceEvent } from "@/lib/types";

/** Readable message for a failed request (FastAPI `detail` when present). */
export function errorMessage(err: unknown): string {
  if (isOfflineError(err)) return "API offline: the Foothold server isn't reachable. Start it and try again.";
  if (isApiError(err) && err.kind === "http") {
    const body = err.body as { detail?: unknown } | undefined;
    if (body && typeof body.detail === "string") return body.detail;
    if (err.status === 401) return "Your session ended. Sign in again.";
    return `Request failed (HTTP ${err.status}).`;
  }
  return err instanceof Error ? err.message : "Request failed.";
}

/**
 * useTrace plus a tap: every SSE event goes to the TracePanel reducer AND to `onTap`, so a page
 * can accumulate things the merged `state.data` would overwrite (e.g. parallel coworker reactions).
 */
export function useTappedTrace(onTap: (event: TraceEvent) => void) {
  const trace = useTrace();
  const tapRef = useRef(onTap);
  useEffect(() => {
    tapRef.current = onTap;
  }, [onTap]);
  const abortRef = useRef<AbortController | null>(null);
  const { dispatch } = trace;

  const run = useCallback(
    async (path: string, body: unknown): Promise<boolean> => {
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      dispatch({ type: "connecting" });
      try {
        await streamSSE(
          path,
          body,
          (event) => {
            dispatch(event);
            tapRef.current(event);
          },
          ctrl.signal,
          { idleTimeoutMs: 120_000 },
        );
        if (ctrl.signal.aborted) return false;
        dispatch({ type: "stream-end" });
        return true;
      } catch (err) {
        if (isAbortError(err)) return false;
        const message = errorMessage(err);
        dispatch({ type: "error", message });
        tapRef.current({ type: "error", message });
        return false;
      }
    },
    [dispatch],
  );

  const cancel = useCallback(() => abortRef.current?.abort(), []);
  return { trace, run, cancel };
}
