"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { Brackets, drawLinkClass, techButtonClass } from "@/components/auth/parts";
import { MonoLabel } from "@/components/foothold/mono-label";
import { ProvenanceBadge } from "@/components/foothold/provenance-badge";
import { SourceLink } from "@/components/foothold/source-link";
import { TracePanel } from "@/components/foothold/trace-panel";
import { errorMessage, useTappedTrace } from "@/components/sim/use-tapped-trace";
import { getJSON, postJSON } from "@/lib/api";
import type { Account } from "@/lib/auth";
import type { Provenance, TraceEvent } from "@/lib/types";
import { cn } from "@/lib/utils";
import { PathKanban } from "./path-kanban";
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

function prov(status: unknown): Provenance {
  const s = String(status ?? "").split(" ")[0].toUpperCase();
  return s === "REAL" || s === "SAMPLE" || s === "SYNTHETIC" || s === "FICTIONAL" ? (s as Provenance) : "SAMPLE";
}
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

function RouteColumn({ plan, best, selected, onSelect }: { plan: RoutePlan; best: boolean; selected: boolean; onSelect: () => void }) {
  const wage = plan.expected_wage;
  const passed = plan.checks?.filter((c) => c.ok).length ?? 0;
  return (
    <section
      aria-label={`${plan.label} route`}
      className={cn("flex flex-col gap-3 border p-4", selected ? "border-accent" : "border-line", !plan.feasible && "bg-surface")}
    >
      <div className="flex items-center justify-between gap-2">
        <MonoLabel tone={best ? "accent" : "muted"}>{best ? "Best fit" : ROUTE_LABEL[plan.route_type] ?? plan.route_type}</MonoLabel>
        <MonoLabel tone={plan.feasible ? "success" : "danger"}>{plan.feasible ? "Feasible" : "Doesn't fit"}</MonoLabel>
      </div>
      <h3 className="font-display text-xl text-ink">{plan.label}</h3>
      {plan.program ? (
        <div className="text-sm">
          <p className="text-ink">{plan.program.name}</p>
          <p className="text-ink-muted">{plan.program.provider}</p>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <ProvenanceBadge status={prov(plan.program.status)} href={plan.program.source?.url} />
            {plan.program.url ? <SourceLink href={plan.program.url} label="Program page" /> : null}
          </div>
        </div>
      ) : null}

      {plan.feasible ? (
        <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-sm">
          <div>
            <MonoLabel as="dt">Time</MonoLabel>
            <dd className="font-mono text-lg text-ink tabular-nums">{plan.months ?? "–"} mo</dd>
          </div>
          <div>
            <MonoLabel as="dt">Listed cost</MonoLabel>
            <dd className="font-mono text-lg text-ink tabular-nums">{plan.cost_usd != null ? usd(plan.cost_usd) : "–"}</dd>
          </div>
          <div>
            <MonoLabel as="dt">Peak load</MonoLabel>
            <dd className="font-mono text-ink tabular-nums">{plan.peak_hours_per_week ?? "–"} h/wk</dd>
          </div>
          <div>
            <MonoLabel as="dt">Terms</MonoLabel>
            <dd className="text-ink">
              {plan.start_term} → {plan.finish_term}
            </dd>
          </div>
        </dl>
      ) : (
        <div className="space-y-2 text-sm">
          <p className="text-ink">{plan.reason ?? "No schedule satisfies every rule."}</p>
          {plan.hints && Object.keys(plan.hints).length > 0 ? (
            <MonoLabel as="p">
              Would need:{" "}
              {Object.entries(plan.hints)
                .map(([k, v]) => `${k.replace(/_/g, " ")} ${String(v)}`)
                .join(" · ")}
            </MonoLabel>
          ) : null}
        </div>
      )}

      <div className="border-t border-line pt-3 text-sm">
        <MonoLabel as="p">Expected wage</MonoLabel>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          {typeof wage?.median_annual === "number" ? (
            <span className="font-mono text-ink tabular-nums">{usd(wage.median_annual)}/yr median</span>
          ) : (
            <span className="text-ink-muted">not available</span>
          )}
          {wage ? <ProvenanceBadge status={prov(wage.status)} href={wage.source?.url} note={wage.area} /> : null}
        </div>
        {typeof plan.starting_wage_hourly === "number" ? (
          <p className="mt-1 text-ink-muted">Starting pay in plan: ${plan.starting_wage_hourly.toFixed(2)}/h</p>
        ) : null}
      </div>

      {plan.greedy ? (
        <div className="border-t border-line pt-3">
          <MonoLabel as="p">CP-SAT vs greedy</MonoLabel>
          <table className="mt-1 w-full text-sm">
            <caption className="sr-only">Solver comparison for {plan.label}</caption>
            <thead>
              <tr className="text-left">
                <th scope="col" className="font-normal text-ink-muted" />
                <th scope="col" className="font-mono text-xs font-normal text-ink-muted">CP-SAT</th>
                <th scope="col" className="font-mono text-xs font-normal text-ink-muted">Greedy</th>
              </tr>
            </thead>
            <tbody className="font-mono tabular-nums">
              <tr>
                <th scope="row" className="text-left font-sans font-normal text-ink-muted">Months</th>
                <td className="text-ink">{plan.feasible ? plan.months : "✕"}</td>
                <td className="text-ink">{plan.greedy.feasible ? plan.greedy.months : "✕"}</td>
              </tr>
              <tr>
                <th scope="row" className="text-left font-sans font-normal text-ink-muted">Cost</th>
                <td className="text-ink">{plan.feasible && plan.cost_usd != null ? usd(plan.cost_usd) : "✕"}</td>
                <td className="text-ink">{plan.greedy.feasible && plan.greedy.cost_usd != null ? usd(plan.greedy.cost_usd) : "✕"}</td>
              </tr>
              <tr>
                <th scope="row" className="text-left font-sans font-normal text-ink-muted">Solve</th>
                <td className="text-ink">{plan.solve_ms ?? 0} ms</td>
                <td className="text-ink">{plan.greedy.solve_ms ?? 0} ms</td>
              </tr>
            </tbody>
          </table>
        </div>
      ) : null}

      <div className="mt-auto flex items-center justify-between gap-2 pt-2">
        {plan.checks?.length ? (
          <MonoLabel tone={plan.verified ? "success" : "warning"}>
            {passed}/{plan.checks.length} checks
          </MonoLabel>
        ) : (
          <span />
        )}
        {plan.feasible ? (
          <button type="button" onClick={onSelect} aria-pressed={selected} className={drawLinkClass}>
            {selected ? "Showing terms" : "Show terms"}
          </button>
        ) : null}
      </div>
    </section>
  );
}

function TermTimeline({ plan }: { plan: RoutePlan }) {
  const terms = plan.terms ?? [];
  if (!terms.length) return null;
  return (
    <div>
      <MonoLabel as="h3" tone="ink" className="mb-3">
        Term by term · {plan.label}
      </MonoLabel>
      <ol className="grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
        {terms.map((t) => (
          <li key={t.index} className="bg-bg p-3">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-ink">{t.term}</span>
              <MonoLabel>
                {t.hours_per_week} h/wk · {usd(t.cost_usd)}
              </MonoLabel>
            </div>
            <ul className="mt-2 space-y-2 text-sm">
              {t.steps.map((s) => (
                <li key={s.step} className="border-l-2 border-line-strong pl-2">
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
          </li>
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

  const onTap = React.useCallback((ev: TraceEvent) => {
    if (ev.type === "done") {
      const r = ev.result as { approved?: boolean } | null;
      if (r?.approved) {
        setApproved(true);
        setKanbanVersion((v) => v + 1);
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
      postJSON<SolveResponse>("/api/path/solve", { career_id: careerId, ...inputs, extra_constraints: rules }, { signal: ctrl.signal })
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
  }, [inputs, careerId, rules]);

  const translate = async () => {
    if (!ruleText.trim()) return;
    setTranslating(true);
    setTranslateError(null);
    try {
      const r = await postJSON<{ rules: Rule[]; source?: string }>("/api/path/translate", { text: ruleText });
      setProposed(r.rules);
      if (!r.rules.length) setTranslateError("No rule found in that sentence. Try something like “no classes before 9am” or “weekends off”.");
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
    await run("/api/path/start", { career_id: careerId, ...inputs, rules });
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
      {/* constraints */}
      <section aria-labelledby="path-constraints" className="grid gap-8 lg:grid-cols-12">
        <div className="space-y-5 lg:col-span-4">
          <MonoLabel as="h2" id="path-constraints" tone="accent">
            Step 1 · Your constraints
          </MonoLabel>
          <div className="space-y-2">
            <MonoLabel as="label" htmlFor="path-career" tone="ink">
              Career
            </MonoLabel>
            <select
              id="path-career"
              value={careerId}
              onChange={(e) => setCareerId(e.target.value)}
              className="h-11 w-full border border-line-strong bg-bg px-2 text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              {!careerId ? <option value="">Choose a career</option> : null}
              {careers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </div>
          {inputs
            ? SLIDERS.map((s) => (
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
            : <MonoLabel as="p">Loading your constraints…</MonoLabel>}
          {persona ? (
            <MonoLabel as="p" tone="faint">
              Prefilled from {persona.display_name ?? account.display_name}&apos;s profile (fictional)
            </MonoLabel>
          ) : null}
        </div>

        <div className="space-y-4 lg:col-span-8">
          <MonoLabel as="h2" tone="accent">
            Step 2 · Rules in your own words
          </MonoLabel>
          <div className="space-y-2">
            <MonoLabel as="label" htmlFor="path-rule-text" tone="ink">
              Describe your week
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
              <button type="button" onClick={() => void translate()} disabled={translating || !ruleText.trim()} className={cn(techButtonClass, "h-11")}>
                <span>{translating ? "Reading…" : "Turn into rules"}</span>
                <Brackets offset={5} />
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
              <MonoLabel as="p">Confirm these rules before they change your plan</MonoLabel>
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
          <div>
            <MonoLabel as="p">Active rules</MonoLabel>
            <div className="mt-2 flex flex-wrap gap-2">
              {rules.length ? (
                rules.map((r, i) => <RuleChip key={ruleKey(r)} rule={r} onRemove={() => setRules(rules.filter((_, j) => j !== i))} />)
              ) : (
                <span className="text-sm text-ink-muted">None yet. The sliders still apply.</span>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-line pt-3 text-sm">
            <MonoLabel>Check with the colleges</MonoLabel>
            <SourceLink href="https://programmap.deltacollege.edu/" label="Delta College Program Mapper" />
            <SourceLink href="https://programmap.mjc.edu/" label="MJC Program Mapper" />
            <SourceLink href="https://assist.org" label="ASSIST (UC/CSU transfer)" />
          </div>
        </div>
      </section>

      {/* routes */}
      <section aria-labelledby="path-routes" aria-busy={solving}>
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
          <h2 id="path-routes" className="font-display text-2xl text-ink">
            {solve ? `Routes to ${solve.career_title}` : "Routes"}
          </h2>
          <MonoLabel aria-live="polite">
            {solving ? "Solving…" : solve ? `OR-Tools CP-SAT · ${solve.solve_ms} ms · starts ${solve.start_term ?? ""}` : ""}
          </MonoLabel>
        </div>
        {solveError ? (
          <p role="alert" className="mb-4 text-danger">
            {solveError}
          </p>
        ) : null}
        <div className={cn("grid gap-3 sm:grid-cols-2 xl:grid-cols-4", solving && "opacity-70")}>
          {routes.map((p) => (
            <RouteColumn key={p.route_type} plan={p} best={solve?.best_route === p.route_type} selected={selected === p.route_type} onSelect={() => setSelected(p.route_type)} />
          ))}
        </div>
        {solve?.assumptions?.length ? (
          <details className="mt-3 text-sm text-ink-muted">
            <summary className="cursor-pointer hover:text-ink focus-visible:outline-2 focus-visible:outline-accent">Planner assumptions</summary>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {solve.assumptions.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          </details>
        ) : null}
      </section>

      {selPlan?.feasible ? <TermTimeline plan={selPlan} /> : null}

      {/* agent approval */}
      <section aria-labelledby="path-agent" className="grid gap-8 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-5">
          <MonoLabel as="h2" id="path-agent" tone="accent">
            Step 3 · Get a plan you approve
          </MonoLabel>
          <p className="text-ink-muted">
            Foothold retrieves programs, solves, checks every number, then waits for you. Reject it with a reason and that reason becomes a new rule.
          </p>
          {!interrupt ? (
            <button type="button" onClick={() => void startAgent()} disabled={agentBusy || !inputs || !careerId} className={techButtonClass}>
              <span>{agentBusy ? "Working…" : approved ? "Plan again" : "Propose my plan"}</span>
              <span aria-hidden="true" className="font-mono text-xs">
                ↵
              </span>
              <Brackets offset={5} />
            </button>
          ) : null}
          {trace.state.error ? (
            <p role="alert" className="text-danger">
              {trace.state.error}
            </p>
          ) : null}
          {approved && !interrupt ? (
            <p role="status" className="text-success">
              Plan approved. Its steps are on your board below.
            </p>
          ) : null}
        </div>
        <div className="space-y-4 lg:col-span-7">
          {interrupt?.kind === "approve_plan" ? (
            <div className="border border-line-strong p-4" aria-live="polite">
              <MonoLabel as="p">
                Proposal · round {interrupt.round ?? 1}
                {interrupt.best_route ? ` · ${ROUTE_LABEL[interrupt.best_route] ?? interrupt.best_route}` : ""}
              </MonoLabel>
              <p className="mt-2 text-lg text-ink">{interrupt.proposal?.text}</p>
              {interrupt.proposal?.reasons?.length ? (
                <ul className="mt-2 list-disc pl-5 text-sm text-ink-muted">
                  {interrupt.proposal.reasons.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              ) : null}
              {interrupt.rules?.length ? (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <MonoLabel>Rules in this round</MonoLabel>
                  {interrupt.rules.map((r) => (
                    <RuleChip key={ruleKey(r)} rule={r} />
                  ))}
                </div>
              ) : null}
              <div className="mt-4 flex flex-col gap-3">
                <button type="button" onClick={() => void decide(true)} disabled={agentBusy || !interrupt.proposal?.best_route} className={cn(techButtonClass, "self-start")}>
                  <span>Approve this plan</span>
                  <Brackets offset={5} />
                </button>
                <div className="space-y-1">
                  <MonoLabel as="label" htmlFor="path-reject-reason" tone="ink">
                    Or tell Foothold what&apos;s wrong
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
                  {interrupt.can_retry === false ? <MonoLabel as="p">Retry limit reached for this run.</MonoLabel> : null}
                </div>
              </div>
            </div>
          ) : null}
          {interrupt?.kind === "confirm_rules" ? (
            <div className="border border-dashed border-accent p-4">
              <MonoLabel as="p">Confirm the rules Foothold read</MonoLabel>
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
          {trace.state.status !== "idle" ? <TracePanel nodes={trace.nodes} state={trace.state} title="Behind the scenes" defaultOpen /> : null}
        </div>
      </section>

      <PathKanban version={kanbanVersion} />
    </div>
  );
}
