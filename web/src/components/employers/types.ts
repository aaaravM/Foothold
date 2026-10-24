/** Shapes returned by api/foothold/routes/employer.py + consent.py (all FICTIONAL demo data). */

export interface SkillRef {
  id: string;
  name: string;
  level?: number;
  evidence?: string;
}

export interface SimBand {
  band: string;
  career_id?: string;
  career_title?: string | null;
  metric?: string;
}

export interface PathwayProgress {
  pct?: number;
  label?: string | null;
  career_id?: string;
  career_title?: string | null;
  route_type?: string;
  steps_done?: number;
  steps_total?: number;
}

export interface Availability {
  hours_per_week: number | null;
  shifts: string[];
  days: string[];
  start?: string | null;
  label?: string | null;
}

export interface Region {
  label?: string | null;
  radius_miles?: number;
  commute_minutes?: number;
}

export interface BlindCard {
  candidate_id: string;
  fictional: boolean;
  demonstrated_skills: SkillRef[];
  sim_bands: SimBand[];
  pathway_progress: PathwayProgress | null;
  availability: Availability | null;
  region: Region | null;
  target_career?: { id: string; title: string } | null;
  hidden: string[];
}

export interface CardMatch {
  score: number;
  matched: string[];
  missing: string[];
  recommender: number | null;
}

export interface RequestStatusRef {
  id: string;
  status: RequestStatus;
}

export type RequestStatus = "pending" | "accepted" | "declined";

export interface TalentCard extends BlindCard {
  match?: CardMatch;
  request?: RequestStatusRef | null;
}

export interface TalentResponse {
  posting_id: string | null;
  pool_size: number;
  eligible: number;
  filtered_out: number;
  recommender: { used: boolean; note: string };
  weights: { skill_match: number; recommender: number };
  provenance: string;
  fictional: boolean;
  cards: TalentCard[];
}

export interface Revealed {
  name: string | null;
  initials: string | null;
  photo: string | null;
  exact_location: string | null;
  contact: { email: string | null; phone: string | null };
}

export interface EmployerRequest {
  id: string;
  candidate_id: string;
  posting_id: string | null;
  posting_title: string | null;
  message: string;
  status: RequestStatus;
  created_at: string;
  decided_at: string | null;
  card: BlindCard | null;
  revealed: Revealed | null;
  duplicate?: boolean;
}

export interface RequestCounts {
  pending: number;
  accepted: number;
  declined: number;
  total: number;
  acceptance_rate: number | null;
}

export interface RequestsResponse {
  requests: EmployerRequest[];
  counts: RequestCounts;
}

export interface CandidateResponse {
  card: BlindCard;
  consented: boolean;
  revealed: Revealed | null;
  request: RequestStatusRef | null;
}

export interface PostingSkill {
  skill_id: string;
  name: string;
  importance: "required" | "preferred";
  evidence: string;
}

export interface PostingProfile {
  role_title: string;
  career_id: string | null;
  career_title: string | null;
  skills: PostingSkill[];
  dropped_unknown_skills: string[];
  shift: string;
  min_hours_per_week: number | null;
  summary: string;
}

export interface InjectionInfo {
  attempt: boolean;
  flags: string[];
  flag_text: string[];
  model_flagged: boolean;
  model_note: string | null;
  excerpts: string[];
  handling: string | null;
}

export interface SimVariantEvent {
  event_id: string;
  template_event_id: string;
  clock?: string | null;
  title: string;
  text: string;
  choices: { choice_id: string; text: string }[];
  status: string;
}

export interface SimVariant {
  status: string;
  needs_human_review: boolean;
  setting: string;
  career_id: string | null;
  events: SimVariantEvent[];
  llm?: string;
  note?: string;
}

export interface PostingSummary {
  id: string;
  title: string;
  created_at: string;
  career_id: string | null;
  skills: PostingSkill[];
  injection: InjectionInfo | null;
}

export interface FairnessRate {
  group: string;
  n: number | null;
  selected: number | null;
  rate: number | null;
  suppressed: boolean;
}

export interface FairnessAudit {
  available: boolean;
  reason?: string;
  selected?: number;
  pool?: number;
  min_group_size?: number;
  rates?: FairnessRate[];
  impact_ratio?: number | null;
  passes_four_fifths?: boolean | null;
  note?: string | null;
  method?: string | null;
}

export interface FairnessResponse {
  posting_id: string | null;
  posting_title?: string;
  shortlist_size?: number;
  audit: FairnessAudit;
  offline?: unknown;
}

export interface GapRow {
  skill_id: string;
  skill_name: string;
  postings: number;
  required: number;
  demand_score: number;
  pool_size: number;
  pool_with_skill: number | null;
  coverage: number | null;
  gap: number | null;
  suppressed: boolean;
}

export interface GapReport {
  available: boolean;
  reason?: string;
  postings: number;
  pool_size: number;
  min_group_size: number;
  rows: GapRow[];
  suppressed?: number;
  updated_at?: string;
}

export interface PickInterrupt {
  kind: "pick_candidates";
  posting_id: string | null;
  shortlist_ids: string[];
  prompt: string;
  message_template: string;
}

/* Learner inbox */

export interface InboxRequest {
  id: string;
  employer: { id: string; name: string; fictional: boolean };
  posting_id: string | null;
  posting_title: string | null;
  message: string;
  status: RequestStatus;
  created_at: string;
  decided_at: string | null;
}

export interface InboxResponse {
  candidate_id: string | null;
  card: BlindCard | null;
  requests: InboxRequest[];
  shared_on_accept: { field: string; label: string; value: string }[];
  always_visible: { field: string; label: string }[];
}
