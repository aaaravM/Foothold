"use client";

/**
 * "Live in your area": streams POST /api/research/stream (Tavily web search -> ranked
 * sources -> cited summary) for one career + the viewer's place, and shows a live status
 * line while it runs, then 3-5 source cards and a 2-3 sentence summary with numbered refs.
 * Web results are untrusted: rendered as text only, links open in a new tab.
 */
import * as React from "react";
import { motion, useReducedMotion } from "motion/react";
import { ExternalLink, RotateCw } from "lucide-react";
import { TracePanel, useTrace } from "@/components/foothold";
import { EASE, QuietLabel } from "@/components/sim/fx";
import { cn } from "@/lib/utils";

interface Source {
  n: number;
  title: string;
  url: string;
  snippet?: string;
  source_domain?: string;
}
interface Claim {
  text: string;
  sources: number[];
}
interface Report {
  title?: string;
  place?: string | null;
  sources?: Source[];
  results?: Source[];
  summary?: string;
  claims?: Claim[];
}

export interface LiveInYourAreaProps {
  careerId?: string | null;
  /** free-text career title when there is no career_id */
  title?: string | null;
  placeId?: string | null;
  className?: string;
}

const MAX_CARDS = 5;

function safeUrl(url: unknown): string | null {
  if (typeof url !== "string") return null;
  try {
    const u = new URL(url);
    return u.protocol === "https:" || u.protocol === "http:" ? u.href : null;
  } catch {
    return null;
  }
}

function domainOf(s: Source): string {
  if (s.source_domain) return s.source_domain;
  try {
    return new URL(s.url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

function asSources(v: unknown): Source[] {
  if (!Array.isArray(v)) return [];
  return v.filter((s): s is Source => !!s && typeof s === "object" && typeof (s as Source).n === "number" && !!safeUrl((s as Source).url));
}

function asClaims(v: unknown): Claim[] {
  if (!Array.isArray(v)) return [];
  return v.filter((c): c is Claim => !!c && typeof c === "object" && typeof (c as Claim).text === "string" && Array.isArray((c as Claim).sources));
}

export function LiveInYourArea({ careerId, title, placeId, className }: LiveInYourAreaProps) {
  const trace = useTrace();
  const { run, reset } = trace;
  const reduce = useReducedMotion();
  const [nonce, setNonce] = React.useState(0);
  const hasSubject = !!(careerId || (title && title.trim()));

  React.useEffect(() => {
    if (!hasSubject) return;
    const ctrl = new AbortController();
    reset();
    const body: Record<string, string> = {};
    if (careerId) body.career_id = careerId;
    else if (title) body.title = title.trim();
    if (placeId) body.place_id = placeId;
    void run("/api/research/stream", body, ctrl.signal, { idleTimeoutMs: 60_000 });
    return () => ctrl.abort();
  }, [careerId, title, placeId, nonce, hasSubject, run, reset]);

  const { state } = trace;
  const report = (state.status === "done" && state.result && typeof state.result === "object" ? state.result : null) as Report | null;
  const sources = asSources(report?.sources ?? report?.results ?? state.data.sources).slice(0, MAX_CARDS);
  const claims = asClaims(report?.claims ?? state.data.claims);
  const byN = new Map(sources.map((s) => [s.n, s]));
  const place = report?.place ?? null;
  const live = state.status === "connecting" || state.status === "running";

  // Live status line: the active node, else the latest node summary.
  const active = state.nodes.filter((n) => state.nodeState[n.id]?.status === "active");
  const searching = active.filter((n) => n.id.startsWith("search:"));
  let status = "Starting live search…";
  if (searching.length > 0) {
    const q = searching[0].label.replace(/^Search:\s*/, "");
    status = `Searching the web: “${q}”${searching.length > 1 ? ` +${searching.length - 1}` : ""}`;
  } else if (active.length > 0) {
    status = active[0].id === "summarize" ? `Reading ${sources.length || "the"} sources` : active[0].label;
  } else if (state.lastSummary) {
    status = state.lastSummary;
  }

  if (!hasSubject) return null;

  return (
    <section aria-label="Live in your area" className={cn("space-y-3", className)}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="font-display text-xl text-ink">Live in your area</h2>
        {place ? <QuietLabel>{place}</QuietLabel> : null}
        {!live ? (
          <button
            type="button"
            onClick={() => setNonce((n) => n + 1)}
            className="ml-auto inline-flex items-center gap-1.5 text-[13px] text-ink-muted transition-colors hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
          >
            <RotateCw aria-hidden="true" className="size-3.5" />
            Refresh
          </button>
        ) : null}
      </div>

      {live ? (
        <p className="flex items-center gap-2 text-[13px] text-ink-muted" aria-live="polite">
          <span aria-hidden="true" className="relative inline-flex size-2">
            <span className={cn("absolute inline-flex size-full rounded-full bg-accent opacity-60", !reduce && "animate-ping")} />
            <span className="relative inline-flex size-2 rounded-full bg-accent" />
          </span>
          <span className="truncate">{status}</span>
        </p>
      ) : null}

      {state.status === "error" ? <QuietLabel as="p">Live search is unavailable right now.</QuietLabel> : null}
      {state.status === "done" && sources.length === 0 ? <QuietLabel as="p">No live results found.</QuietLabel> : null}

      {claims.length > 0 ? (
        <p className="max-w-3xl text-[15px] leading-6 text-ink">
          {claims.map((c, i) => (
            <React.Fragment key={i}>
              {c.text}
              {c.sources
                .filter((n) => byN.has(n))
                .map((n) => (
                  <a
                    key={n}
                    href={safeUrl(byN.get(n)?.url) ?? undefined}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={`Source ${n}`}
                    className="ml-0.5 align-super text-[11px] text-accent hover:underline"
                  >
                    [{n}]
                  </a>
                ))}
              {i < claims.length - 1 ? " " : ""}
            </React.Fragment>
          ))}
        </p>
      ) : null}

      {sources.length > 0 ? (
        <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          {sources.map((s, i) => (
            <motion.li
              key={s.url}
              initial={reduce ? { opacity: 0 } : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, ease: EASE, delay: i * 0.06 }}
            >
              <a
                href={safeUrl(s.url) ?? undefined}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex h-full flex-col rounded-2xl border border-line p-3 transition-colors hover:border-line-strong focus-visible:outline-2 focus-visible:outline-accent"
              >
                <span className="flex items-center gap-1.5 text-[12px] text-ink-faint">
                  <span className="text-accent">{s.n}</span>
                  <span className="truncate">{domainOf(s)}</span>
                  <ExternalLink aria-hidden="true" className="ml-auto size-3 shrink-0 opacity-60 group-hover:opacity-100" />
                </span>
                <span className="mt-1 line-clamp-2 text-sm text-ink">{s.title || domainOf(s)}</span>
              </a>
            </motion.li>
          ))}
        </ol>
      ) : null}

      {state.nodes.length > 0 ? <TracePanel nodes={trace.nodes} state={state} defaultOpen={false} /> : null}
    </section>
  );
}
