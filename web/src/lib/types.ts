/**
 * TypeScript mirrors of docs/CONTRACTS.md:
 *   section 4 (shared ids), section 5 (data/processed/*.json), section 6 (SSE events),
 *   section 9 (API surface) and section 10 (ml/artifacts/metrics.json).
 *
 * Where the contract leaves a shape open, the type is deliberately loose
 * (`unknown` / index signatures) so pages validate at runtime instead of trusting it.
 */

/* ------------------------------------------------------------------ */
/* Section 4: shared ids and vocabularies                              */
/* ------------------------------------------------------------------ */

export type Provenance = "REAL" | "SAMPLE" | "SYNTHETIC" | "FICTIONAL";
export const PROVENANCE_VALUES: readonly Provenance[] = ["REAL", "SAMPLE", "SYNTHETIC", "FICTIONAL"];

export const CAREER_IDS = [
  "logistics_lead",
  "registered_nurse",
  "diesel_mechanic",
  "welder",
  "electrician",
  "software_dev",
  "farm_ops_manager",
  "robotics_tech",
] as const;
export type CareerId = (typeof CAREER_IDS)[number];

/** O*NET 31.0 Work Styles (21 elements). Display names/order come from data/processed/traits.json at runtime. */
export const TRAIT_IDS = [
  "innovation",
  "achievement_orientation",
  "intellectual_curiosity",
  "tolerance_for_ambiguity",
  "initiative",
  "adaptability",
  "self_confidence",
  "perseverance",
  "leadership_orientation",
  "humility",
  "sincerity",
  "empathy",
  "cooperation",
  "optimism",
  "social_orientation",
  "cautiousness",
  "attention_to_detail",
  "dependability",
  "integrity",
  "stress_tolerance",
  "self_control",
] as const;
export type TraitId = (typeof TRAIT_IDS)[number];

export const SIM_STAT_IDS = ["safety", "output", "team_trust", "stress"] as const;
export type SimStatId = (typeof SIM_STAT_IDS)[number];
/** ints 0..100; a run starts at 70/50/50/20 */
export type SimStats = Record<SimStatId, number>;

export const ROUTE_TYPES = ["cc_transfer", "certificate", "apprenticeship", "direct_to_work"] as const;
export type RouteType = (typeof ROUTE_TYPES)[number];

export type LearnerId = "maya" | "dev" | "luis";
export type EmployerId = "tri_valley_freight";

/* ------------------------------------------------------------------ */
/* Section 5: data files (data/processed/)                             */
/* ------------------------------------------------------------------ */

export interface Trait {
  id: TraitId;
  name: string;
  onet_element_id: string;
  group: string;
  short: string;
}

export interface Wage {
  median_hourly: number | null;
  median_annual: number | null;
  p25_annual: number | null;
  p75_annual: number | null;
  area: string;
  period: string;
  source_id: string;
  status: Provenance;
}

export interface Outlook {
  growth_pct: number | null;
  annual_openings: number | null;
  period: string;
  source_id: string;
  status: Provenance;
}

export interface Coworker {
  id: string;
  name: string;
  role: string;
  style: string;
  base_mood: string | number;
}

export interface Career {
  id: CareerId;
  title: string;
  onet_soc: string;
  onet_title: string;
  summary: string;
  path_types: RouteType[];
  /** trait_id -> 0..1 */
  work_styles: Partial<Record<TraitId, number>>;
  skills: string[];
  wage: Wage;
  outlook: Outlook;
  /** 3, fictional */
  coworkers: Coworker[];
}

export interface Occupation {
  onet_soc: string;
  title: string;
  career_id: CareerId | null;
  work_styles: Partial<Record<TraitId, number>>;
}

export interface Skill {
  id: string;
  name: string;
  category: string;
}

export interface Course {
  id: string;
  title: string;
  provider: string;
  cost_usd: number;
  hours: number;
  skills: string[];
  url: string;
  status: Provenance;
}

export type Weekday = "Mon" | "Tue" | "Wed" | "Thu" | "Fri" | "Sat" | "Sun";

export interface ProgramSection {
  id: string;
  days: Weekday[];
  /** "18:00" */
  start: string;
  /** "20:50" */
  end: string;
  modality: "in_person" | "online" | "hybrid";
  campus?: string;
}

export interface ProgramStep {
  id: string;
  title: string;
  kind: "course" | "block" | "job";
  units?: number;
  hours_per_week: number;
  weeks: number;
  cost_usd: number;
  prereqs: string[];
  sections: ProgramSection[];
  paid_wage_hourly?: number;
}

export interface Program {
  id: string;
  career_id: CareerId;
  route_type: RouteType;
  name: string;
  provider: string;
  credential: string;
  url: string;
  status: Provenance;
  source_id: string;
  steps: ProgramStep[];
}

export interface SimChoice {
  choice_id: string;
  text: string;
  /** values in [-1, 1] over 2-4 traits */
  trait_deltas: Partial<Record<TraitId, number>>;
  /** ints in [-15, 15] */
  stat_deltas: Partial<SimStats>;
  /** coworker_id -> how this coworker tends to feel about it */
  coworker_hints: Record<string, string>;
}

export interface SimEvent {
  event_id: string;
  career_ids: CareerId[];
  /** "09:15" */
  clock: string;
  title: string;
  text: string;
  crunch: boolean;
  status: string;
  choices: SimChoice[];
}

export interface EventsFile {
  schema_version: 1;
  status: string;
  events: SimEvent[];
}

export interface Source {
  id: string;
  title: string;
  url: string;
  publisher: string;
  license: string;
  retrieved: string;
  status: Provenance;
}

/** personas.json: the contract lists constraints/interests without a fixed schema. */
export interface PersonaRecord {
  id: LearnerId | EmployerId;
  [key: string]: unknown;
}

/* ------------------------------------------------------------------ */
/* Section 6: SSE contract (every LangGraph run)                       */
/* ------------------------------------------------------------------ */

export type TraceNodeKind = "llm" | "model" | "solver" | "human" | "logic";
export type LlmSource = "openai" | "cache" | "mock";

export interface TraceNode {
  id: string;
  label: string;
  kind: TraceNodeKind;
  /** parallel fan-out nodes share a group, e.g. "coworkers_react" */
  group?: string;
}

export interface TraceMetaEvent {
  type: "meta";
  graph: string;
  thread_id: string;
  nodes: TraceNode[];
}

export interface TraceNodeEvent {
  type: "node";
  graph: string;
  node: string;
  status: "start" | "end";
  ts: number;
  ms?: number;
  /** short, non-personal, e.g. "picked event rn_02 · gain 0.41 bits" */
  summary?: string;
  llm?: LlmSource;
}

export interface TraceStateEvent {
  type: "state";
  graph: string;
  data: Record<string, unknown>;
}

export interface TraceInterruptEvent {
  type: "interrupt";
  graph: string;
  node: string;
  payload: unknown;
}

export interface TraceDoneEvent {
  type: "done";
  graph: string;
  result: unknown;
}

export interface TraceErrorEvent {
  type: "error";
  message: string;
}

export type TraceEvent =
  | TraceMetaEvent
  | TraceNodeEvent
  | TraceStateEvent
  | TraceInterruptEvent
  | TraceDoneEvent
  | TraceErrorEvent;

export type TraceEventType = TraceEvent["type"];

/* ------------------------------------------------------------------ */
/* Section 9: API surface                                              */
/* ------------------------------------------------------------------ */

/** GET /health (no /api prefix) */
export interface HealthResponse {
  ok: boolean;
  llm: {
    /** "auto" | "openai" | "mock" as configured / resolved by the API */
    mode: string;
    model: string | null;
    key_present: boolean;
    key_ok: boolean | null;
  };
  demo_mode: boolean;
}

export type MetaKind = "careers" | "traits" | "skills" | "courses" | "programs" | "sources" | "personas";

export interface MetaResponseMap {
  careers: Career[];
  traits: Trait[];
  skills: Skill[];
  courses: Course[];
  programs: Program[];
  sources: Source[];
  personas: PersonaRecord[];
}

/* Sim */
export interface SimStartRequest {
  career_id: CareerId | null;
  persona_id?: string;
}
export interface SimChooseRequest {
  choice_id: string;
}

/* Path */
export interface PathSolveRequest {
  career_id: CareerId;
  current_credits: number;
  hours_per_week: number;
  budget_usd: number;
  commute_minutes: number;
  dependents: number;
  extra_constraints?: Record<string, unknown>;
}
export interface PathSolveResponse {
  solve_ms: number;
  [key: string]: unknown;
}
export interface PathTranslateRequest {
  text: string;
}
export interface PathDecisionRequest {
  approve: boolean;
  reason?: string;
}

/* Employer */
export interface EmployerPostingRequest {
  employer_id: EmployerId | string;
  title: string;
  text: string;
}
export interface ConsentDecisionRequest {
  /** value vocabulary is defined by the employer slice */
  decision: string;
}

/* Circle */
export interface CoachRequest {
  session_id: string;
  text: string;
  mode: string;
}
export interface EqFeedbackRequest {
  scenario_id: string;
  response: string;
}

/* Graph */
export interface GraphNode {
  id: string;
  [key: string]: unknown;
}
export interface GraphLink {
  source: string;
  target: string;
  [key: string]: unknown;
}
export interface GraphSample {
  nodes: GraphNode[];
  links: GraphLink[];
}
export type RecommenderModel = "gnn" | "mf" | "pop";

/* ------------------------------------------------------------------ */
/* Section 10: ml/artifacts/metrics.json (served by GET /api/metrics)  */
/* ------------------------------------------------------------------ */

export interface MetricBlockBase {
  status: string;
  provenance: string;
  data: unknown;
  seed: number;
  trained_at: string;
  reproduce: string;
  [key: string]: unknown;
}

export interface Metrics {
  career_fit?: MetricBlockBase;
  selector?: MetricBlockBase;
  recommender?: MetricBlockBase;
  planner?: MetricBlockBase;
  fairness?: MetricBlockBase;
  verifier?: MetricBlockBase;
  [key: string]: MetricBlockBase | undefined;
}
