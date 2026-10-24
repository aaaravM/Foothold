"use client";

import { useEffect, useState } from "react";
import { getJSON } from "@/lib/api";

/** A persona record from GET /api/meta/personas (all FICTIONAL). Only the fields the UI reads. */
export interface PersonaRow {
  id: string;
  kind: "learner" | "employer";
  display_name?: string;
  target_career?: string | null;
  interests_careers?: string[];
  current_credits?: number;
  hours_per_week?: number;
  budget_usd?: number;
  commute_minutes?: number;
  dependents?: number;
  region?: string;
  goal?: string;
}

/** The signed-in account's persona (null while loading or when the API is down). */
export function usePersona(personaId: string | null | undefined): PersonaRow | null {
  const [persona, setPersona] = useState<PersonaRow | null>(null);
  useEffect(() => {
    if (!personaId) return;
    let live = true;
    getJSON<{ personas?: PersonaRow[] } | PersonaRow[]>("/api/meta/personas")
      .then((res) => {
        const list = Array.isArray(res) ? res : (res?.personas ?? []);
        const p = list.find((x) => x && x.id === personaId) ?? null;
        if (live) setPersona(p);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [personaId]);
  return persona;
}
