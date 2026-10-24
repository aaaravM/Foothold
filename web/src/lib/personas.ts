/**
 * Static profiles of the demo people, for public examples only (landing chapters, About).
 * ALL FICTIONAL: invented people and an invented employer. Ids match docs/CONTRACTS.md section 4.
 *
 * This is not identity: who is signed in comes from the per-tab account session
 * (components/auth, CONTRACTS section 13). There is no persona switcher.
 * Detailed constraints (hours, budget, commute, credits) live in data/processed/personas.json
 * and come from GET /api/meta/personas.
 */
import type { EmployerId, LearnerId, Provenance } from "./types";

export type PersonaId = LearnerId | EmployerId;
export type PersonaKind = "learner" | "employer";

export interface PersonaSummary {
  id: PersonaId;
  kind: PersonaKind;
  /** display name (first name for learners) */
  name: string;
  /** one-line situation */
  tagline: string;
  /** short facts for example cards */
  facts: string[];
  age?: number;
  fictional: true;
  status: Extract<Provenance, "FICTIONAL">;
}

export const PERSONAS: Readonly<Record<PersonaId, PersonaSummary>> = {
  maya: {
    id: "maya",
    kind: "learner",
    name: "Maya",
    age: 16,
    tagline: "High-school junior, first in her family headed to college, wants a UC.",
    facts: ["16, junior", "First-generation", "Into engineering", "Wants to get into a UC"],
    fictional: true,
    status: "FICTIONAL",
  },
  dev: {
    id: "dev",
    kind: "learner",
    name: "Dev",
    age: 41,
    tagline: "Warehouse picker whose job is being automated; 45 h/week, two kids.",
    facts: ["41", "Warehouse picker, role being automated", "Works 45 h/week", "Two kids"],
    fictional: true,
    status: "FICTIONAL",
  },
  luis: {
    id: "luis",
    kind: "learner",
    name: "Luis",
    age: 18,
    tagline: "High-school senior into diesel and farm equipment; family business.",
    facts: ["18, senior", "Diesel and farm equipment", "Family business"],
    fictional: true,
    status: "FICTIONAL",
  },
  tri_valley_freight: {
    id: "tri_valley_freight",
    kind: "employer",
    name: "Tri-Valley Freight",
    tagline: "Fictional logistics employer hiring through blind, consent-gated cards.",
    facts: ["Logistics employer", "Fictional company"],
    fictional: true,
    status: "FICTIONAL",
  },
};

export const PERSONA_ORDER: readonly PersonaId[] = ["maya", "dev", "luis", "tri_valley_freight"];
export const LEARNER_IDS: readonly LearnerId[] = ["maya", "dev", "luis"];
export const EMPLOYER_IDS: readonly EmployerId[] = ["tri_valley_freight"];

export function isPersonaId(value: unknown): value is PersonaId {
  return typeof value === "string" && Object.prototype.hasOwnProperty.call(PERSONAS, value);
}

export function isLearnerId(value: unknown): value is LearnerId {
  return value === "maya" || value === "dev" || value === "luis";
}

export function getPersona(id: PersonaId): PersonaSummary {
  return PERSONAS[id];
}
