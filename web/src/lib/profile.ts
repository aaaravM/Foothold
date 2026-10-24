/**
 * Profile + places (GET/PATCH /api/auth/me/profile, GET /api/meta/places, GET /api/places/near).
 * Other pages can listen for `PROFILE_EVENT` on window to re-solve when the place changes.
 */

import { getJSON, patchJSON } from "./api";

export interface Place {
  id: string;
  name: string;
  county: string;
  lat: number;
  lon: number;
  approximate?: boolean;
}

export interface Campus {
  id: string;
  name: string;
  kind: string;
  place_id: string;
  lat: number;
  lon: number;
  approximate?: boolean;
}

export interface PlacesResponse {
  places: Place[];
  campuses: Campus[];
  drive_assumption?: string;
  approximate?: boolean;
}

export interface Profile {
  place_id: string | null;
  lat: number | null;
  lon: number | null;
  hours_per_week: number | null;
  budget_usd: number | null;
  commute_minutes: number | null;
  current_credits: number | null;
  dependents: number | null;
  interests: string[];
  talent_opt_in: boolean;
  place: { id: string; name: string; county: string } | null;
  org_name?: string | null;
}

export type ProfilePatch = Partial<
  Pick<Profile, "place_id" | "hours_per_week" | "budget_usd" | "commute_minutes" | "current_credits" | "dependents" | "interests" | "talent_opt_in" | "org_name">
>;

/** Fired on window after a successful profile save: `detail` is the new Profile. */
export const PROFILE_EVENT = "foothold:profile";

let placesPromise: Promise<PlacesResponse> | null = null;

/** Places and campuses (cached for the page view; a failure clears the cache so it can retry). */
export function fetchPlaces(): Promise<PlacesResponse> {
  if (!placesPromise) {
    placesPromise = getJSON<PlacesResponse>("/api/meta/places", { auth: false }).catch((e: unknown) => {
      placesPromise = null;
      throw e;
    });
  }
  return placesPromise;
}

export function fetchProfile(signal?: AbortSignal): Promise<Profile> {
  return getJSON<Profile>("/api/auth/me/profile", { signal });
}

export async function saveProfile(patch: ProfilePatch): Promise<Profile> {
  const p = await patchJSON<Profile>("/api/auth/me/profile", patch);
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent<Profile>(PROFILE_EVENT, { detail: p }));
  return p;
}

/** Interests offered on onboarding (career ids from the sim catalogue + plain words). */
export const INTEREST_OPTIONS: readonly { id: string; label: string }[] = [
  { id: "logistics", label: "Warehouses & logistics" },
  { id: "healthcare", label: "Healthcare" },
  { id: "welding", label: "Welding & fabrication" },
  { id: "agriculture", label: "Agriculture & ag-tech" },
  { id: "diesel", label: "Diesel & equipment" },
  { id: "electrical", label: "Electrical" },
  { id: "it", label: "IT & computers" },
  { id: "business", label: "Business & office" },
];
