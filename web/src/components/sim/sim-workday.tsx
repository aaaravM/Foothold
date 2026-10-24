"use client";

import * as React from "react";
import Link from "next/link";
import { Brackets, techButtonClass, drawLinkClass } from "@/components/auth/parts";
import { usePersona } from "@/components/path/use-persona";
import { FictionalTag } from "@/components/foothold/fictional-tag";
import { NotTrainedYet } from "@/components/foothold/metric-value";
import { MonoLabel } from "@/components/foothold/mono-label";
import { ProvenanceBadge } from "@/components/foothold/provenance-badge";
import { SourceLink } from "@/components/foothold/source-link";
import { StatBar, type StatTone } from "@/components/foothold/stat-bar";
import { TracePanel } from "@/components/foothold/trace-panel";
import { TraitRadar } from "@/components/foothold/trait-radar";
import { getJSON } from "@/lib/api";
import type { Account } from "@/lib/auth";
import type { Provenance, TraceEvent } from "@/lib/types";
import { cn } from "@/lib/utils";
import { errorMessage, useTappedTrace } from "./use-tapped-trace";

/* ------------------------------------------------------------------ */
/* API shapes (api/foothold/routes/sim.py + graphs/sim.py)             */
/* ------------------------------------------------------------------ */

interface Coworker {
  id: string;
  name: string;
  role?: string;
  style?: string;
  mood: number;
  mood_label?: string;
}
interface WageLite {
  median_annual?: number | null;
  median_hourly?: number | null;
  area?: string;
  period?: string;
  status?: string;
}
interface CareerRow {
  id: string;
  title: string;
  summary?: string;
  events: number;
  coworkers: Coworker[];
  wage: WageLite | null;
}
interface CareersResponse {
  careers: CareerRow[];
  available: boolean;
  events_per_day: number;
}
interface SimChoiceView {
  choice_id: string;
  text: string;
}
interface InterruptPayload {
  event: { event_id: string; title: string; text: string; clock: string; crunch: boolean; status?: string; choices: SimChoiceView[] };
  index: number;
  total: number;
  clock: string;
  stats: Stats;
  coworkers: Coworker[];
  career_id: string | null;
  mode?: string;
  error?: string;
}
type Stats = { safety: number; output: number; team_trust: number; stress: number };
interface Reaction {
  event_id: string;
  coworker_id: string;
  name: string;
  reaction: string;
  mood_delta: number;
  line: string;
  llm?: string;
}
interface HistoryEntry {
  event_id: string;
  title: string;
  clock: string;
  crunch: boolean;
  choice_text?: string;
  stat_deltas: Partial<Stats>;
}
interface SourceRef {
  id?: string;
  title?: string;
  url?: string;
}
interface FactBlock {
  status?: string;
  source?: SourceRef | null;
  [k: string]: unknown;
}
interface CareerFacts {
  career_id: string;
  title?: string;
  wage: (FactBlock & { median_annual?: number | null; median_hourly?: number | null; area?: string; period?: string }) | null;
  outlook: (FactBlock & { growth_pct?: number | null; annual_openings?: number | null; period?: string }) | null;
}
interface Report {
  mode?: string;
  career_id: string | null;
  stats: Stats;
  traits: { id: string; name: string; group?: string; value: number }[];
  trait_method?: string;
  top_careers: { rank: number; career_id: string; title: string; probability: number; p_overall?: number | null; probability_basis?: string | null }[];
  /** what `probability` is a share of, e.g. "share among the 8 Foothold careers" */
  probability_basis?: string | null;
  model: {
    probability_basis?: string | null;
    source: string;
    name?: string | null;
    trained: boolean;
    note?: string | null;
    metrics?: { careers8?: { mlp?: { top3?: number } }; status?: string } | null;
  };
  careers: Record<string, CareerFacts>;
  history: HistoryEntry[];
  events_played: number;
  summary?: { text: string; source?: string };
}

const STAT_META: { id: keyof Stats; label: string; tone: StatTone; invert?: boolean }[] = [
  { id: "safety", label: "Safety", tone: "success" },
  { id: "output", label: "Output", tone: "info" },
  { id: "team_trust", label: "Team trust", tone: "accent" },
  { id: "stress", label: "Stress", tone: "danger", invert: true },
];

const DAY_START = 7 * 60;
const DAY_END = 17 * 60;

function toMin(clock: string | undefined): number | null {
  if (!clock) return null;
  const m = /^(\d{1,2}):(\d{2})/.exec(clock);
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

function prov(status: unknown): Provenance {
  const s = String(status ?? "").split(" ")[0].toUpperCase();
  return s === "REAL" || s === "SAMPLE" || s === "SYNTHETIC" || s === "FICTIONAL" ? (s as Provenance) : "SAMPLE";
}

const usd = (n: number) => `$${Math.round(n).toLocaleString("en-US")}`;
/** 0.4213 -> "42%", 0.0123 -> "1.2%", 0.0004 -> "<0.1%" */
const fmtPct = (p: number) => {
  const v = p * 100;
  if (v >= 10) return `${v.toFixed(0)}%`;
  if (v >= 0.1) return `${v.toFixed(1)}%`;
  return "<0.1%";
};

const REACTION_TONE: Record<string, string> = {
  approves: "text-success",
  relieved: "text-success",
  neutral: "text-ink-muted",
  uneasy: "text-warning",
  frustrated: "text-danger",
};

/* ------------------------------------------------------------------ */
/* Pieces                                                              */
/* ------------------------------------------------------------------ */

function DayTimeline({ history, current }: { history: HistoryEntry[]; current?: string }) {
  const pct = (clock: string | undefined) => {
    const m = toMin(clock);
    if (m === null) return null;
    return Math.min(100, Math.max(0, ((m - DAY_START) / (DAY_END - DAY_START)) * 100));
  };
  const cur = pct(current);
  return (
    <div className="space-y-2">
      <div className="flex justify-between">
        <MonoLabel>07:00</MonoLabel>
        <MonoLabel>12:00</MonoLabel>
        <MonoLabel>17:00</MonoLabel>
      </div>
      <div className="relative h-6" role="img" aria-label={`Workday timeline: ${history.length} events done${current ? `, now ${current}` : ""}`}>
        <div className="absolute inset-x-0 top-1/2 h-px bg-line-strong" />
        {Array.from({ length: 11 }, (_, i) => (
          <span key={i} className="absolute top-1/2 h-2 w-px -translate-y-1/2 bg-line-strong" style={{ left: `${i * 10}%` }} />
        ))}
        {cur !== null ? <div className="absolute top-1/2 left-0 h-0.5 -translate-y-1/2 bg-accent" style={{ width: `${cur}%` }} /> : null}
        {history.map((h) => {
          const p = pct(h.clock);
          return p === null ? null : (
            <span
              key={`${h.event_id}-${h.clock}`}
              title={`${h.clock} ${h.title}`}
              className={cn("absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 border", h.crunch ? "border-danger bg-danger" : "border-ink bg-ink")}
              style={{ left: `${p}%` }}
            />
          );
        })}
        {cur !== null ? (
          <span className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-accent bg-bg" style={{ left: `${cur}%` }} />
        ) : null}
      </div>
    </div>
  );
}

function StatsBlock({ stats, deltas }: { stats: Stats; deltas?: Partial<Stats> }) {
  return (
    <div className="space-y-3">
      {STAT_META.map((s) => (
        <StatBar key={s.id} label={s.label} value={stats[s.id] ?? 0} max={100} tone={s.tone} delta={deltas?.[s.id] ?? null} invertDelta={s.invert} />
      ))}
    </div>
  );
}

function CoworkerCard({ cw, reaction }: { cw: Coworker; reaction?: Reaction }) {
  return (
    <div className="border border-line p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm text-ink">{cw.name}</p>
          <p className="truncate text-xs text-ink-muted">{cw.role}</p>
        </div>
        <FictionalTag compact />
      </div>
      {reaction ? (
        <div className="mt-3 space-y-1">
          <p className="text-sm text-ink">&ldquo;{reaction.line}&rdquo;</p>
          <MonoLabel as="p" className={REACTION_TONE[reaction.reaction] ?? "text-ink-muted"}>
            {reaction.reaction} · mood {reaction.mood_delta >= 0 ? "+" : ""}
            {reaction.mood_delta}
          </MonoLabel>
        </div>
      ) : (
        <MonoLabel as="p" className="mt-3">
          mood {cw.mood} · {cw.mood_label ?? ""}
        </MonoLabel>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main                                                                */
/* ------------------------------------------------------------------ */

type Phase = "pick" | "play" | "done";

export function SimWorkday({ account }: { account: Account }) {
  const persona = usePersona(account.persona_id);
  const [careers, setCareers] = React.useState<CareersResponse | null>(null);
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [phase, setPhase] = React.useState<Phase>("pick");
  const [pending, setPending] = React.useState<InterruptPayload | null>(null);
  const [lastEvent, setLastEvent] = React.useState<InterruptPayload | null>(null);
  const [chosen, setChosen] = React.useState<SimChoiceView | null>(null);
  const [reactions, setReactions] = React.useState<Reaction[]>([]);
  const [history, setHistory] = React.useState<HistoryEntry[]>([]);
  const [stats, setStats] = React.useState<Stats | null>(null);
  const [lastDeltas, setLastDeltas] = React.useState<Partial<Stats> | undefined>(undefined);
  const [report, setReport] = React.useState<Report | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const onTap = React.useCallback((ev: TraceEvent) => {
    if (ev.type === "state") {
      const d = ev.data as { reactions?: Reaction[]; stats?: Stats; last?: HistoryEntry | null };
      if (Array.isArray(d.reactions)) {
        setReactions((prev) => {
          const next = [...prev];
          for (const r of d.reactions ?? []) {
            if (!next.some((x) => x.coworker_id === r.coworker_id && x.event_id === r.event_id)) next.push(r);
          }
          return next;
        });
      }
      if (d.stats) setStats(d.stats);
      if (d.last) {
        const last = d.last;
        setLastDeltas(last.stat_deltas);
        setHistory((h) => (h.some((x) => x.event_id === last.event_id && x.clock === last.clock) ? h : [...h, last]));
      }
    } else if (ev.type === "interrupt") {
      const p = ev.payload as InterruptPayload;
      setPending(p);
      if (p?.stats) setStats(p.stats);
    } else if (ev.type === "done") {
      const r = (ev.result as { report?: Report })?.report ?? null;
      setReport(r);
      setPending(null);
      setPhase("done");
    } else if (ev.type === "error") {
      setError(ev.message);
    }
  }, []);

  const { trace, run } = useTappedTrace(onTap);
  const threadId = trace.state.threadId;

  React.useEffect(() => {
    let live = true;
    getJSON<CareersResponse>("/api/sim/careers")
      .then((r) => live && setCareers(r))
      .catch((e) => live && setLoadError(errorMessage(e)));
    return () => {
      live = false;
    };
  }, []);

  const start = React.useCallback(
    async (careerId: string | null) => {
      setPhase("play");
      setPending(null);
      setLastEvent(null);
      setChosen(null);
      setReactions([]);
      setHistory([]);
      setStats(null);
      setLastDeltas(undefined);
      setReport(null);
      setError(null);
      trace.reset();
      setBusy(true);
      await run("/api/sim/start", { career_id: careerId });
      setBusy(false);
    },
    [run, trace],
  );

  const choose = React.useCallback(
    async (choice: SimChoiceView) => {
      if (!threadId || !pending || busy) return;
      setLastEvent(pending);
      setChosen(choice);
      setPending(null);
      setReactions([]);
      setError(null);
      setBusy(true);
      await run(`/api/sim/${threadId}/choose`, { choice_id: choice.choice_id });
      setBusy(false);
    },
    [threadId, pending, busy, run],
  );

  const resume = React.useCallback(async () => {
    if (!threadId) return;
    setError(null);
    setBusy(true);
    try {
      const st = await getJSON<{ status: string; interrupt: InterruptPayload | null; report: Report | null }>(`/api/sim/${threadId}/state`);
      if (st.status === "waiting" && st.interrupt) setPending(st.interrupt);
      else if (st.status === "done" && st.report) {
        setReport(st.report);
        setPhase("done");
      } else if (st.status === "stalled") {
        await run(`/api/sim/${threadId}/continue`, {});
      } else setError("The workday is still running. Try again in a moment.");
    } catch (e) {
      setError(errorMessage(e));
    }
    setBusy(false);
  }, [threadId, run]);

  // keys 1/2/3 pick a choice
  React.useEffect(() => {
    if (!pending || busy) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const i = ["1", "2", "3"].indexOf(e.key);
      const c = pending.event.choices[i];
      if (c) {
        e.preventDefault();
        void choose(c);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pending, busy, choose]);

  /* ---------------- pick ---------------- */
  if (phase === "pick") {
    const target = persona?.target_career ?? null;
    const interests = new Set(persona?.interests_careers ?? []);
    return (
      <div className="space-y-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="max-w-2xl">
            <MonoLabel as="p" tone="accent">
              Step 1 · Pick a workday
            </MonoLabel>
            <p className="mt-2 text-lg text-ink">
              Spend one shift, 07:00 to 17:00, in a Central Valley job. Five moments, three choices each. Your coworkers react, and the
              sim learns how you work.
            </p>
          </div>
          <button type="button" className={cn(techButtonClass, "shrink-0")} onClick={() => void start(null)} disabled={!careers?.available}>
            <span>Let Foothold choose</span>
            <span aria-hidden="true" className="font-mono text-xs">
              ↵
            </span>
            <Brackets offset={5} />
          </button>
        </div>
        {loadError ? <p className="text-danger" role="alert">{loadError}</p> : null}
        {careers && !careers.available ? (
          <p className="text-warning" role="status">
            Sim events are not loaded on the server yet.
          </p>
        ) : null}
        {!careers && !loadError ? <MonoLabel as="p">Loading careers…</MonoLabel> : null}
        <ul className="grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
          {(careers?.careers ?? []).map((c) => {
            const mark = c.id === target ? "Your goal" : interests.has(c.id) ? "Interest" : null;
            return (
              <li key={c.id} className="bg-bg">
                <button
                  type="button"
                  disabled={c.events === 0}
                  onClick={() => void start(c.id)}
                  className="group/bracket relative flex h-full w-full flex-col gap-3 p-4 text-left hover:bg-surface focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent disabled:opacity-50"
                >
                  <div className="flex items-center justify-between gap-2">
                    <MonoLabel>{c.events} events</MonoLabel>
                    {mark ? <MonoLabel tone="accent">{mark}</MonoLabel> : null}
                  </div>
                  <span className="font-display text-lg leading-snug text-ink">{c.title}</span>
                  {c.summary ? <span className="line-clamp-3 text-sm text-ink-muted">{c.summary}</span> : null}
                  <span className="mt-auto flex flex-wrap items-center gap-2 pt-2">
                    {c.wage?.median_annual ? (
                      <>
                        <span className="font-mono text-sm text-ink tabular-nums">{usd(c.wage.median_annual)}/yr</span>
                        <ProvenanceBadge plain status={prov(c.wage.status)} note={c.wage.area} />
                      </>
                    ) : null}
                  </span>
                  <MonoLabel tone="faint">Median wage · {c.wage?.area ?? "local area"}</MonoLabel>
                  <Brackets />
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    );
  }

  /* ---------------- done ---------------- */
  if (phase === "done" && report) {
    const focusId = report.top_careers[0]?.career_id ?? report.career_id ?? "";
    const trained = report.model.source === "career_fit" && report.model.trained;
    const probabilityBasis =
      report.probability_basis ?? report.model.probability_basis ?? report.top_careers[0]?.probability_basis ?? "share among the Foothold careers";
    return (
      <div className="space-y-10">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <MonoLabel as="p" tone="accent">
              End of day · report
            </MonoLabel>
            <h2 className="mt-2 font-display text-3xl text-ink">Here&apos;s how you worked today.</h2>
          </div>
          <div className="flex flex-wrap gap-4">
            <Link href={`/path?career=${encodeURIComponent(focusId)}`} className={techButtonClass}>
              <span>Plan a route to this career</span>
              <span aria-hidden="true" className="font-mono text-xs">
                →
              </span>
              <Brackets offset={5} />
            </Link>
            <button type="button" className={drawLinkClass} onClick={() => setPhase("pick")}>
              Try another workday
            </button>
          </div>
        </div>

        {report.summary?.text ? (
          <p className="max-w-3xl border-l-2 border-accent pl-4 text-lg text-ink">
            {report.summary.text}
            <MonoLabel as="span" className="ml-2 align-middle">
              {report.summary.source === "openai" ? "LLM" : report.summary.source ?? ""} · numbers verified
            </MonoLabel>
          </p>
        ) : null}

        <div className="grid gap-10 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <TraitRadar traits={report.traits} title="Work styles (21 O*NET traits)" />
            <MonoLabel as="p" className="mt-2">
              Method · {report.trait_method ?? "player model"}
            </MonoLabel>
          </div>
          <div className="space-y-6 lg:col-span-6">
            <div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <MonoLabel as="h3" tone="ink">
                  Top careers for how you worked
                </MonoLabel>
                {trained ? (
                  <span className="flex items-center gap-2">
                    <MonoLabel tone="success">
                      Model · {report.model.name}
                      {typeof report.model.metrics?.careers8?.mlp?.top3 === "number"
                        ? ` · top-3 acc ${report.model.metrics.careers8.mlp.top3.toFixed(2)}`
                        : ""}
                    </MonoLabel>
                    <ProvenanceBadge status="SYNTHETIC" note="Accuracy on synthetic held-out profiles" />
                  </span>
                ) : (
                  <NotTrainedYet hint={report.model.note ?? undefined} />
                )}
              </div>
              <ol className="mt-3 divide-y divide-line border border-line">
                {report.top_careers.map((t) => (
                  <li key={t.career_id} className="flex items-center gap-3 p-3">
                    <MonoLabel tone="faint">{String(t.rank).padStart(2, "0")}</MonoLabel>
                    <span className="min-w-0 flex-1">
                      <span className="block text-ink">{t.title}</span>
                      {typeof t.p_overall === "number" ? (
                        <span className="block text-xs text-ink-muted" title="The model's probability for this occupation before narrowing to Foothold's careers">
                          {fmtPct(t.p_overall)} across all occupations the model knows
                        </span>
                      ) : null}
                    </span>
                    <span
                      className="font-mono text-sm text-ink tabular-nums"
                      title={`${fmtPct(t.probability)}: ${t.probability_basis ?? probabilityBasis}${typeof t.p_overall === "number" ? `; ${fmtPct(t.p_overall)} overall` : ""}`}
                    >
                      {(t.probability * 100).toFixed(0)}%
                    </span>
                    <Link href={`/path?career=${encodeURIComponent(t.career_id)}`} className={drawLinkClass} aria-label={`Plan a route to ${t.title}`}>
                      Plan
                    </Link>
                  </li>
                ))}
              </ol>
              <MonoLabel as="p" className="mt-2">
                % = {probabilityBasis}
              </MonoLabel>
              {!trained && report.model.name ? (
                <MonoLabel as="p" className="mt-2">
                  Ranked by {report.model.name}
                </MonoLabel>
              ) : null}
            </div>

            {report.top_careers.slice(0, 3).map((t) => {
              const f = report.careers[t.career_id];
              if (!f) return null;
              return (
                <div key={t.career_id} className="border-t border-line pt-4">
                  <p className="text-ink">{f.title ?? t.title}</p>
                  <dl className="mt-2 grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <MonoLabel as="dt">Median wage</MonoLabel>
                      <dd className="mt-1 flex flex-wrap items-center gap-2">
                        {typeof f.wage?.median_annual === "number" ? (
                          <span className="font-mono tabular-nums text-ink">{usd(f.wage.median_annual)}/yr</span>
                        ) : (
                          <span className="text-ink-muted">not verified</span>
                        )}
                        {f.wage ? <ProvenanceBadge status={prov(f.wage.status)} href={f.wage.source?.url} note={f.wage.area} /> : null}
                      </dd>
                    </div>
                    <div>
                      <MonoLabel as="dt">Outlook</MonoLabel>
                      <dd className="mt-1 flex flex-wrap items-center gap-2">
                        {typeof f.outlook?.growth_pct === "number" ? (
                          <span className="font-mono tabular-nums text-ink">
                            {f.outlook.growth_pct > 0 ? "+" : ""}
                            {f.outlook.growth_pct}%
                          </span>
                        ) : (
                          <span className="text-ink-muted">not verified</span>
                        )}
                        {typeof f.outlook?.annual_openings === "number" ? (
                          <span className="text-ink-muted">{f.outlook.annual_openings.toLocaleString("en-US")} openings/yr</span>
                        ) : null}
                        {f.outlook ? <ProvenanceBadge status={prov(f.outlook.status)} href={f.outlook.source?.url} note={f.outlook.period} /> : null}
                      </dd>
                    </div>
                  </dl>
                  {f.wage?.source?.url ? (
                    <SourceLink href={f.wage.source.url} label={f.wage.source.title ?? "Source"} className="mt-2" />
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>

        <div className="grid gap-8 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <MonoLabel as="h3" tone="ink" className="mb-3">
              Final stats
            </MonoLabel>
            <StatsBlock stats={report.stats} />
          </div>
          <div className="lg:col-span-7">
            <MonoLabel as="h3" tone="ink" className="mb-3">
              Your day
            </MonoLabel>
            <ol className="space-y-2 text-sm">
              {report.history.map((h) => (
                <li key={`${h.event_id}-${h.clock}`} className="flex gap-3">
                  <span className="font-mono text-ink-muted tabular-nums">{h.clock}</span>
                  <span className="text-ink">
                    {h.title}
                    {h.choice_text ? <span className="text-ink-muted"> · {h.choice_text}</span> : null}
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </div>
        <TracePanel nodes={trace.nodes} state={trace.state} title="Behind the scenes" />
      </div>
    );
  }

  /* ---------------- play ---------------- */
  const shown = pending ?? lastEvent;
  const coworkers = shown?.coworkers ?? [];
  const waitingNext = !pending && busy;
  return (
    <div className="space-y-8">
      <DayTimeline history={history} current={pending?.clock ?? lastEvent?.clock} />

      <div className="grid gap-8 lg:grid-cols-12">
        <div className="space-y-6 lg:col-span-8">
          {error ? (
            <div role="alert" className="flex flex-wrap items-center gap-4 border border-danger p-4 text-danger">
              <span className="flex-1">{error}</span>
              {threadId ? (
                <button type="button" className={drawLinkClass} onClick={() => void resume()}>
                  Resume
                </button>
              ) : null}
              <button type="button" className={drawLinkClass} onClick={() => setPhase("pick")}>
                Back to careers
              </button>
            </div>
          ) : null}

          {!shown && !error ? (
            <MonoLabel as="p" aria-live="polite">
              Setting up your shift…
            </MonoLabel>
          ) : null}

          {pending ? (
            <section aria-labelledby="sim-event-title" className="relative border border-line-strong p-5 sm:p-6">
              <div className="flex flex-wrap items-center gap-3">
                <span className="font-mono text-2xl text-ink tabular-nums">{pending.clock}</span>
                <MonoLabel>
                  Moment {pending.index} of {pending.total}
                </MonoLabel>
                {pending.event.crunch ? <MonoLabel tone="danger">Crunch</MonoLabel> : null}
                <ProvenanceBadge status="SYNTHETIC" note="Draft scenario" className="ml-auto" />
              </div>
              <h2 id="sim-event-title" className="mt-4 font-display text-2xl leading-tight text-ink sm:text-3xl">
                {pending.event.title}
              </h2>
              <p className="mt-3 max-w-2xl text-ink-muted">{pending.event.text}</p>
              {pending.error ? <p className="mt-3 text-danger">{pending.error}</p> : null}
              <ol className="mt-6 space-y-2" aria-label="Your choices (press 1, 2 or 3)">
                {pending.event.choices.map((c, i) => (
                  <li key={c.choice_id}>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void choose(c)}
                      className="group/bracket relative flex w-full items-start gap-4 border border-line p-4 text-left hover:border-line-strong hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-60"
                    >
                      <kbd className="grid size-7 shrink-0 place-items-center border border-line-strong font-mono text-xs text-ink">{i + 1}</kbd>
                      <span className="text-ink">{c.text}</span>
                      <Brackets />
                    </button>
                  </li>
                ))}
              </ol>
            </section>
          ) : null}

          {!pending && lastEvent && chosen ? (
            <section aria-live="polite" className="border border-line p-5 sm:p-6">
              <MonoLabel as="p">
                {lastEvent.clock} · {lastEvent.event.title}
              </MonoLabel>
              <p className="mt-2 text-ink">
                You chose: <span className="text-ink-muted">{chosen.text}</span>
              </p>
              {waitingNext ? (
                <MonoLabel as="p" className="mt-3">
                  Coworkers are reacting…
                </MonoLabel>
              ) : null}
            </section>
          ) : null}

          {coworkers.length > 0 ? (
            <div>
              <div className="mb-3 flex items-center justify-between">
                <MonoLabel as="h3" tone="ink">
                  {pending ? "Your crew" : "Crew reactions"}
                </MonoLabel>
                <FictionalTag />
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                {coworkers.map((cw) => (
                  <CoworkerCard
                    key={cw.id}
                    cw={cw}
                    reaction={reactions.find((r) => r.coworker_id === cw.id && (!lastEvent || r.event_id === lastEvent.event.event_id))}
                  />
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <aside className="space-y-6 lg:col-span-4">
          <div>
            <MonoLabel as="h3" tone="ink" className="mb-3">
              Shift stats
            </MonoLabel>
            {stats ? <StatsBlock stats={stats} deltas={lastDeltas} /> : <MonoLabel as="p">Waiting for the first moment…</MonoLabel>}
          </div>
          {history.length > 0 ? (
            <div>
              <MonoLabel as="h3" tone="ink" className="mb-2">
                So far
              </MonoLabel>
              <ol className="space-y-1 text-sm">
                {history.map((h) => (
                  <li key={`${h.event_id}-${h.clock}`} className="flex gap-2">
                    <span className="font-mono text-ink-muted tabular-nums">{h.clock}</span>
                    <span className="truncate text-ink">{h.title}</span>
                  </li>
                ))}
              </ol>
            </div>
          ) : null}
        </aside>
      </div>

      <TracePanel nodes={trace.nodes} state={trace.state} title="Behind the scenes" defaultOpen />
    </div>
  );
}

