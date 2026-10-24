"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { API_URL, getJSON, isAbortError, isApiError } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export type ApiHealthStatus = "checking" | "online" | "degraded" | "offline";

export interface ApiHealthValue {
  status: ApiHealthStatus;
  /** last successful /health body */
  health: HealthResponse | null;
  /** epoch ms of the last check (client clock) */
  checkedAt: number | null;
  error: string | null;
  /** check again now */
  refresh: () => void;
}

const HEALTH_PATH = "/health";
const ApiHealthContext = React.createContext<ApiHealthValue | null>(null);

function classify(h: HealthResponse | null | undefined): ApiHealthStatus {
  if (!h || h.ok !== true) return "degraded";
  // A key that is present but failed its startup check means the LLM silently fell back to mocks.
  if (h.llm?.key_present && h.llm.key_ok === false) return "degraded";
  return "online";
}

export interface ApiHealthProviderProps {
  children: React.ReactNode;
  /** poll interval (default 15 s); paused while the tab is hidden */
  intervalMs?: number;
}

/** Polls GET {API}/health and shares the result (ApiStatus, pages that need "API offline"). */
export function ApiHealthProvider({ children, intervalMs = 15_000 }: ApiHealthProviderProps) {
  const [snapshot, setSnapshot] = React.useState<Omit<ApiHealthValue, "refresh">>({
    status: "checking",
    health: null,
    checkedAt: null,
    error: null,
  });
  const [nonce, setNonce] = React.useState(0);

  React.useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let inflight: AbortController | null = null;

    const check = async () => {
      inflight?.abort();
      const controller = new AbortController();
      inflight = controller;
      try {
        const health = await getJSON<HealthResponse>(HEALTH_PATH, { timeoutMs: 5_000, signal: controller.signal });
        if (cancelled) return;
        setSnapshot({ status: classify(health), health, checkedAt: Date.now(), error: null });
      } catch (err) {
        if (cancelled || isAbortError(err)) return;
        const status: ApiHealthStatus = isApiError(err) && err.kind === "http" ? "degraded" : "offline";
        const message = err instanceof Error ? err.message : "Health check failed";
        setSnapshot((prev) => ({ status, health: prev.health, checkedAt: Date.now(), error: message }));
      } finally {
        if (inflight === controller) inflight = null;
      }
    };

    const loop = () => {
      timer = setTimeout(async () => {
        if (document.visibilityState === "visible") await check();
        if (!cancelled) loop();
      }, intervalMs);
    };

    const onVisible = () => {
      if (document.visibilityState === "visible") void check();
    };

    void check().then(() => {
      if (!cancelled) loop();
    });
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      cancelled = true;
      if (timer !== undefined) clearTimeout(timer);
      inflight?.abort();
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [intervalMs, nonce]);

  const refresh = React.useCallback(() => setNonce((n) => n + 1), []);
  const value = React.useMemo(() => ({ ...snapshot, refresh }), [snapshot, refresh]);
  return <ApiHealthContext.Provider value={value}>{children}</ApiHealthContext.Provider>;
}

const NO_PROVIDER: ApiHealthValue = {
  status: "checking",
  health: null,
  checkedAt: null,
  error: null,
  refresh: () => undefined,
};

/** Shared API health. `status === "offline"` means pages should show "API offline". */
export function useApiHealth(): ApiHealthValue {
  return React.useContext(ApiHealthContext) ?? NO_PROVIDER;
}

const WORD: Record<ApiHealthStatus, string> = {
  checking: "checking",
  online: "online",
  degraded: "degraded",
  offline: "offline",
};

function llmLine(h: HealthResponse | null): string {
  if (!h?.llm) return "LLM: unknown";
  const { mode, model, key_present, key_ok } = h.llm;
  if (h.demo_mode) return "LLM: demo mode, cached responses (misses use deterministic mocks)";
  if (mode === "mock") return key_present && key_ok === false ? "LLM: mock (API key failed its check)" : "LLM: mock (deterministic, works offline)";
  return `LLM: ${mode}${model ? ` · ${model}` : ""}`;
}

export interface ApiStatusProps {
  className?: string;
  /** show the status word next to the dot (default: only on wide screens) */
  showLabel?: boolean;
}

/** Nav dot: online (filled) / degraded (half) / offline (hollow ring), with LLM mode in the tooltip. */
export function ApiStatus({ className, showLabel }: ApiStatusProps) {
  const { status, health, checkedAt, refresh } = useApiHealth();
  const spoken = `API ${WORD[status]}. ${status === "offline" ? "Pages will show API offline." : llmLine(health)}`;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={refresh}
          aria-label={`${spoken} Press to check again.`}
          className={cn(
            "inline-flex h-8 items-center gap-2 rounded-md px-2 text-ink-muted transition-colors hover:bg-muted hover:text-ink",
            className,
          )}
        >
          <span
            aria-hidden="true"
            className={cn(
              "relative inline-flex size-2.5 shrink-0 rounded-full border",
              status === "online" && "border-success bg-success",
              status === "degraded" && "border-warning bg-[linear-gradient(90deg,var(--warning)_50%,transparent_50%)]",
              status === "offline" && "border-danger bg-transparent",
              status === "checking" && "animate-pulse border-dashed border-ink-faint",
            )}
          />
          <span className="label-mono">API</span>
          <span className={cn("label-mono", showLabel === undefined ? "hidden 2xl:inline" : showLabel ? "inline" : "hidden")}>
            {WORD[status]}
          </span>
        </button>
      </TooltipTrigger>
      <TooltipContent side="bottom" sideOffset={6} className="max-w-80 flex-col items-start gap-1 text-left">
        <span className="font-mono text-[10px] tracking-[0.12em] uppercase">API {WORD[status]}</span>
        <span>{API_URL}</span>
        <span>{status === "offline" ? "Not reachable. Start it on port 8000; pages degrade gracefully." : llmLine(health)}</span>
        {checkedAt ? <span className="opacity-85">Last check {new Date(checkedAt).toLocaleTimeString()}</span> : null}
      </TooltipContent>
    </Tooltip>
  );
}
