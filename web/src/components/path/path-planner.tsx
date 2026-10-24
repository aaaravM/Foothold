"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { drawLinkClass } from "@/components/auth/parts";
import { ghostPill, QuietLabel as MonoLabel, primaryPill } from "@/components/sim/fx";
import { TracePanel } from "@/components/foothold/trace-panel";
import { errorMessage, useTappedTrace } from "@/components/sim/use-tapped-trace";
import { getJSON, postJSON } from "@/lib/api";
import type { Account } from "@/lib/auth";
import type { TraceEvent } from "@/lib/types";
import { cn } from "@/lib/utils";
import { AnimatePresence, motion } from "motion/react";
import { NearbyPrograms, PlacePicker, usePlaces } from "./nearby";
import { PathKanban } from "./path-kanban";
import { PickedForYou } from "./picked-for-you";
import { usePersona } from "./use-persona";

/* ------------------------------------------------------------------ */
/* API shapes (api/foothold/routes/path.py + planner.py)               */
/* ------------------------------------------------------------------ */

export interface Rule {
  type: string;
  label?: string;
  number?: number;
  time?: string;
  day?: string;
  route_type?: string;
  season?: string;
  [k: string]: unknown;
}
interface SourceRef {
  id?: string;
  title?: string;
  url?: string;
}
interface TermStep {
  step: string;
  title: string;
  kind: string;
  units?: number | null;
  paid?: boolean;
  paid_wage_hourly?: number | null;
  hours_per_week?: number;
  days?: string[];
  start?: string | null;
  end?: string | null;
  modality?: string | null;
  campus?: string | null;
}
interface Term {
  index: number;
  term: string;
  hours_per_week: number;
  commute_hours_per_week?: number;
  campus_days?: string[];
  cost_usd: number;
  steps: TermStep[];
}
interface RoutePlan {
  route_type: string;
  label: string;
  feasible: boolean;
  status?: string;
  available?: boolean;
  months: number | null;
  cost_usd: number | null;
  peak_hours_per_week?: number | null;
  start_term?: string | null;
  finish_term?: string | null;
  terms?: Term[];
  solve_ms?: number;
  reason?: string | null;
  hints?: Record<string, unknown>;
  greedy?: { feasible: boolean; months: number | null; cost_usd: number | null; schedule_changes?: number; solve_ms?: number; reason?: string | null };
  delta?: { months?: number | null; cost_usd?: number | null; schedule_changes?: number | null };
  checks?: { id: string; label: string; ok: boolean }[];
  verified?: boolean;
  expected_wage?: {
    median_annual?: number | null;
    median_hourly?: number | null;
    area?: string;
    period?: string;
    status?: string;
    source?: SourceRef | null;
  } | null;
  starting_wage_hourly?: number | null;
  commute?: { campus_id?: string; campus?: string; distance_km?: number; minutes_one_way?: number; approximate?: boolean } | null;
  program?: { id: string; name: string; provider?: string; credential?: string; url?: string; status?: string; source?: SourceRef | null } | null;
}
interface SolveResponse {
  career_id: string;
  career_title: string;
  start_term?: string;
  order: string[];
  best_route: string | null;
  solve_ms: number;
  request_ms?: number;
  assumptions?: string[];
  routes: Record<string, RoutePlan>;
  rules: Rule[];
}
interface CareerLite {
  id: string;
  title: string;
}
interface ApprovalPayload {
  kind: "approve_plan" | "confirm_rules";
  round?: number;
  best_route?: string | null;
  proposal?: { best_route: string | null; text: string; source?: string; reasons?: string[] } | null;
  rules?: Rule[];
  proposed?: Rule[];
  can_retry?: boolean;
}

interface Inputs {
  hours_per_week: number;
  budget_usd: number;
  commute_minutes: number;
  current_credits: number;
  dependents: number;
}

const DEFAULT_INPUTS: Inputs = { hours_per_week: 12, budget_usd: 2000, commute_minutes: 20, current_credits: 0, dependents: 0 };

const ROUTE_LABEL: Record<string, string> = {
  cc_transfer: "College transfer",
  certificate: "Certificate",
  apprenticeship: "Apprenticeship",
  direct_to_work: "Direct to work",
};

const SLIDERS: { key: keyof Inputs; label: string; min: number; max: number; step: number; fmt: (n: number) => string }[] = [
  { key: "hours_per_week", label: "Hours a week for school", min: 2, max: 40, step: 1, fmt: (n) => `${n} h` },
  { key: "budget_usd", label: "Total budget", min: 0, max: 15000, step: 100, fmt: (n) => `$${n.toLocaleString("en-US")}` },
  { key: "commute_minutes", label: "Max commute (one way)", min: 5, max: 90, step: 5, fmt: (n) => `${n} min` },
  { key: "current_credits", label: "College credits already earned", min: 0, max: 60, step: 1, fmt: (n) => `${n} units` },
];

const usd = (n: number) => `$${Math.round(n).toLocaleString("en-US")}`;
const ruleKey = (r: Rule) => JSON.stringify({ ...r, label: undefined });

function RuleChip({ rule, onRemove }: { rule: Rule; onRemove?: () => void }) {
  return (
    <span className="inline-flex items-center gap-2 border border-line-strong px-2 py-1 text-sm text-ink">
      {rule.label ?? rule.type}
      {onRemove ? (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Remove rule: ${rule.label ?? rule.type}`}
          className="font-mono text-xs text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
        >
          ×
        </button>
      ) : null}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Route column                                                        */
/* ------------------------------------------------------------------ */

function RouteColumn({ plan, best, selected, onSelect, index = 0 }: { plan: RoutePlan; best: boolean; selected: boolean; onSelect: () => void; index?: number }) {
  const wage = plan.expected_wage;
  return (
    <motion.section
      aria-label={`${plan.label} route`}
      initial={{ opacity: 0, y: 18, filter: "blur(6px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay: index * 0.07 }}
      className={cn(
        "relative flex flex-col gap-3 rounded-2xl border p-5 transition-colors duration-500",
        selected ? "border-accent/70 bg-accent-wash" : "border-line hover:border-line-strong",
        !plan.feasible && "opacity-70",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <MonoLabel tone={best ? "accent" : "muted"}>{best ? "Best fit" : ROUTE_LABEL[plan.route_type] ?? plan.route_type}</MonoLabel>
        <MonoLabel tone={plan.feasible ? "muted" : "danger"}>{plan.feasible ? "Fits your week" : "Doesn't fit"}</MonoLabel>
      </div>
      <h3 className="font-display text-xl text-ink">{plan.label}</h3>
      {plan.program ? (
        <p className="text-sm text-ink-muted">
          {plan.program.url ? (
            <a href={plan.program.url} target="_blank" rel="noreferrer" className="link-draw text-ink">
              {plan.program.name}
            </a>
          ) : (
            <span className="text-ink">{plan.program.name}</span>
          )}
          {plan.commute?.minutes_one_way != null ? ` · ${plan.commute.minutes_one_way} min drive` : ""}
        </p>
      ) : null}

      {plan.feasible ? (
        <dl className="grid grid-cols-3 gap-x-3 text-sm">
          <div>
            <MonoLabel as="dt">Time</MonoLabel>
            <dd className="font-mono text-lg text-ink tabular-nums">{plan.months ?? "–"} mo</dd>
          </div>
          <div>
            <MonoLabel as="dt">Cost</MonoLabel>
            <dd className="font-mono text-lg text-ink tabular-nums">{plan.cost_usd != null ? usd(plan.cost_usd) : "–"}</dd>
          </div>
          <div>
            <MonoLabel as="dt">Pay</MonoLabel>
            <dd className="font-mono text-lg text-ink tabular-nums">{typeof wage?.median_annual === "number" ? `${usd(wage.median_annual / 1000)}k` : "–"}</dd>
          </div>
        </dl>
      ) : (
        <p className="text-sm text-ink">{plan.reason ?? "No schedule fits every rule."}</p>
      )}

      {plan.feasible ? (
        <div className="mt-auto pt-1">
          <button type="button" onClick={onSelect} aria-pressed={selected} className={drawLinkClass}>
            {selected ? "Hide terms" : "Show terms"}
          </button>
        </div>
      ) : null}
    </motion.section>
  );
}

/** A collapsible step: one title, one hint, body revealed on demand. */
function Step({ title, hint, open, onToggle, children }: { title: string; hint?: string; open: boolean; onToggle: (open: boolean) => void; children: React.ReactNode }) {
  const id = `path-step-${title.toLowerCase()}`;
  return (
    <section className="border-t border-line pt-5">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => onToggle(!open)}
        className="group flex w-full items-baseline justify-between gap-4 text-left focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
      >
        <span className="flex items-baseline gap-3">
          <span className="font-display text-2xl text-ink">{title}</span>
          {hint ? <MonoLabel>{hint}</MonoLabel> : null}
        </span>
        <span aria-hidden="true" className={cn("text-xl text-ink-muted transition-transform duration-300", open && "rotate-45")}>
          +
        </span>
      </button>
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            id={id}
            key="body"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="pt-6">{children}</div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </section>
  );
}

function TermTimeline({ plan }: { plan: RoutePlan }) {
  const terms = plan.terms ?? [];
  if (!terms.length) return null;
  return (
    <div>
      <div className="relative mb-4 h-px bg-line" aria-hidden="true">
        <motion.div
          key={plan.route_type}
          className="absolute inset-y-0 left-0 origin-left bg-accent"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          style={{ width: "100%" }}
          transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>
      <ol key={plan.route_type} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {terms.map((t, i) => (
          <motion.li
            key={t.index}
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1], delay: 0.15 + i * 0.08 }}
            className="rounded-2xl border border-line p-4"
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-ink">{t.term}</span>
              <MonoLabel>
                {t.hours_per_week} h/wk · {usd(t.cost_usd)}
              </MonoLabel>
            </div>
            <ul className="mt-2 space-y-2 text-sm">
              {t.steps.map((s) => (
                <li key={s.step} className="border-l border-accent/40 pl-3">
                  <p className="text-ink">{s.title}</p>
                  <MonoLabel as="p">
                    {[s.days?.join(" "), s.start && s.end && !(s.start === "00:00" && s.end === "23:59") ? `${s.start}–${s.end}` : null, s.modality?.replace("_", " "), s.paid ? "paid" : null]
                      .filter(Boolean)
                      .join(" · ")}
                  </MonoLabel>
                  {s.campus ? <p className="text-xs text-ink-muted">{s.campus}</p> : null}
                </li>
              ))}
            </ul>
          </motion.li>
        ))}
      </ol>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main                                                                */
/* ------------------------------------------------------------------ */

export function PathPlanner({ account }: { account: Account }) {
  const params = useSearchParams();
  const persona = usePersona(account.persona_id);
  const [careers, setCareers] = React.useState<CareerLite[]>([]);
  const [careerChoice, setCareerId] = React.useState<string>(params.get("career") ?? "");
  const [override, setInputs] = React.useState<Inputs | null>(null);
  const [timedOut, setTimedOut] = React.useState(false);
  const personaInputs = React.useMemo<Inputs | null>(
    () =>
      persona
        ? {
            hours_per_week: persona.hours_per_week ?? 12,
            budget_usd: persona.budget_usd ?? 2000,
            commute_minutes: persona.commute_minutes ?? 20,
            current_credits: persona.current_credits ?? 0,
            dependents: persona.dependents ?? 0,
          }
        : null,
    [persona],
  );
  const inputs: Inputs | null = override ?? personaInputs ?? (timedOut ? DEFAULT_INPUTS : null);
  const careerId = careerChoice || persona?.target_career || (timedOut ? "logistics_lead" : "");
  const [rules, setRules] = React.useState<Rule[]>([]);
  const [solve, setSolve] = React.useState<SolveResponse | null>(null);
  const [solving, setSolving] = React.useState(false);
  const [solveError, setSolveError] = React.useState<string | null>(null);
  const [selected, setSelected] = React.useState<string | null>(null);
  const [ruleText, setRuleText] = React.useState("");
  const [proposed, setProposed] = React.useState<Rule[] | null>(null);
  const [translating, setTranslating] = React.useState(false);
  const [translateError, setTranslateError] = React.useState<string | null>(null);
  const [reason, setReason] = React.useState("");
  const [agentBusy, setAgentBusy] = React.useState(false);
  const [approved, setApproved] = React.useState(false);
  const [kanbanVersion, setKanbanVersion] = React.useState(0);
  const [showTerms, setShowTerms] = React.useState(false);
  const [adjustOpen, setAdjustOpen] = React.useState(false);
  const [trackOpen, setTrackOpen] = React.useState(false);
  const { places, placeId, save: savePlace } = usePlaces();
  /** a place picked here this session; only then is it sent to the solver (demo personas keep their commute otherwise) */
  const [pickedPlace, setPickedPlace] = React.useState<string | null>(null);
  const placeName = places.find((p) => p.id === placeId)?.name;
  const where = pickedPlace ? { place_id: pickedPlace } : {};

  const onTap = React.useCallback((ev: TraceEvent) => {
    if (ev.type === "done") {
      const r = ev.result as { approved?: boolean } | null;
      if (r?.approved) {
        setApproved(true);
        setKanbanVersion((v) => v + 1);
        setTrackOpen(true);
      }
    }
  }, []);
  const { trace, run } = useTappedTrace(onTap);
  const interrupt = (trace.state.interrupt?.payload ?? null) as ApprovalPayload | null;

  // careers list
  React.useEffect(() => {
    getJSON<{ careers: CareerLite[] }>("/api/sim/careers")
      .then((r) => setCareers(r.careers.map((c) => ({ id: c.id, title: c.title }))))
      .catch(() => undefined);
  }, []);

  // persona fetch failed or slow: fall back to the API defaults after a moment
  React.useEffect(() => {
    const t = setTimeout(() => setTimedOut(true), 2500);
    return () => clearTimeout(t);
  }, []);

  // debounced solve
  React.useEffect(() => {
    if (!inputs || !careerId) return;
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      setSolving(true);
      postJSON<SolveResponse>("/api/path/solve", { career_id: careerId, ...inputs, ...where, extra_constraints: rules }, { signal: ctrl.signal })
        .then((r) => {
          setSolve(r);
          setSolveError(null);
          setSelected((cur) => (cur && r.routes[cur]?.feasible ? cur : r.best_route));
        })
        .catch((e) => {
          if (!ctrl.signal.aborted) setSolveError(errorMessage(e));
        })
        .finally(() => {
          if (!ctrl.signal.aborted) setSolving(false);
        });
    }, 350);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inputs, careerId, rules, pickedPlace]);

  const translate = async () => {
    if (!ruleText.trim()) return;
    setTranslating(true);
    setTranslateError(null);
    try {
      const r = await postJSON<{ rules: Rule[]; source?: string }>("/api/path/translate", { text: ruleText });
      setProposed(r.rules);
      if (!r.rules.length) setTranslateError("No rule found. Try “weekends off”.");
    } catch (e) {
      setTranslateError(errorMessage(e));
    }
    setTranslating(false);
  };

  const applyProposed = () => {
    if (!proposed) return;
    setRules((cur) => {
      const keys = new Set(cur.map(ruleKey));
      return [...cur, ...proposed.filter((r) => !keys.has(ruleKey(r)))];
    });
    setProposed(null);
    setRuleText("");
  };

  const startAgent = async () => {
    if (!inputs || !careerId) return;
    setApproved(false);
    setAgentBusy(true);
    trace.reset();
    await run("/api/path/start", { career_id: careerId, ...inputs, ...where, rules });
    setAgentBusy(false);
  };

  const decide = async (approve: boolean) => {
    const tid = trace.state.threadId;
    if (!tid || !interrupt) return;
    setAgentBusy(true);
    const body =
      interrupt.kind === "confirm_rules" ? { approve: true, rules: interrupt.proposed ?? [] } : { approve, reason: approve ? null : reason.trim() || null };
    await run(`/api/path/${tid}/decision`, body);
    if (!approve) setReason("");
    setAgentBusy(false);
  };

  const routes = solve ? solve.order.map((k) => solve.routes[k]).filter(Boolean) : [];
  const selPlan = selected && solve ? solve.routes[selected] : null;

  return (
    <div className="space-y-10">
      {/* routes first */}
      <section aria-labelledby="path-routes" aria-busy={solving}>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 id="path-routes" className="font-display text-2xl text-ink">
            Routes for your week
          </h2>
          <div className="flex items-center gap-3">
            <MonoLabel aria-live="polite">{solving ? "Solving…" : ""}</MonoLabel>
            <label htmlFor="path-career" className="sr-only">
              Career
            </label>
            <select
              id="path-career"
              value={careerId}
              onChange={(e) => setCareerId(e.target.value)}
              className="h-10 rounded-full border border-line-strong bg-bg px-3 text-sm text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              {!careerId ? <option value="">Choose a career</option> : null}
              {careers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </div>
        </div>
        {solveError ? (
          <p role="alert" className="mb-4 text-danger">
            {solveError}
          </p>
        ) : null}
        <div className={cn("grid gap-3 sm:grid-cols-2", routes.length > 3 ? "xl:grid-cols-4" : "lg:grid-cols-3", solving && "opacity-70")}>
          {routes.map((p, i) => (
            <RouteColumn
              key={p.route_type}
              index={i}
              plan={p}
              best={solve?.best_route === p.route_type}
              selected={showTerms && selected === p.route_type}
              onSelect={() => {
                if (showTerms && selected === p.route_type) setShowTerms(false);
                else {
                  setSelected(p.route_type);
                  setShowTerms(true);
                }
              }}
            />
          ))}
        </div>
        {showTerms && selPlan?.feasible ? (
          <div className="mt-6">
            <TermTimeline plan={selPlan} />
          </div>
        ) : null}
      </section>

      <PickedForYou personaId={account.persona_id} />

      {/* near you, compact */}
      <section aria-label="Programs near you" className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-xl text-ink">
            Programs near <span className="text-accent">{placeName ?? "you"}</span>
          </h2>
          <PlacePicker
            places={places}
            value={placeId}
            onChange={(id) => {
              setPickedPlace(id);
              void savePlace(id);
            }}
          />
        </div>
        <NearbyPrograms placeId={placeId} placeName={placeName} careerId={careerId} hideHeading />
      </section>

      {/* adjust: sliders, rules, approval */}
      <Step title="Adjust" hint={approved ? "Plan approved" : "Your week, rules, approval"} open={adjustOpen} onToggle={setAdjustOpen}>
        <div className="grid gap-8 lg:grid-cols-12">
          <div className="space-y-5 lg:col-span-4">
            {inputs ? (
              SLIDERS.map((s) => (
                <div key={s.key} className="space-y-1">
                  <div className="flex items-baseline justify-between">
                    <MonoLabel as="label" htmlFor={`path-${s.key}`} tone="ink">
                      {s.label}
                    </MonoLabel>
                    <span className="font-mono text-sm text-ink tabular-nums">{s.fmt(inputs[s.key])}</span>
                  </div>
                  <input
                    id={`path-${s.key}`}
                    type="range"
                    min={s.min}
                    max={s.max}
                    step={s.step}
                    value={inputs[s.key]}
                    onChange={(e) => setInputs({ ...inputs, [s.key]: Number(e.target.value) })}
                    className="w-full accent-[var(--color-accent)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                  />
                </div>
              ))
            ) : (
              <MonoLabel as="p">Loading…</MonoLabel>
            )}
          </div>

          <div className="space-y-5 lg:col-span-8">
            <div className="space-y-2">
              <MonoLabel as="label" htmlFor="path-rule-text" tone="ink">
                Rules in your words
              </MonoLabel>
              <div className="flex flex-col gap-2 sm:flex-row">
                <input
                  id="path-rule-text"
                  value={ruleText}
                  onChange={(e) => setRuleText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      void translate();
                    }
                  }}
                  placeholder="I work weekends and can't make class before 9am"
                  className="h-11 flex-1 border border-line-strong bg-bg px-3 text-ink placeholder:text-ink-faint focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                />
                <button type="button" onClick={() => void translate()} disabled={translating || !ruleText.trim()} className={cn(ghostPill, "h-11 justify-center")}>
                  {translating ? "Reading…" : "Add rules"}
                </button>
              </div>
              {translateError ? (
                <p role="alert" className="text-sm text-danger">
                  {translateError}
                </p>
              ) : null}
            </div>
            {proposed && proposed.length > 0 ? (
              <div className="border border-dashed border-accent p-3" aria-live="polite">
                <MonoLabel as="p">Confirm these rules</MonoLabel>
                <div className="mt-2 flex flex-wrap gap-2">
                  {proposed.map((r, i) => (
                    <RuleChip key={ruleKey(r)} rule={r} onRemove={() => setProposed(proposed.filter((_, j) => j !== i))} />
                  ))}
                </div>
                <div className="mt-3 flex gap-4">
                  <button type="button" className={drawLinkClass} onClick={applyProposed}>
                    Apply {proposed.length} rule{proposed.length === 1 ? "" : "s"}
                  </button>
                  <button type="button" className={drawLinkClass} onClick={() => setProposed(null)}>
                    Discard
                  </button>
                </div>
              </div>
            ) : null}
            {rules.length ? (
              <div className="flex flex-wrap gap-2">
                {rules.map((r, i) => (
                  <RuleChip key={ruleKey(r)} rule={r} onRemove={() => setRules(rules.filter((_, j) => j !== i))} />
                ))}
              </div>
            ) : null}

            <div className="space-y-4 border-t border-line pt-5">
              {!interrupt ? (
                <button type="button" onClick={() => void startAgent()} disabled={agentBusy || !inputs || !careerId} className={primaryPill}>
                  <span>{agentBusy ? "Working…" : approved ? "Plan again" : "Propose my plan"}</span>
                  <span aria-hidden="true" className="font-mono text-xs">
                    ↵
                  </span>
                </button>
              ) : null}
              {trace.state.error ? (
                <p role="alert" className="text-danger">
                  {trace.state.error}
                </p>
              ) : null}
              {approved && !interrupt ? (
                <p role="status" className="text-success">
                  Approved. Steps added to Track.
                </p>
              ) : null}
              {interrupt?.kind === "approve_plan" ? (
                <div className="border border-line-strong p-4" aria-live="polite">
                  <MonoLabel as="p">
                    Proposal{interrupt.round && interrupt.round > 1 ? ` · round ${interrupt.round}` : ""}
                    {interrupt.best_route ? ` · ${ROUTE_LABEL[interrupt.best_route] ?? interrupt.best_route}` : ""}
                  </MonoLabel>
                  <p className="mt-2 text-lg text-ink">{interrupt.proposal?.text}</p>
                  <div className="mt-4 flex flex-col gap-3">
                    <button type="button" onClick={() => void decide(true)} disabled={agentBusy || !interrupt.proposal?.best_route} className={cn(primaryPill, "self-start")}>
                      <span>Approve this plan</span>
                    </button>
                    <div className="space-y-1">
                      <MonoLabel as="label" htmlFor="path-reject-reason" tone="ink">
                        Or say what&apos;s wrong
                      </MonoLabel>
                      <div className="flex flex-col gap-2 sm:flex-row">
                        <input
                          id="path-reject-reason"
                          value={reason}
                          onChange={(e) => setReason(e.target.value)}
                          placeholder="Too long. I also can't do Fridays."
                          className="h-11 flex-1 border border-line-strong bg-bg px-3 text-ink placeholder:text-ink-faint focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                        />
                        <button
                          type="button"
                          onClick={() => void decide(false)}
                          disabled={agentBusy || interrupt.can_retry === false}
                          className="h-11 border border-line-strong px-4 text-ink hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-50"
                        >
                          Reject and re-solve
                        </button>
                      </div>
                      {interrupt.can_retry === false ? <MonoLabel as="p">Retry limit reached.</MonoLabel> : null}
                    </div>
                  </div>
                </div>
              ) : null}
              {interrupt?.kind === "confirm_rules" ? (
                <div className="border border-dashed border-accent p-4">
                  <MonoLabel as="p">Confirm these rules</MonoLabel>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {(interrupt.proposed ?? []).map((r) => (
                      <RuleChip key={ruleKey(r)} rule={r} />
                    ))}
                  </div>
                  <button type="button" className={cn(drawLinkClass, "mt-3")} onClick={() => void decide(true)} disabled={agentBusy}>
                    Confirm rules
                  </button>
                </div>
              ) : null}
              {trace.state.status !== "idle" ? <TracePanel nodes={trace.nodes} state={trace.state} title="Behind the scenes" /> : null}
            </div>
          </div>
        </div>
      </Step>

      <Step title="Track" hint="Your saved steps" open={trackOpen} onToggle={setTrackOpen}>
        <PathKanban version={kanbanVersion} />
      </Step>
    </div>
  );
}
