"use client";

import * as React from "react";
import { Lock } from "lucide-react";
import { RequireAccount } from "@/components/auth/require-account";
import { MonoLabel } from "@/components/foothold/mono-label";
import { getJSON, isAbortError, isApiError, isOfflineError } from "@/lib/api";
import type { AccountKind } from "@/lib/auth";
import { cn } from "@/lib/utils";
import type { BlindCard, RequestStatus } from "./types";

/* ------------------------------------------------------------------ */
/* Errors + polling                                                    */
/* ------------------------------------------------------------------ */

export function errorText(err: unknown): string {
  if (isOfflineError(err)) return "API offline: start the API on port 8000 and try again.";
  if (isApiError(err)) return err.detail;
  return err instanceof Error ? err.message : "Something went wrong.";
}

export interface PollResult<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

/** GET `path` now and every `intervalMs` while the tab is visible. `path = null` pauses. */
export function usePolling<T>(path: string | null, intervalMs = 4000): PollResult<T> {
  const [res, setRes] = React.useState<{ path: string | null; data: T | null; error: string | null }>({ path: null, data: null, error: null });
  const pathRef = React.useRef(path);
  React.useLayoutEffect(() => {
    pathRef.current = path;
  }, [path]);

  const refresh = React.useCallback(async () => {
    const p = pathRef.current;
    if (!p) return;
    try {
      const next = await getJSON<T>(p, { timeoutMs: 12_000 });
      if (pathRef.current === p) setRes({ path: p, data: next, error: null });
    } catch (err) {
      if (!isAbortError(err) && pathRef.current === p) setRes((r) => ({ path: p, data: r.data, error: errorText(err) }));
    }
  }, []);

  React.useEffect(() => {
    if (!path) return;
    void refresh();
    if (!intervalMs) return;
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, intervalMs);
    return () => window.clearInterval(id);
  }, [path, intervalMs, refresh]);

  return { data: res.data, error: res.error, loading: path !== null && res.path !== path, refresh };
}

/* ------------------------------------------------------------------ */
/* Account gate (the shared RequireAccount guard)                      */
/* ------------------------------------------------------------------ */

export function AccountGate({ kind, children }: { kind: AccountKind; children: React.ReactNode }) {
  return <RequireAccount kind={kind}>{() => children}</RequireAccount>;
}

/* ------------------------------------------------------------------ */
/* Small presentational parts                                          */
/* ------------------------------------------------------------------ */

export function Panel({
  id,
  label,
  title,
  aside,
  children,
  className,
}: {
  id?: string;
  label: string;
  title: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  const headingId = id ? `${id}-h` : undefined;
  return (
    <section id={id} aria-labelledby={headingId} className={cn("scroll-mt-24 border border-line bg-surface", className)}>
      <header className="flex flex-wrap items-end justify-between gap-3 border-b border-line px-4 py-3 sm:px-5">
        <div className="grid gap-1">
          <MonoLabel>{label}</MonoLabel>
          <h2 id={headingId} className="text-lg font-semibold tracking-tight text-ink">
            {title}
          </h2>
        </div>
        {aside ? <div className="flex flex-wrap items-center gap-2">{aside}</div> : null}
      </header>
      <div className="p-4 sm:p-5">{children}</div>
    </section>
  );
}

export function Chip({ children, tone = "plain", title }: { children: React.ReactNode; tone?: "plain" | "accent" | "muted" | "warning"; title?: string }) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1 border px-2 py-0.5 text-xs leading-5",
        tone === "plain" && "border-line-strong text-ink",
        tone === "accent" && "border-accent/60 bg-accent-wash text-ink",
        tone === "muted" && "border-dashed border-line-strong text-ink-muted",
        tone === "warning" && "border-warning/60 text-warning",
      )}
    >
      {children}
    </span>
  );
}

const STATUS_TONE: Record<RequestStatus, string> = {
  pending: "border-warning/60 text-warning",
  accepted: "border-success/60 text-success",
  declined: "border-line-strong text-ink-muted",
};

export function StatusPill({ status }: { status: RequestStatus }) {
  return <span className={cn("label-mono inline-flex h-6 items-center border px-2", STATUS_TONE[status])}>{status}</span>;
}

export function ErrorNote({ children }: { children: React.ReactNode }) {
  return (
    <p role="alert" className="border border-danger/50 px-3 py-2 text-sm text-danger">
      {children}
    </p>
  );
}

export function EmptyNote({ children }: { children: React.ReactNode }) {
  return <p className="border border-dashed border-line-strong px-4 py-6 text-sm text-ink-muted">{children}</p>;
}

export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export function pct(v: number | null | undefined, digits = 0): string {
  return typeof v === "number" ? `${(v * 100).toFixed(digits)}%` : "n/a";
}

export const inputClass =
  "w-full border border-line-strong bg-bg px-3 py-2 text-sm text-ink placeholder:text-ink-faint " +
  "focus-visible:border-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

export const primaryButtonClass =
  "inline-flex h-10 items-center justify-center gap-2 bg-ink px-4 text-sm font-medium text-bg transition-colors hover:bg-ink/90 " +
  "disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent";

export const secondaryButtonClass =
  "inline-flex h-10 items-center justify-center gap-2 border border-line-strong px-4 text-sm text-ink transition-colors hover:bg-surface-2 " +
  "disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent";

/** The blind fields of a talent card (skills, sim bands, pathway progress, availability, region) + locked fields. */
export function BlindFields({ card, matched, showLocked = true }: { card: BlindCard; matched?: string[]; showLocked?: boolean }) {
  const hit = new Set(matched ?? []);
  const p = card.pathway_progress;
  const a = card.availability;
  const r = card.region;
  return (
    <dl className="grid gap-3 text-sm">
      <div className="grid gap-1.5">
        <dt><MonoLabel>Demonstrated skills</MonoLabel></dt>
        <dd className="flex flex-wrap gap-1.5">
          {card.demonstrated_skills.length ? (
            card.demonstrated_skills.map((s) => (
              <Chip key={s.id} tone={hit.has(s.id) ? "accent" : "plain"} title={s.evidence ? `Evidence: ${s.evidence}` : undefined}>
                {s.name}
                {hit.has(s.id) ? <span className="sr-only"> (matches posting)</span> : null}
              </Chip>
            ))
          ) : (
            <span className="text-ink-muted">None recorded yet</span>
          )}
        </dd>
      </div>
      {card.sim_bands.length ? (
        <div className="grid gap-1.5">
          <dt><MonoLabel>Sim bands</MonoLabel></dt>
          <dd className="flex flex-wrap gap-1.5">
            {card.sim_bands.map((b, i) => (
              <Chip key={`${b.career_id ?? "x"}-${i}`} tone="muted">
                {b.metric ? `${b.metric.replace(/_/g, " ")}: ` : b.career_title ? `${b.career_title}: ` : ""}
                <span className="font-medium text-ink">{b.band}</span>
              </Chip>
            ))}
          </dd>
        </div>
      ) : null}
      <div className="grid gap-x-4 gap-y-2 sm:grid-cols-3">
        <div>
          <dt><MonoLabel>Pathway</MonoLabel></dt>
          <dd className="text-ink">
            {p ? (
              <>
                {p.career_title ?? card.target_career?.title ?? p.label ?? "In progress"}
                {typeof p.pct === "number" ? <span className="text-ink-muted"> · {pct(p.pct)}</span> : null}
                {typeof p.pct === "number" ? (
                  <span aria-hidden="true" className="mt-1 block h-1 w-full bg-line">
                    <span className="block h-full bg-accent" style={{ width: `${Math.min(100, Math.max(0, p.pct * 100))}%` }} />
                  </span>
                ) : null}
              </>
            ) : (
              <span className="text-ink-muted">Not started</span>
            )}
          </dd>
        </div>
        <div>
          <dt><MonoLabel>Availability</MonoLabel></dt>
          <dd className="text-ink">
            {a ? (
              [a.hours_per_week ? `${a.hours_per_week} h/wk` : null, a.shifts.join(", ") || null, a.label && !a.hours_per_week ? a.label : null]
                .filter(Boolean)
                .join(" · ") || "Flexible"
            ) : (
              <span className="text-ink-muted">Not shared</span>
            )}
          </dd>
        </div>
        <div>
          <dt><MonoLabel>Region</MonoLabel></dt>
          <dd className="text-ink">
            {r ? [r.label, r.commute_minutes ? `${r.commute_minutes} min commute` : null].filter(Boolean).join(" · ") : <span className="text-ink-muted">Not shared</span>}
          </dd>
        </div>
      </div>
      {showLocked && card.hidden.length ? (
        <div className="flex flex-wrap items-center gap-1.5 border-t border-dashed border-line pt-2">
          <dt className="sr-only">Hidden until the candidate accepts</dt>
          <dd className="flex flex-wrap items-center gap-1.5 text-xs text-ink-faint">
            <Lock aria-hidden="true" className="size-3.5" />
            {card.hidden.map((h) => (
              <span key={h} className="border border-dashed border-line px-1.5 py-0.5">
                {h.replace("_", " ")}
              </span>
            ))}
            <span className="self-center">hidden until they accept</span>
          </dd>
        </div>
      ) : null}
    </dl>
  );
}
