"use client";

import * as React from "react";
import { MonoLabel } from "@/components/foothold/mono-label";
import { getJSON, resolveApiBaseInfo, type ApiBaseInfo } from "@/lib/api";
import { errorMessage } from "@/components/sim/use-tapped-trace";

interface Health {
  ok: boolean;
  llm?: { mode?: string; model?: string | null; key_ok?: boolean };
  demo_mode?: boolean;
  route_errors?: Record<string, string>;
  routes?: string[];
  db?: { backend?: string; reason?: string };
}

const METRIC_KEYS = ["career_fit", "selector", "planner", "recommender", "verifier"];

function Row({ label, ok, value }: { label: string; ok: boolean | null; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line py-2">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="flex items-center gap-2 text-right font-mono text-sm text-ink">
        {value}
        <span aria-hidden="true" className={ok === null ? "text-ink-faint" : ok ? "text-success" : "text-danger"}>
          {ok === null ? "·" : ok ? "✓" : "✕"}
        </span>
        <span className="sr-only">{ok === null ? "unknown" : ok ? "ok" : "problem"}</span>
      </dd>
    </div>
  );
}

/** Live pre-flight checks for the presenter: GET /health and GET /api/metrics, refreshed every 10 s. */
export function DemoChecks() {
  const [health, setHealth] = React.useState<Health | null>(null);
  const [metrics, setMetrics] = React.useState<Record<string, unknown> | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [at, setAt] = React.useState<string>("");
  const [base, setBase] = React.useState<ApiBaseInfo | null>(null);

  React.useEffect(() => {
    let live = true;
    void resolveApiBaseInfo().then((b) => {
      if (live) setBase(b);
    });
    return () => {
      live = false;
    };
  }, []);

  React.useEffect(() => {
    let live = true;
    const load = async () => {
      try {
        const [h, m] = await Promise.all([getJSON<Health>("/health", { auth: false }), getJSON<Record<string, unknown>>("/api/metrics", { auth: false })]);
        if (!live) return;
        setHealth(h);
        setMetrics(m);
        setError(null);
      } catch (e) {
        if (live) setError(errorMessage(e));
      }
      if (live) setAt(new Date().toLocaleTimeString("en-US", { hour12: false }));
    };
    void load();
    const t = setInterval(load, 10_000);
    return () => {
      live = false;
      clearInterval(t);
    };
  }, []);

  const routeErrors = Object.entries(health?.route_errors ?? {});
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <MonoLabel as="h2" tone="ink">
          Live checks
        </MonoLabel>
        <MonoLabel>{at ? `checked ${at}` : "checking…"}</MonoLabel>
      </div>
      {error ? (
        <p role="alert" className="mb-2 text-danger">
          {error}
        </p>
      ) : null}
      <dl>
        <Row
          label="API base"
          ok={health ? health.ok : error ? false : null}
          value={base ? `${base.url.replace(/^https?:\/\//, "")} · via ${base.source}` : "resolving…"}
        />
        <Row
          label="LLM"
          ok={health ? health.llm?.mode === "openai" || !!health.demo_mode : null}
          value={health ? `${health.llm?.mode ?? "?"}${health.llm?.model ? ` · ${health.llm.model}` : ""}` : "–"}
        />
        <Row label="Demo mode (cached LLM)" ok={health ? true : null} value={health ? (health.demo_mode ? "on" : "off") : "–"} />
        <Row label="Database" ok={health ? true : null} value={health?.db?.backend ?? "–"} />
        <Row label="Route errors" ok={health ? routeErrors.length === 0 : null} value={health ? (routeErrors.length ? routeErrors.map(([k]) => k).join(", ") : "none") : "–"} />
        {METRIC_KEYS.map((k) => (
          <Row key={k} label={`metrics.${k}`} ok={metrics ? k in metrics : null} value={metrics ? (k in metrics ? "present" : "missing") : "–"} />
        ))}
      </dl>
      {routeErrors.length ? (
        <ul className="mt-2 space-y-1 text-sm text-danger">
          {routeErrors.map(([k, v]) => (
            <li key={k}>
              {k}: {v}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
