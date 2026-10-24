"use client";

import * as React from "react";
import { motion, useMotionValue, useMotionValueEvent, useTransform, type MotionValue } from "motion/react";
import { cn } from "@/lib/utils";
import { getJSON, isAbortError, isOfflineError, postJSON } from "@/lib/api";
import { DEMO_ACCOUNTS } from "@/lib/auth";
import { MonoLabel } from "@/components/foothold/mono-label";
import { PreviewOffline, PreviewPanel } from "./feature-section";

/* ------------------------------------------------------------------ */
/* Try a real shift: one event from GET /api/sim/sample-event           */
/* ------------------------------------------------------------------ */

interface SampleChoice {
  choice_id: string;
  text: string;
  trait_deltas: { id: string; name: string; delta: number }[];
  stat_deltas: Record<string, number>;
  /** coworker id -> how they take this choice (present when the API sends it) */
  coworker_hints?: Record<string, string>;
}
interface SampleEvent {
  event: { event_id: string; title: string; text: string; clock?: string; status?: string; choices: SampleChoice[] };
  career: { id: string; title: string } | null;
  coworkers?: { id: string; name?: string; role?: string }[];
  events_status?: string;
  provenance?: string;
}

const STAT_LABEL: Record<string, string> = { safety: "Safety", output: "Output", team_trust: "Team trust", stress: "Stress" };
/** Stress going up is bad; every other stat going up is good. */
const statGood = (key: string, d: number) => (key === "stress" ? d < 0 : d > 0);

function titleCaseId(id: string) {
  return id
    .split("_")
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ");
}

type Load<T> = { state: "loading" } | { state: "ok"; data: T } | { state: "offline" } | { state: "error"; message: string };

export function TryShiftPreview() {
  const [res, setRes] = React.useState<Load<SampleEvent>>({ state: "loading" });
  const [picked, setPicked] = React.useState<string | null>(null);

  React.useEffect(() => {
    const ac = new AbortController();
    getJSON<SampleEvent>("/api/sim/sample-event", { auth: false, signal: ac.signal })
      .then((data) => setRes({ state: "ok", data }))
      .catch((e: unknown) => {
        if (isAbortError(e)) return;
        setRes(isOfflineError(e) ? { state: "offline" } : { state: "error", message: "The sample shift could not be loaded." });
      });
    return () => ac.abort();
  }, []);

  if (res.state === "loading") {
    return (
      <PreviewPanel label="Workday · loading">
        <p className="label-mono text-ink-faint">Clocking in…</p>
      </PreviewPanel>
    );
  }
  if (res.state !== "ok") {
    return <PreviewPanel label="Workday">{res.state === "offline" ? <PreviewOffline what="shift" /> : <p className="text-sm text-danger">{res.message}</p>}</PreviewPanel>;
  }

  const { event, career, coworkers } = res.data;
  const choice = event.choices.find((c) => c.choice_id === picked) ?? null;
  const names = new Map((coworkers ?? []).map((c) => [c.id, c]));

  return (
    <PreviewPanel
      label={`${career?.title ?? "Workday"}${event.clock ? ` · ${event.clock}` : ""}`}
    >
      <h3 className="text-lg font-medium text-ink">{event.title}</h3>
      <p className="mt-2 text-[15px] leading-relaxed text-ink-muted">{event.text}</p>
      <MonoLabel as="p" className="mt-4">
        What do you do?
      </MonoLabel>
      <ol className="mt-2 space-y-2" aria-label="Choices">
        {event.choices.map((c, i) => {
          const on = c.choice_id === picked;
          return (
            <li key={c.choice_id}>
              <button
                type="button"
                aria-pressed={on}
                onClick={() => setPicked(on ? null : c.choice_id)}
                className={cn(
                  "grid w-full grid-cols-[1.75rem_1fr] gap-2 rounded-xl border p-3 text-left text-[15px] leading-snug transition-colors",
                  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                  on ? "border-accent bg-surface text-ink" : "border-line text-ink hover:border-line-strong hover:bg-surface",
                )}
              >
                <span className="font-mono text-xs text-ink-faint tabular-nums">{i + 1}</span>
                <span>{c.text}</span>
              </button>
            </li>
          );
        })}
      </ol>

      <div aria-live="polite" className="mt-4 min-h-[5.5rem]">
        {choice ? (
          <div className="space-y-3 border-t border-line pt-3">
            <div>
              <MonoLabel as="p">Shift stats</MonoLabel>
              <ul className="mt-1.5 flex flex-wrap gap-2">
                {Object.entries(choice.stat_deltas).map(([k, d]) => (
                  <li
                    key={k}
                    className={cn(
                      "label-mono inline-flex h-6 items-center rounded-full gap-1.5 border px-2",
                      d === 0 ? "border-line text-ink-muted" : statGood(k, d) ? "border-success/50 text-success" : "border-danger/50 text-danger",
                    )}
                  >
                    {STAT_LABEL[k] ?? titleCaseId(k)} <span className="tabular-nums">{d > 0 ? `+${d}` : d}</span>
                  </li>
                ))}
              </ul>
            </div>
            {choice.trait_deltas.length ? (
              <p className="text-sm text-ink-muted">
                <span className="text-ink">Shows: </span>
                {choice.trait_deltas
                  .filter((t) => t.delta > 0)
                  .map((t) => t.name)
                  .join(", ") || "none of the tracked work styles"}
              </p>
            ) : null}
            {choice.coworker_hints && Object.keys(choice.coworker_hints).length ? (
              <ul className="space-y-1.5">
                {Object.entries(choice.coworker_hints).map(([id, hint]) => {
                  const cw = names.get(id);
                  return (
                    <li key={id} className="text-sm">
                      <span className="text-ink">{cw?.name ?? titleCaseId(id)}</span>
                      {cw?.role ? <span className="text-ink-faint"> · {cw.role}</span> : null}
                      <span className="text-ink-muted">: {hint}</span>
                    </li>
                  );
                })}
              </ul>
            ) : null}
          </div>
        ) : (
          <p className="text-sm text-ink-faint">Pick a choice to see how it moves your shift and what it shows about how you work.</p>
        )}
      </div>
    </PreviewPanel>
  );
}

/* ------------------------------------------------------------------ */
/* A path that fits your week: POST /api/path/solve                     */
/* ------------------------------------------------------------------ */

interface SolvePlan {
  route_type: string;
  label: string;
  feasible: boolean;
  months: number | null;
  cost_usd: number | null;
  peak_hours_per_week?: number | null;
  reason?: string | null;
}
interface SolveResponse {
  career_title?: string;
  routes: Record<string, SolvePlan>;
  order?: string[];
  best_route?: string | null;
  solve_ms?: number;
}

/** Maya's own limits from her profile; only the weekly hours move. */
const MAYA = { career_id: "robotics_tech", current_credits: 0, budget_usd: 4000, commute_minutes: 35, dependents: 0 };
const usd = (n: number) => `$${Math.round(n).toLocaleString("en-US")}`;

export function PathPreview() {
  const [hours, setHours] = React.useState(10);
  const [res, setRes] = React.useState<Load<SolveResponse>>({ state: "loading" });

  React.useEffect(() => {
    const ac = new AbortController();
    const t = setTimeout(() => {
      postJSON<SolveResponse>("/api/path/solve", { ...MAYA, hours_per_week: hours }, { auth: false, signal: ac.signal })
        .then((data) => setRes({ state: "ok", data }))
        .catch((e: unknown) => {
          if (isAbortError(e)) return;
          setRes(isOfflineError(e) ? { state: "offline" } : { state: "error", message: "The planner could not answer just now." });
        });
    }, 180);
    return () => {
      clearTimeout(t);
      ac.abort();
    };
  }, [hours]);

  const data = res.state === "ok" ? res.data : null;
  const order = data ? (data.order ?? Object.keys(data.routes)).filter((k) => data.routes[k]) : [];

  return (
    <PreviewPanel label={`Path · ${data?.career_title ?? "Robotics and Automation Technician"}`}>
      <p className="text-sm text-ink-muted">
        Maya has a <span className="text-ink">{usd(MAYA.budget_usd)}</span> budget and a <span className="text-ink">{MAYA.commute_minutes}-minute</span> commute. How many hours a
        week can she give it?
      </p>
      <label className="mt-4 block">
        <span className="flex items-baseline justify-between">
          <MonoLabel>Hours per week</MonoLabel>
          <span className="font-mono text-2xl text-ink tabular-nums">{hours} h</span>
        </span>
        <input
          type="range"
          min={2}
          max={24}
          step={1}
          value={hours}
          onChange={(e) => setHours(Number(e.target.value))}
          className="mt-2 w-full accent-[var(--accent)]"
          aria-valuetext={`${hours} hours per week`}
        />
      </label>

      {res.state === "offline" ? <PreviewOffline what="planner" /> : null}
      {res.state === "error" ? <p className="mt-3 text-sm text-danger">{res.message}</p> : null}
      {res.state === "loading" ? <p className="label-mono mt-3 text-ink-faint">Solving…</p> : null}

      {data ? (
        <ul className="mt-4 grid gap-2 sm:grid-cols-3" aria-live="polite">
          {order.map((k) => {
            const p = data.routes[k];
            const best = data.best_route === k;
            return (
              <li key={k} className={cn("flex flex-col gap-1 rounded-xl border p-3", best ? "border-accent" : "border-line", !p.feasible && "bg-surface")}>
                <span className="flex items-center justify-between gap-2">
                  <MonoLabel tone={p.feasible ? "success" : "danger"}>{p.feasible ? "Fits" : "Doesn't fit"}</MonoLabel>
                  {best ? <MonoLabel tone="accent">Best</MonoLabel> : null}
                </span>
                <span className="text-[15px] leading-snug text-ink">{p.label}</span>
                {p.feasible ? (
                  <span className="font-mono text-sm text-ink-muted tabular-nums">
                    {p.months ?? "–"} mo · {p.cost_usd != null ? usd(p.cost_usd) : "–"}
                  </span>
                ) : (
                  <span className="line-clamp-3 text-xs text-ink-muted" title={p.reason ?? undefined}>
                    {p.reason ?? "No schedule meets every limit."}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      ) : null}
      <p className="mt-3 text-xs text-ink-faint">
        Live from the constraint solver{typeof data?.solve_ms === "number" ? ` (${data.solve_ms} ms)` : ""}. Times and listed costs come from program data; each source is shown on Path.
      </p>
    </PreviewPanel>
  );
}

/* ------------------------------------------------------------------ */
/* Get found for what you can do: a blind card that unlocks on consent  */
/* ------------------------------------------------------------------ */

const EXAMPLE_SHOWN = ["Attention to Detail", "Dependability", "Cooperation"];

export function TalentPreview({ progress }: { progress?: MotionValue<number> } = {}) {
  const [consent, setConsent] = React.useState(false);
  const touched = React.useRef(false);
  /* On the landing stage, the request is accepted on its own partway through the stage, unless
     the visitor has already flipped the switch themselves. */
  const idle = useMotionValue(0);
  useMotionValueEvent(progress ?? idle, "change", (v) => {
    if (!touched.current) setConsent(v > 0.5);
  });
  const luis = DEMO_ACCOUNTS.find((a) => a.persona_id === "luis");
  const name = luis?.display_name ?? "Luis";
  const initials = luis?.initials ?? "L";

  return (
    <PreviewPanel label="What an employer sees">
      <div className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-start">
        <div className="min-w-0 space-y-3">
          <div className="flex items-center gap-3">
            <span
              aria-hidden="true"
              className={cn(
                "grid size-11 shrink-0 place-items-center rounded-full border font-mono text-sm transition-colors",
                consent ? "border-accent text-accent" : "border-dashed border-line-strong text-ink-faint",
              )}
            >
              {consent ? initials : "?"}
            </span>
            <div className="min-w-0">
              <p className="text-lg text-ink">{consent ? name : "Candidate · name hidden"}</p>
              <p className="text-sm text-ink-muted">{consent ? (luis?.email ?? "Contact shared") : "No name, school or photo until they say yes"}</p>
            </div>
          </div>
          <div>
            <MonoLabel as="p">Shown in a simulated workday · Diesel and Heavy-Equipment Mechanic</MonoLabel>
            <ul className="mt-1.5 flex flex-wrap gap-1.5">
              {EXAMPLE_SHOWN.map((s) => (
                <li key={s} className="label-mono inline-flex h-6 items-center rounded-full border border-line px-2 text-ink">
                  {s}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
        <span className="text-sm text-ink-muted">
          <span className="text-ink">Tri-Valley Freight</span> asked to see who this is.
        </span>
        <button
          type="button"
          role="switch"
          aria-checked={consent}
          onClick={() => {
            touched.current = true;
            setConsent((v) => !v);
          }}
          className="inline-flex items-center gap-3 text-sm text-ink focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
        >
          <span className={cn("relative h-6 w-11 rounded-full border transition-colors", consent ? "border-accent bg-accent" : "border-line-strong bg-surface")}>
            <span className={cn("absolute top-0.5 size-4 rounded-full bg-bg transition-[left]", consent ? "left-[1.4rem]" : "left-0.5")} />
          </span>
          {consent ? "Shared · tap to take it back" : "Learner: share my name"}
        </button>
      </div>
    </PreviewPanel>
  );
}

/* ------------------------------------------------------------------ */
/* You're not doing this alone: a short circle exchange                 */
/* ------------------------------------------------------------------ */

const EXCHANGE: { who: string; initials: string; text: string; self?: boolean }[] = [
  { who: "Ana", initials: "AR", text: "Got my first shift at the distribution center Monday. Nervous about the forklift cert." },
  { who: "Kou", initials: "KV", text: "I failed the practical once. Second time I asked to walk the course first. Ask them, they'll let you." },
  { who: "You", initials: "ME", text: "Same boat. Want to practice the pre-shift checklist together Sunday?", self: true },
  { who: "Ana", initials: "AR", text: "Yes. Library at 3?" },
];

function ExchangeRow({ i, progress, children, className }: { i: number; progress?: MotionValue<number>; children: React.ReactNode; className?: string }) {
  const start = 0.05 + i * 0.16;
  const idle = useMotionValue(1);
  const opacity = useTransform(progress ?? idle, (v) => Math.max(0, Math.min(1, (v - start) / 0.12)));
  const y = useTransform(opacity, [0, 1], [14, 0]);
  return (
    <motion.li style={{ opacity, y }} className={className}>
      {children}
    </motion.li>
  );
}

export function CirclePreview({ progress }: { progress?: MotionValue<number> } = {}) {
  return (
    <PreviewPanel label="Circle · Logistics, Stockton">
      <ol className="space-y-3">
        {EXCHANGE.map((m, i) => (
          <ExchangeRow key={i} i={i} progress={progress} className={cn("flex items-end gap-2", m.self && "flex-row-reverse")}>
            <span aria-hidden="true" className="grid size-8 shrink-0 place-items-center rounded-full border border-line font-mono text-[11px] text-ink-muted">
              {m.initials}
            </span>
            <div className={cn("max-w-[80%] rounded-2xl border px-3.5 py-2", m.self ? "border-accent/60" : "border-line")}>
              <MonoLabel as="p">{m.who}</MonoLabel>
              <p className="text-[15px] leading-snug text-ink">{m.text}</p>
            </div>
          </ExchangeRow>
        ))}
      </ol>
      <p className="mt-4 border-t border-line pt-3 text-sm text-ink-muted">
        Small circles by career and city, a coach for hard conversations, and crisis resources one tap away.
      </p>
    </PreviewPanel>
  );
}
