"use client";

import * as React from "react";
import { fetchProfile, PROFILE_EVENT, saveProfile, type Profile, type ProfilePatch } from "@/lib/profile";
import { useAccount } from "./auth-provider";

/* One profile per tab session, shared by every component that asks (nav place switcher, pages). */

let cacheToken: string | null = null;
let cache: Profile | null = null;
let inflight: Promise<void> | null = null;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

function subscribe(l: () => void) {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
}

if (typeof window !== "undefined") {
  window.addEventListener(PROFILE_EVENT, (e) => {
    const p = (e as CustomEvent<Profile>).detail;
    if (p) {
      cache = p;
      emit();
    }
  });
}

function load(token: string) {
  if (cacheToken === token && (cache || inflight)) return;
  cacheToken = token;
  cache = null;
  inflight = fetchProfile()
    .then((p) => {
      if (cacheToken === token) cache = p;
    })
    .catch(() => undefined)
    .finally(() => {
      inflight = null;
      emit();
    });
}

export interface UseProfileResult {
  profile: Profile | null;
  save: (patch: ProfilePatch) => Promise<Profile>;
}

/** The signed-in account's profile (null while loading or signed out). */
export function useProfile(): UseProfileResult {
  const { token } = useAccount();
  React.useEffect(() => {
    if (token) load(token);
  }, [token]);
  const profile = React.useSyncExternalStore(
    subscribe,
    () => (token && cacheToken === token ? cache : null),
    () => null,
  );
  return { profile, save: saveProfile };
}
