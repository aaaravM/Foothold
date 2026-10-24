"use client";

import * as React from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { usePersona } from "@/components/path/use-persona";
import { NotTrainedYet } from "@/components/foothold/metric-value";
import { type StatTone } from "@/components/foothold/stat-bar";
import { TracePanel } from "@/components/foothold/trace-panel";
import { TraitRadar } from "@/components/foothold/trait-radar";
import { getJSON } from "@/lib/api";
import type { Account } from "@/lib/auth";
import type { TraceEvent } from "@/lib/types";
import { cn } from "@/lib/utils";
import { PickedForYou } from "@/components/path/picked-for-you";
import { CrisisPanel, type CrisisPayload } from "@/components/circle/crisis-panel";
import { LiveInYourArea } from "@/components/research/live-in-your-area";
import { CareerSearch, type CareerHit } from "./career-search";
import { EASE, Kicker, Reveal, ScrambleText, SwapArrow, TiltCard, Tween, ghostPill, primaryPill, staggerChild, staggerParent } from "./fx";
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
  custom_allowed?: boolean;
  occupation?: { title?: string | null; onet_soc?: string | null } | null;
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
  occupation?: { title?: string | null; onet_soc?: string | null } | null;
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

const STAT_BAR: Record<StatTone, string> = {
  success: "bg-success",
  info: "bg-info",
  accent: "bg-accent",
  danger: "bg-danger",
  warning: "bg-warning",
  ink: "bg-ink",
};

function StatsRow({ stats, deltas }: { stats: Stats; deltas?: Partial<Stats> }) {
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
      {STAT_META.map((s) => {
        const v = Math.max(0, Math.min(100, stats[s.id] ?? 0));
        const d = deltas?.[s.id] ?? 0;
        const good = s.invert ? d < 0 : d > 0;
        return (
          <div key={s.id}>
            <dt className="text-xs text-ink-faint">{s.label}</dt>
            <dd className="mt-1 flex items-baseline gap-2">
              <Tween value={v} className="font-mono text-lg text-ink" />
              <AnimatePresence mode="popLayout">
                {d ? (
                  <motion.span
                    key={`${s.id}-${d}-${v}`}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.5, ease: EASE }}
                    className={cn("font-mono text-xs tabular-nums", good ? "text-success" : "text-danger")}
                  >
                    {d > 0 ? "+" : ""}
                    {d}
                  </motion.span>
                ) : null}
              </AnimatePresence>
            </dd>
            <div className="mt-2 h-1 overflow-hidden rounded-full bg-line">
              <motion.div
                className={cn("h-full origin-left rounded-full", STAT_BAR[s.tone] ?? "bg-ink")}
                initial={{ scaleX: 0 }}
                animate={{ scaleX: v / 100 }}
                transition={{ duration: 0.9, ease: EASE }}
              />
            </div>
          </div>
        );
      })}
    </dl>
  );
}

function initialsOf(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");
}

function Avatar({ name, tone, small }: { name: string; tone?: string; small?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "grid shrink-0 place-items-center rounded-full border border-line-strong bg-surface font-mono text-ink",
        small ? "size-7 text-[10px]" : "size-9 text-xs",
        tone,
      )}
    >
      {initialsOf(name)}
    </span>
  );
}

function TypingDots() {
  return (
    <span aria-hidden="true" className="flex gap-1">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="size-1.5 rounded-full bg-ink-faint"
          animate={{ opacity: [0.3, 1, 0.3], y: [0, -2, 0] }}
          transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }}
        />
      ))}
    </span>
  );
}

/** Server crisis payload -> CrisisPanel props (resources get stable ids; the panel keys and styles by id). */
function toCrisisPayload(raw: object): CrisisPayload {
  const r = raw as { resources?: unknown };
  const resources = Array.isArray(r.resources)
    ? r.resources
        .filter((x): x is { id?: string; label: string; href: string } => !!x && typeof x.label === "string" && typeof x.href === "string")
        .map((x) => ({
          id: x.id ?? (x.href === "tel:988" ? "call_988" : x.href === "sms:988" ? "text_988" : x.href.startsWith("sms:") ? `text_${x.href.slice(4)}` : `call_${x.href.replace(/\W+/g, "")}`),
          label: x.label,
          href: x.href,
        }))
    : undefined;
  return { crisis: true, resources };
}

/** A crisis signal anywhere in an event payload -> the 988 panel payload (else null). */
function crisisOf(x: unknown): CrisisPayload | null {
  if (!x || typeof x !== "object") return null;
  const o = x as { crisis?: unknown; crisis_payload?: unknown };
  if (o.crisis_payload && typeof o.crisis_payload === "object") return toCrisisPayload(o.crisis_payload);
  if (o.crisis === true) return { crisis: true };
  if (o.crisis && typeof o.crisis === "object" && (o.crisis as { crisis?: unknown }).crisis !== false) return toCrisisPayload(o.crisis);
  return null;
}

const CUSTOM_ID = "custom";

/* ------------------------------------------------------------------ */
/* Main                                                                */
/* ------------------------------------------------------------------ */

type Phase = "pick" | "play" | "done";

/** Short, readable radar axis labels (the radar upper-cases them). */
const SHORT_TRAIT: Record<string, string> = {
  "Achievement Orientation": "Drive",
  "Intellectual Curiosity": "Curiosity",
  "Tolerance for Ambiguity": "Ambiguity",
  "Self-Confidence": "Confidence",
  "Leadership Orientation": "Leading",
  "Social Orientation": "Social",
  "Attention to Detail": "Detail",
  "Stress Tolerance": "Calm",
  "Self-Control": "Composure",
  Cautiousness: "Caution",
  Perseverance: "Grit",
  Dependability: "Reliable",
  Adaptability: "Adapting",
  Cooperation: "Teamwork",
};

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
  const [selected, setSelected] = React.useState<string | null>(null);
  const [hovered, setHovered] = React.useState<string | null>(null);
  /** after a choice, hold the reactions on screen until the player continues */
  const [afterOpen, setAfterOpen] = React.useState(false);
  const [customOpen, setCustomOpen] = React.useState(false);
  const [customText, setCustomText] = React.useState("");
  const [crisis, setCrisis] = React.useState<CrisisPayload | null>(null);
  const crisisRef = React.useRef(false);

  const onTap = React.useCallback((ev: TraceEvent) => {
    const c = crisisOf(ev.type === "state" ? ev.data : ev.type === "interrupt" ? ev.payload : ev.type === "done" ? ev.result : null);
    if (c) {
      crisisRef.current = true;
      setCrisis(c);
    }
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
      setPending(null);
      if (r) {
        setReport(r);
        setPhase("done");
      }
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
    async (careerId: string | null, onetSoc?: string) => {
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
      setAfterOpen(false);
      setCustomOpen(false);
      setCustomText("");
      setCrisis(null);
      trace.reset();
      setBusy(true);
      await run("/api/sim/start", onetSoc ? { onet_soc: onetSoc } : { career_id: careerId });
      setBusy(false);
    },
    [run, trace],
  );

  const choose = React.useCallback(
    async (choice: SimChoiceView) => {
      if (!threadId || !pending || busy) return;
      setLastEvent(pending);
      setChosen(choice);
      setAfterOpen(true);
      setPending(null);
      setReactions([]);
      setError(null);
      setCrisis(null);
      crisisRef.current = false;
      setCustomOpen(false);
      setBusy(true);
      const asked = pending;
      const body = choice.choice_id === CUSTOM_ID ? { choice_id: CUSTOM_ID, text: choice.text } : { choice_id: choice.choice_id };
      await run(`/api/sim/${threadId}/choose`, body);
      if (crisisRef.current) {
        // The day pauses on the same moment; the 988 panel shows above it.
        setAfterOpen(false);
        setChosen(null);
        setPending((p) => p ?? asked);
      } else {
        setCustomText("");
      }
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
    if (!pending || busy || afterOpen) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const i = ["1", "2", "3", "4"].indexOf(e.key);
      if (i >= 0 && i === pending.event.choices.length && pending.custom_allowed !== false) {
        e.preventDefault();
        setCustomOpen(true);
        return;
      }
      const c = pending.event.choices[i];
      if (c) {
        e.preventDefault();
        void choose(c);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pending, busy, choose, afterOpen]);

  // Enter continues once the next moment (or the report) is ready
  const canContinue = afterOpen && (!!pending || !!report);
  React.useEffect(() => {
    if (!canContinue) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Enter" && !(e.target instanceof HTMLButtonElement)) {
        e.preventDefault();
        setAfterOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [canContinue]);

  /* ---------------- pick ---------------- */
  if (phase === "pick") {
    const target = persona?.target_career ?? null;
    const interests = new Set(persona?.interests_careers ?? []);
    const list = careers?.careers ?? [];
    const sel = list.find((c) => c.id === selected) ?? null;
    return (
      <div className="pb-28">
        <Reveal className="max-w-2xl">
          <Kicker>Pick a workday</Kicker>
          <p className="mt-4 text-xl leading-relaxed text-ink sm:text-2xl">One shift, five moments.</p>
        </Reveal>
        <CareerSearch
          className="mt-8 max-w-xl"
          disabled={careers ? !careers.available : false}
          onPick={(h: CareerHit) => void (h.career_id && list.some((c) => c.id === h.career_id) ? start(h.career_id) : start(null, h.onet_soc))}
        />
        {loadError ? (
          <p className="mt-6 text-danger" role="alert">
            {loadError}
          </p>
        ) : null}
        {careers && !careers.available ? (
          <p className="mt-6 text-warning" role="status">
            Workdays aren&apos;t ready on the server yet.
          </p>
        ) : null}
        {!careers && !loadError ? (
          <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="Loading careers">
            {Array.from({ length: 8 }, (_, i) => (
              <div key={i} className="h-40 animate-pulse rounded-2xl bg-surface/60" />
            ))}
          </div>
        ) : null}
        <motion.ul
          className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
          variants={staggerParent(0.05, 0.15)}
          initial="hidden"
          animate={list.length ? "show" : "hidden"}
          role="listbox"
          aria-label="Careers"
        >
          {list.map((c) => {
            const mark = c.id === target ? "Your goal" : interests.has(c.id) ? "Interest" : null;
            const on = selected === c.id;
            return (
              <motion.li key={c.id} variants={staggerChild} role="option" aria-selected={on}>
                <TiltCard className="h-full">
                  <button
                    type="button"
                    disabled={c.events === 0}
                    onClick={() => setSelected(c.id)}
                    onDoubleClick={() => void start(c.id)}
                    onMouseEnter={() => setHovered(c.id)}
                    className={cn(
                      "group relative flex h-full min-h-40 w-full flex-col overflow-hidden rounded-2xl border p-5 text-left transition-[border-color,background-color] duration-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-40",
                      on ? "border-accent/70 bg-accent-wash" : "border-line bg-surface/30 hover:border-line-strong hover:bg-surface/70",
                    )}
                  >
                    {/* accent sweep on hover */}
                    <span
                      aria-hidden="true"
                      className="pointer-events-none absolute inset-y-0 -left-1/3 w-1/4 -skew-x-12 bg-gradient-to-r from-transparent via-accent/10 to-transparent opacity-0 transition-[transform,opacity] duration-[1100ms] ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:translate-x-[620%] group-hover:opacity-100"
                    />
                    <span className="flex items-start justify-between gap-3">
                      <span className="font-display text-lg leading-snug text-ink">
                        <ScrambleText text={c.title} replayKey={hovered === c.id ? c.id : null} duration={700} />
                      </span>
                      <span
                        aria-hidden="true"
                        className={cn(
                          "mt-1 grid size-5 shrink-0 place-items-center rounded-full border transition-colors duration-300",
                          on ? "border-accent bg-accent" : "border-line-strong",
                        )}
                      >
                        {on ? <motion.span layoutId="sim-pick-dot" className="size-1.5 rounded-full bg-accent-ink" /> : null}
                      </span>
                    </span>
                    {c.summary ? <span className="mt-2 line-clamp-2 text-sm text-ink-muted">{c.summary}</span> : null}
                    <span className="mt-auto flex items-center justify-between gap-2 pt-5">
                      {c.wage?.median_annual ? (
                        <span className="flex items-center gap-1.5 font-mono text-sm text-ink tabular-nums">
                          {usd(c.wage.median_annual)}
                          <span className="text-ink-faint">/yr</span>
                        </span>
                      ) : (
                        <span />
                      )}
                      {mark ? <span className="rounded-full bg-accent-wash px-2 py-0.5 text-xs text-accent">{mark}</span> : null}
                    </span>
                  </button>
                </TiltCard>
              </motion.li>
            );
          })}
        </motion.ul>

        {/* start bar */}
        <motion.div
          initial={{ y: 40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.9, ease: EASE, delay: 0.5 }}
          className="fixed inset-x-0 bottom-0 z-30 flex justify-center px-4 pb-5"
        >
          <div className="flex w-full max-w-xl items-center gap-3 rounded-full border border-line bg-bg/85 p-2 pl-5 shadow-[0_20px_60px_-20px_rgba(0,0,0,0.6)] backdrop-blur-md">
            <span className="min-w-0 flex-1 truncate text-sm text-ink-muted" aria-live="polite">
              <AnimatePresence mode="wait" initial={false}>
                <motion.span
                  key={sel?.id ?? "none"}
                  initial={{ y: 10, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ y: -10, opacity: 0 }}
                  transition={{ duration: 0.35, ease: EASE }}
                  className="block truncate"
                >
                  {sel ? <span className="text-ink">{sel.title}</span> : "Pick a career, or let Foothold choose"}
                </motion.span>
              </AnimatePresence>
            </span>
            {sel ? (
              <button type="button" className={cn(primaryPill, "shrink-0")} onClick={() => void start(sel.id)} disabled={!careers?.available}>
                <span>Start workday</span>
                <SwapArrow />
              </button>
            ) : (
              <button type="button" className={cn(primaryPill, "shrink-0")} onClick={() => void start(null)} disabled={!careers?.available}>
                <span>Let Foothold choose</span>
                <SwapArrow />
              </button>
            )}
          </div>
        </motion.div>
      </div>
    );
  }

  /* ---------------- done ---------------- */
  if (phase === "done" && report && !afterOpen) {
    const focusId = report.top_careers[0]?.career_id ?? report.career_id ?? "";
    const top = report.top_careers[0];
    const probabilityBasis =
      report.probability_basis ?? report.model.probability_basis ?? report.top_careers[0]?.probability_basis ?? "share among the Foothold careers";
    const maxP = Math.max(0.0001, ...report.top_careers.map((t) => t.probability));
    const list8 = new Set((careers?.careers ?? []).map((c) => c.id));
    return (
      <div className="space-y-14">
        <Reveal>
          <Kicker>End of your shift</Kicker>
          <h2 className="mt-4 font-display text-4xl leading-[0.95] tracking-tight text-ink sm:text-6xl">
            You work like a <br className="hidden sm:block" />
            <span className="text-accent">
              <ScrambleText text={top?.title ?? "pro"} duration={1200} />
            </span>
          </h2>
          {report.summary?.text ? <p className="mt-6 line-clamp-2 max-w-2xl text-lg leading-relaxed text-ink-muted">{report.summary.text}</p> : null}
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link href={`/path?career=${encodeURIComponent(focusId)}`} className={primaryPill}>
              <span>Plan my path</span>
              <SwapArrow />
            </Link>
            <button type="button" className={ghostPill} onClick={() => setPhase("pick")}>
              Try another workday
            </button>
          </div>
        </Reveal>

        <div className="grid gap-12 lg:grid-cols-12">
          <Reveal delay={0.25} className="lg:col-span-5">
            <h3 className="mb-4 text-sm text-ink-muted">Careers that fit</h3>
            <ol className="space-y-2">
              {report.top_careers.map((t, i) => {
                const f = report.careers[t.career_id];
                return (
                  <motion.li
                    key={t.career_id}
                    initial={{ opacity: 0, x: -16 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.7, ease: EASE, delay: 0.4 + i * 0.12 }}
                  >
                    <Link
                      href={`/path?career=${encodeURIComponent(t.career_id)}`}
                      aria-label={`Plan a route to ${t.title}`}
                      className="group block rounded-2xl border border-line p-4 transition-colors duration-300 hover:border-line-strong hover:bg-surface/60"
                    >
                      <span className="flex items-baseline justify-between gap-3">
                        <span className="text-ink">{t.title}</span>
                        <span
                          className="font-mono text-sm text-ink tabular-nums"
                          title={`${fmtPct(t.probability)}: ${t.probability_basis ?? probabilityBasis}${typeof t.p_overall === "number" ? `; ${fmtPct(t.p_overall)} overall` : ""}`}
                        >
                          {(t.probability * 100).toFixed(0)}%
                        </span>
                      </span>
                      <span className="mt-3 block h-1 overflow-hidden rounded-full bg-line">
                        <motion.span
                          className={cn("block h-full origin-left rounded-full", i === 0 ? "bg-accent" : "bg-ink-muted")}
                          initial={{ scaleX: 0 }}
                          animate={{ scaleX: t.probability / maxP }}
                          transition={{ duration: 1.1, ease: EASE, delay: 0.6 + i * 0.12 }}
                        />
                      </span>
                      {f && typeof f.wage?.median_annual === "number" ? (
                        <span className="mt-3 flex items-center gap-1.5 text-sm text-ink-muted">
                          <span className="font-mono text-ink tabular-nums">{usd(f.wage.median_annual)}</span>/yr locally
                          {typeof f.outlook?.growth_pct === "number" ? (
                            <span>
                              · {f.outlook.growth_pct > 0 ? "+" : ""}
                              {f.outlook.growth_pct}% growth
                            </span>
                          ) : null}
                        </span>
                      ) : null}
                    </Link>
                  </motion.li>
                );
              })}
            </ol>
            {!(report.model.source === "career_fit" && report.model.trained) && report.model.note ? (
              <div className="mt-3">
                <NotTrainedYet hint={report.model.note} />
              </div>
            ) : null}
          </Reveal>
          <Reveal delay={0.5} className="lg:col-span-7">
            <TraitRadar traits={report.traits.map((t) => ({ ...t, short: SHORT_TRAIT[t.name] ?? t.name }))} title="How you work" />
          </Reveal>
        </div>

        <LiveInYourArea
          careerId={list8.has(focusId) ? focusId : null}
          title={list8.has(focusId) ? null : (top?.title ?? report.occupation?.title ?? null)}
        />

        <PickedForYou personaId={account.persona_id} />

        <Reveal inView>
          <details className="group rounded-2xl border border-line p-5 open:bg-surface/30">
            <summary className="flex cursor-pointer list-none items-center justify-between text-ink">
              Your day
              <span aria-hidden="true" className="text-ink-faint transition-transform duration-300 group-open:rotate-45">
                +
              </span>
            </summary>
            <div className="mt-6 grid gap-8 lg:grid-cols-12">
              <div className="lg:col-span-5">
                <StatsRow stats={report.stats} />
              </div>
              <ol className="space-y-2 text-sm lg:col-span-7">
                {report.history.map((h) => (
                  <li key={`${h.event_id}-${h.clock}`} className="flex gap-3">
                    <span className="font-mono text-ink-faint tabular-nums">{h.clock}</span>
                    <span className="text-ink">
                      {h.title}
                      {h.choice_text ? <span className="text-ink-muted"> · {h.choice_text}</span> : null}
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          </details>
        </Reveal>
        <TracePanel nodes={trace.nodes} state={trace.state} title="Behind the scenes" />
      </div>
    );
  }

  /* ---------------- play ---------------- */
  const showAfter = afterOpen && !!lastEvent && !!chosen;
  const scene = showAfter ? null : pending;
  const shown = pending ?? lastEvent;
  const coworkers = shown?.coworkers ?? [];
  const waitingNext = !pending && !report && busy;
  const total = shown?.total ?? careers?.events_per_day ?? 5;
  const done = history.length;
  const clockNow = pending?.clock ?? lastEvent?.clock;
  const dayPct = (() => {
    const m = toMin(clockNow);
    return m === null ? 0 : Math.min(100, Math.max(0, ((m - DAY_START) / (DAY_END - DAY_START)) * 100));
  })();
  const evReactions = reactions.filter((r) => !lastEvent || r.event_id === lastEvent.event.event_id);
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      {/* day progress */}
      <div>
        <div className="flex items-baseline justify-between gap-3">
          <span className="font-mono text-3xl text-ink tabular-nums sm:text-4xl">
            <AnimatePresence mode="popLayout" initial={false}>
              <motion.span
                key={clockNow ?? "--"}
                initial={{ y: 18, opacity: 0, filter: "blur(4px)" }}
                animate={{ y: 0, opacity: 1, filter: "blur(0px)" }}
                exit={{ y: -18, opacity: 0 }}
                transition={{ duration: 0.6, ease: EASE }}
                className="inline-block"
              >
                {clockNow ?? "07:00"}
              </motion.span>
            </AnimatePresence>
          </span>
          <span className="text-sm text-ink-muted tabular-nums">
            {Math.min(done + (scene ? 1 : 0), total)} of {total}
          </span>
        </div>
        <div className="relative mt-3 h-1 rounded-full bg-line" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done} aria-label="Workday progress">
          <motion.div className="absolute inset-y-0 left-0 rounded-full bg-accent" animate={{ width: `${dayPct}%` }} transition={{ duration: 1, ease: EASE }} />
          {history.map((h) => {
            const m = toMin(h.clock);
            if (m === null) return null;
            const p = Math.min(100, Math.max(0, ((m - DAY_START) / (DAY_END - DAY_START)) * 100));
            return (
              <span
                key={`${h.event_id}-${h.clock}`}
                title={`${h.clock} ${h.title}`}
                className={cn("absolute top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-bg", h.crunch ? "bg-danger" : "bg-ink")}
                style={{ left: `${p}%` }}
              />
            );
          })}
        </div>
      </div>

      {error ? (
        <div role="alert" className="flex flex-wrap items-center gap-4 rounded-2xl border border-danger/60 p-4 text-danger">
          <span className="flex-1">{error}</span>
          {threadId ? (
            <button type="button" className={ghostPill} onClick={() => void resume()}>
              Resume
            </button>
          ) : null}
          <button type="button" className={ghostPill} onClick={() => setPhase("pick")}>
            Back to careers
          </button>
        </div>
      ) : null}

      {crisis ? <CrisisPanel payload={crisis} /> : null}

      {!shown && !error ? (
        <div aria-live="polite" className="space-y-3">
          <div className="h-8 w-2/3 animate-pulse rounded-lg bg-surface/70" />
          <div className="h-4 w-full animate-pulse rounded bg-surface/50" />
          <div className="h-4 w-5/6 animate-pulse rounded bg-surface/50" />
          <p className="pt-2 text-sm text-ink-muted">Setting up your shift…</p>
        </div>
      ) : null}

      <AnimatePresence mode="wait">
        {scene ? (
          <motion.section
            key={`ev-${scene.event.event_id}-${scene.index}`}
            aria-labelledby="sim-event-title"
            initial={{ opacity: 0, y: 24, filter: "blur(8px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: -16, filter: "blur(6px)" }}
            transition={{ duration: 0.7, ease: EASE }}
          >
            {scene.event.crunch ? <span className="mb-3 inline-block rounded-full bg-danger/15 px-2.5 py-0.5 text-xs text-danger">Crunch time</span> : null}
            <h2 id="sim-event-title" className="font-display text-3xl leading-tight tracking-tight text-ink sm:text-4xl">
              {scene.event.title}
            </h2>
            <p className="mt-4 text-lg leading-relaxed text-ink-muted">{scene.event.text}</p>
            {scene.error ? <p className="mt-3 text-danger">{scene.error}</p> : null}
            <motion.ol
              className="mt-8 space-y-2.5"
              aria-label="Your choices (press a number)"
              variants={staggerParent(0.08, 0.25)}
              initial="hidden"
              animate="show"
            >
              {scene.event.choices.map((c, i) => (
                <motion.li key={c.choice_id} variants={staggerChild}>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void choose(c)}
                    className="group flex w-full items-center gap-4 rounded-2xl border border-line bg-surface/30 p-4 text-left transition-[border-color,background-color,transform] duration-300 hover:-translate-y-0.5 hover:border-accent/50 hover:bg-surface/70 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent active:translate-y-0 disabled:opacity-60 sm:p-5"
                  >
                    <kbd className="grid size-8 shrink-0 place-items-center rounded-full border border-line-strong font-mono text-xs text-ink-muted transition-colors duration-300 group-hover:border-accent group-hover:bg-accent group-hover:text-accent-ink">
                      {i + 1}
                    </kbd>
                    <span className="flex-1 text-ink">{c.text}</span>
                    <SwapArrow className="text-ink-faint group-hover:text-accent" />
                  </button>
                </motion.li>
              ))}
              {scene.custom_allowed !== false ? (
                <motion.li key="custom" variants={staggerChild}>
                  {customOpen ? (
                    <form
                      className="flex w-full items-center gap-4 rounded-2xl border border-accent/50 bg-surface/50 p-3 sm:p-4"
                      onSubmit={(e) => {
                        e.preventDefault();
                        const text = customText.trim();
                        if (text) void choose({ choice_id: CUSTOM_ID, text });
                      }}
                    >
                      <kbd className="grid size-8 shrink-0 place-items-center rounded-full border border-accent bg-accent font-mono text-xs text-accent-ink">
                        {scene.event.choices.length + 1}
                      </kbd>
                      <label className="sr-only" htmlFor="sim-custom">
                        What would you do?
                      </label>
                      <input
                        id="sim-custom"
                        autoFocus
                        maxLength={400}
                        value={customText}
                        disabled={busy}
                        onChange={(e) => setCustomText(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Escape") setCustomOpen(false);
                        }}
                        placeholder="What would you do?"
                        className="min-w-0 flex-1 bg-transparent text-ink placeholder:text-ink-faint focus:outline-none"
                      />
                      <button type="submit" disabled={busy || !customText.trim()} aria-label="Send" className="shrink-0 text-ink-faint transition-colors hover:text-accent disabled:opacity-40">
                        <SwapArrow />
                      </button>
                    </form>
                  ) : (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => setCustomOpen(true)}
                      className="group flex w-full items-center gap-4 rounded-2xl border border-dashed border-line p-4 text-left transition-[border-color,background-color] duration-300 hover:border-accent/50 hover:bg-surface/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-60 sm:p-5"
                    >
                      <kbd className="grid size-8 shrink-0 place-items-center rounded-full border border-line-strong font-mono text-xs text-ink-muted transition-colors duration-300 group-hover:border-accent group-hover:text-accent">
                        {scene.event.choices.length + 1}
                      </kbd>
                      <span className="flex-1 text-ink-muted">Something else…</span>
                    </button>
                  )}
                </motion.li>
              ) : null}
            </motion.ol>
          </motion.section>
        ) : showAfter && lastEvent && chosen ? (
          <motion.section
            key={`after-${lastEvent.event.event_id}-${lastEvent.index}`}
            aria-live="polite"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.6, ease: EASE }}
          >
            <p className="text-sm text-ink-faint">{lastEvent.event.title}</p>
            <p className="mt-2 text-xl text-ink">
              You chose <span className="text-accent">{chosen.text}</span>
            </p>
            <ul className="mt-6 space-y-3">
              <AnimatePresence initial={false}>
                {evReactions.map((r) => (
                  <motion.li
                    key={`${r.event_id}-${r.coworker_id}`}
                    initial={{ opacity: 0, x: -16, filter: "blur(4px)" }}
                    animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
                    transition={{ duration: 0.5, ease: EASE }}
                    className="flex items-start gap-3"
                  >
                    <Avatar name={r.name} tone={REACTION_TONE[r.reaction]} />
                    <div className="min-w-0 rounded-2xl rounded-tl-sm bg-surface/70 px-4 py-3">
                      <p className="text-xs text-ink-faint">
                        {r.name} · <span className={REACTION_TONE[r.reaction] ?? "text-ink-muted"}>{r.reaction}</span>
                      </p>
                      <p className="mt-1 text-ink">{r.line}</p>
                    </div>
                  </motion.li>
                ))}
              </AnimatePresence>
              {waitingNext && evReactions.length < coworkers.length ? (
                <li className="flex items-center gap-3 pl-1 text-sm text-ink-faint">
                  <TypingDots />
                  {evReactions.length === 0
                    ? chosen.choice_id === CUSTOM_ID
                      ? "Reading your answer"
                      : "Your crew is reacting"
                    : "More reactions coming"}
                </li>
              ) : null}
            </ul>
            <div className="mt-8 flex items-center gap-4">
              <button type="button" className={primaryPill} disabled={!canContinue} onClick={() => setAfterOpen(false)}>
                <span>{report ? "See your report" : canContinue ? "Next moment" : "Waiting for your crew"}</span>
                <SwapArrow />
              </button>
              {canContinue ? <span className="hidden text-sm text-ink-faint sm:inline">or press Enter</span> : null}
            </div>
          </motion.section>
        ) : null}
      </AnimatePresence>

      {scene && coworkers.length > 0 ? (
        <div className="flex flex-wrap items-center gap-4">
          <span className="text-sm text-ink-faint">On shift with you</span>
          <div className="flex flex-wrap gap-3">
            {coworkers.map((cw) => (
              <span key={cw.id} className="flex items-center gap-2 text-sm text-ink-muted" title={`${cw.name}, ${cw.role ?? ""} · mood ${cw.mood}`}>
                <Avatar name={cw.name} small />
                <span className="hidden sm:inline">{cw.name.split(" ")[0]}</span>
              </span>
            ))}
          </div>
        </div>
      ) : null}

      <div className="border-t border-line pt-6">
        {stats ? <StatsRow stats={stats} deltas={lastDeltas} /> : null}
      </div>

      <TracePanel nodes={trace.nodes} state={trace.state} title="Behind the scenes" />
    </div>
  );
}
