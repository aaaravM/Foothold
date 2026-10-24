"use client";

import { useCallback, useReducer } from "react";
import { isAbortError, isOfflineError, streamSSE, type StreamOptions } from "@/lib/api";
import { createTraceState, traceReducer, type TraceAction, type TraceState } from "@/lib/trace";
import type { TraceEvent, TraceNode } from "@/lib/types";

export interface UseTraceResult {
  state: TraceState;
  /** shortcut for state.nodes (TracePanel takes both) */
  nodes: TraceNode[];
  /** feed one SSE event (pass to streamSSE as the onEvent callback) */
  onEvent: (event: TraceEvent) => void;
  dispatch: (action: TraceAction) => void;
  reset: () => void;
  /**
   * POST + stream a LangGraph run into this trace. Never throws: failures land in
   * `state.error` ("API offline: ..." when the API is down). Resolves true when the
   * stream finished normally, false on error or abort.
   */
  run: (path: string, body: unknown, signal?: AbortSignal, options?: StreamOptions) => Promise<boolean>;
}

/** Reduce CONTRACTS section 6 TraceEvents into TracePanel state. */
export function useTrace(): UseTraceResult {
  const [state, dispatch] = useReducer(traceReducer, undefined, createTraceState);

  const onEvent = useCallback((event: TraceEvent) => dispatch(event), []);
  const reset = useCallback(() => dispatch({ type: "reset" }), []);

  const run = useCallback(async (path: string, body: unknown, signal?: AbortSignal, options?: StreamOptions) => {
    dispatch({ type: "connecting" });
    try {
      await streamSSE(path, body, (event) => dispatch(event), signal, options);
      if (signal?.aborted) return false;
      dispatch({ type: "stream-end" });
      return true;
    } catch (err) {
      if (isAbortError(err)) return false;
      const message = isOfflineError(err)
        ? "API offline: start the API (port 8000) and try again."
        : err instanceof Error
          ? err.message
          : "Request failed";
      dispatch({ type: "error", message });
      return false;
    }
  }, []);

  return { state, nodes: state.nodes, onEvent, dispatch, reset, run };
}
