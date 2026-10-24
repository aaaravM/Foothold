"use client";

import * as React from "react";
import { getJSON, isAbortError, isApiError, isOfflineError } from "@/lib/api";

export type ResourceState = "loading" | "ready" | "missing" | "offline" | "error";

export interface Resource<T> {
  data: T | null;
  state: ResourceState;
  /** epoch ms of the last successful read */
  updatedAt: number | null;
}

interface Options {
  /** re-read every N ms while the tab is visible (0 = once) */
  pollMs?: number;
}

/**
 * GET a JSON resource from the Foothold API with an explicit state:
 * "missing" = the endpoint is not there yet (404, e.g. a slice still being built),
 * "offline" = the API is unreachable. Keeps the last good data across failed polls.
 */
export function useApiResource<T>(path: string | null, { pollMs = 0 }: Options = {}): Resource<T> {
  const [resource, setResource] = React.useState<Resource<T>>({ data: null, state: "loading", updatedAt: null });

  React.useEffect(() => {
    if (!path) return;
    let alive = true;
    let controller: AbortController | null = null;

    const read = () => {
      controller?.abort();
      controller = new AbortController();
      getJSON<T>(path, { signal: controller.signal, timeoutMs: 12_000 })
        .then((data) => {
          if (alive) setResource({ data, state: "ready", updatedAt: Date.now() });
        })
        .catch((err: unknown) => {
          if (!alive || isAbortError(err)) return;
          const state: ResourceState = isOfflineError(err)
            ? "offline"
            : isApiError(err) && err.status === 404
              ? "missing"
              : "error";
          setResource((prev) => (prev.data !== null ? prev : { data: null, state, updatedAt: null }));
        });
    };

    read();
    let timer: ReturnType<typeof setInterval> | undefined;
    if (pollMs > 0) {
      timer = setInterval(() => {
        if (typeof document === "undefined" || document.visibilityState === "visible") read();
      }, pollMs);
    }
    return () => {
      alive = false;
      controller?.abort();
      if (timer) clearInterval(timer);
    };
  }, [path, pollMs]);

  return resource;
}
