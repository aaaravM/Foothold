"use client";

import * as React from "react";
import {
  DEFAULT_PERSONA_ID,
  getPersona,
  isPersonaId,
  PERSONA_ORDER,
  PERSONAS,
  type PersonaId,
  type PersonaSummary,
} from "@/lib/personas";

export const PERSONA_STORAGE_KEY = "foothold-persona";

/* ---- tiny external store (localStorage + in-memory fallback + cross-tab sync) ---- */

const listeners = new Set<() => void>();
let memoryPersona: PersonaId | null = null;

function readPersona(): PersonaId {
  if (memoryPersona) return memoryPersona;
  try {
    const v = window.localStorage.getItem(PERSONA_STORAGE_KEY);
    if (isPersonaId(v)) return v;
  } catch {
    // storage blocked
  }
  return DEFAULT_PERSONA_ID;
}

function writePersona(id: PersonaId): void {
  memoryPersona = id;
  try {
    window.localStorage.setItem(PERSONA_STORAGE_KEY, id);
  } catch {
    // storage blocked: the in-memory value still works for this tab
  }
  listeners.forEach((l) => l());
}

function subscribePersona(onChange: () => void): () => void {
  listeners.add(onChange);
  const onStorage = (e: StorageEvent) => {
    if (e.key === PERSONA_STORAGE_KEY) {
      memoryPersona = isPersonaId(e.newValue) ? e.newValue : null;
      onChange();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onStorage);
  };
}

const getServerPersona = (): PersonaId => DEFAULT_PERSONA_ID;

/* ---- context ---- */

export interface PersonaContextValue {
  personaId: PersonaId;
  persona: PersonaSummary;
  setPersona: (id: PersonaId) => void;
  /** all personas in display order */
  personas: readonly PersonaSummary[];
  isLearner: boolean;
  /** true while a parent forces the persona (e.g. demo mode) */
  forced: boolean;
}

const PersonaContext = React.createContext<PersonaContextValue | null>(null);

const ALL_PERSONAS: readonly PersonaSummary[] = PERSONA_ORDER.map((id) => PERSONAS[id]);

function useStorePersona(): PersonaId {
  return React.useSyncExternalStore(subscribePersona, readPersona, getServerPersona);
}

function buildValue(personaId: PersonaId, forced: boolean): PersonaContextValue {
  const persona = getPersona(personaId);
  return {
    personaId,
    persona,
    setPersona: writePersona,
    personas: ALL_PERSONAS,
    isLearner: persona.kind === "learner",
    forced,
  };
}

export interface PersonaProviderProps {
  children: React.ReactNode;
  /** force a persona for this subtree (demo mode); switching is still stored for later */
  forcePersonaId?: PersonaId;
}

/** Current demo persona (fictional), persisted in localStorage. Default: maya. */
export function PersonaProvider({ children, forcePersonaId }: PersonaProviderProps) {
  const stored = useStorePersona();
  const personaId = forcePersonaId ?? stored;
  const forced = forcePersonaId !== undefined;
  const value = React.useMemo(() => buildValue(personaId, forced), [personaId, forced]);
  return <PersonaContext.Provider value={value}>{children}</PersonaContext.Provider>;
}

/** Works inside or outside <PersonaProvider> (outside it reads the stored persona). */
export function usePersona(): PersonaContextValue {
  const ctx = React.useContext(PersonaContext);
  const stored = useStorePersona();
  const fallback = React.useMemo(() => buildValue(stored, false), [stored]);
  return ctx ?? fallback;
}
