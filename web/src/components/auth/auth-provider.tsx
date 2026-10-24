"use client";

import * as React from "react";
import { toast } from "sonner";
import { getJSON, isApiError, postJSON } from "@/lib/api";
import {
  clearSession,
  getSession,
  isAccount,
  onSessionCheckRequested,
  sessionExpiresAt,
  setSession,
  subscribeSession,
  type Account,
  type Session,
} from "@/lib/auth";

export type { Account, AccountKind, Session } from "@/lib/auth";

export type AuthStatus = "loading" | "signed_in" | "signed_out";

export type AuthState = {
  account: Account | null;
  /** "loading" only until the tab's session has been read (server render + hydration) */
  status: AuthStatus;
  token: string | null;
  /** epoch ms when this tab's session ends */
  expiresAt: number | null;
  /** POST /api/auth/login; resolves with the account or throws an ApiError (401 wrong credentials) */
  signIn: (email: string, password: string) => Promise<Account>;
  /** POST /api/auth/register; signs this tab in with the new account (throws ApiError 409/422) */
  signUp: (input: SignUpInput) => Promise<Account>;
  /** ends this tab's session only (other tabs stay signed in) */
  signOut: () => Promise<void>;
  /** re-check the session with GET /api/auth/me now */
  refresh: () => Promise<void>;
};

interface LoginResponse {
  token: string;
  token_type?: string;
  account: Account;
  expires_at?: string;
}

export interface SignUpInput {
  display_name: string;
  email: string;
  password: string;
  kind: "learner" | "employer";
  org_name?: string;
  place_id?: string;
}

interface MeResponse {
  account: Account;
  expires_at?: string;
  candidate_id?: string | null;
}

/* ------------------------------------------------------------------ */
/* Session lifecycle (module singletons: one per tab)                  */
/* ------------------------------------------------------------------ */

const RECHECK_AFTER_MS = 20_000;

let lastCheckedToken: string | null = null;
let lastCheckedAt = 0;
let inflight: Promise<void> | null = null;
let expiryTimer: ReturnType<typeof setTimeout> | undefined;
let lifecycleStarted = false;

function sameAccount(a: Account, b: Account): boolean {
  return (
    a.id === b.id &&
    a.kind === b.kind &&
    a.display_name === b.display_name &&
    a.persona_id === b.persona_id &&
    a.email === b.email &&
    a.initials === b.initials &&
    (a.org ?? null) === (b.org ?? null)
  );
}

/**
 * Background check with GET /api/auth/me. A 401 ends the tab's session; network errors,
 * timeouts and other statuses keep it (an offline API must never sign the presenter out).
 */
function checkSession(force: boolean): Promise<void> {
  const session = getSession();
  if (!session) return Promise.resolve();
  if (!force && lastCheckedToken === session.token && Date.now() - lastCheckedAt < RECHECK_AFTER_MS) return Promise.resolve();
  if (inflight) return inflight;
  const token = session.token;
  inflight = (async () => {
    try {
      const me = await getJSON<MeResponse>("/api/auth/me", {
        auth: false,
        headers: { Authorization: `Bearer ${token}` },
        timeoutMs: 8_000,
      });
      lastCheckedToken = token;
      lastCheckedAt = Date.now();
      const latest = getSession();
      if (latest?.token === token && me && isAccount(me.account)) {
        const expiresAt = me.expires_at ?? latest.expires_at;
        if (!sameAccount(latest.account, me.account) || expiresAt !== latest.expires_at) {
          setSession({ token, account: me.account, expires_at: expiresAt });
        }
      }
    } catch (err) {
      if (isApiError(err) && err.kind === "http" && err.status === 401 && getSession()?.token === token) {
        clearSession();
        toast("Signed out", { description: "This tab's session ended. Sign in again to continue." });
      }
    } finally {
      inflight = null;
    }
  })();
  return inflight;
}

function scheduleExpiry(): void {
  if (expiryTimer !== undefined) clearTimeout(expiryTimer);
  expiryTimer = undefined;
  const session = getSession();
  const exp = session ? sessionExpiresAt(session) : null;
  if (!session || exp === null) return;
  const wait = Math.min(Math.max(exp - Date.now(), 0) + 250, 2_000_000_000);
  expiryTimer = setTimeout(() => {
    clearSession();
    toast("Session ended", { description: `Sessions last 12 hours. Sign in again to continue.` });
  }, wait);
}

/**
 * DEV-ONLY: `?dev_token=<token>` signs this tab in with an existing token (used by headless
 * screenshots). The whole branch is removed from production builds (NODE_ENV is inlined).
 */
export function devTokenPending(): boolean {
  if (process.env.NODE_ENV !== "development" || typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).has("dev_token");
}

function consumeDevToken(): void {
  if (process.env.NODE_ENV !== "development" || typeof window === "undefined") return;
  const url = new URL(window.location.href);
  const token = url.searchParams.get("dev_token");
  if (!token) return;
  const strip = () => {
    url.searchParams.delete("dev_token");
    window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
  };
  void getJSON<MeResponse>("/api/auth/me", { auth: false, headers: { Authorization: `Bearer ${token}` }, timeoutMs: 8_000 })
    .then((me) => {
      if (me && isAccount(me.account)) {
        lastCheckedToken = token;
        lastCheckedAt = Date.now();
        setSession({ token, account: me.account, expires_at: me.expires_at });
      }
    })
    .catch(() => undefined)
    .finally(() => {
      strip();
      emitDevDone();
    });
}

const devListeners = new Set<() => void>();
function emitDevDone(): void {
  devListeners.forEach((l) => l());
}
/** Re-render when the dev token check finishes (only meaningful in development). */
export function useDevTokenPending(): boolean {
  return React.useSyncExternalStore(
    (l) => {
      devListeners.add(l);
      return () => devListeners.delete(l);
    },
    devTokenPending,
    () => false,
  );
}

function startLifecycle(): void {
  if (lifecycleStarted || typeof window === "undefined") return;
  lifecycleStarted = true;
  consumeDevToken();
  const onReturn = () => {
    if (document.visibilityState === "visible") void checkSession(false);
  };
  // Switching back to this tab re-checks quietly (e.g. it was signed out from elsewhere).
  document.addEventListener("visibilitychange", onReturn);
  window.addEventListener("focus", onReturn);
  window.addEventListener("pageshow", (e) => {
    if (e.persisted) void checkSession(true);
  });
  onSessionCheckRequested(() => void checkSession(true));
  subscribeSession(scheduleExpiry);
  scheduleExpiry();
  void checkSession(true);
}

async function signIn(email: string, password: string): Promise<Account> {
  const res = await postJSON<LoginResponse>("/api/auth/login", { email, password }, { auth: false });
  if (!res || typeof res.token !== "string" || !isAccount(res.account)) {
    throw new Error("Unexpected response from sign-in");
  }
  lastCheckedToken = res.token;
  lastCheckedAt = Date.now();
  setSession({ token: res.token, account: res.account, expires_at: res.expires_at });
  return res.account;
}

async function signUp(input: SignUpInput): Promise<Account> {
  const res = await postJSON<LoginResponse>("/api/auth/register", input, { auth: false });
  if (!res || typeof res.token !== "string" || !isAccount(res.account)) {
    throw new Error("Unexpected response from sign-up");
  }
  lastCheckedToken = res.token;
  lastCheckedAt = Date.now();
  setSession({ token: res.token, account: res.account, expires_at: res.expires_at });
  return res.account;
}

async function signOut(): Promise<void> {
  const token = getSession()?.token ?? null;
  clearSession();
  lastCheckedToken = null;
  if (!token) return;
  try {
    await postJSON("/api/auth/logout", {}, { auth: false, headers: { Authorization: `Bearer ${token}` }, timeoutMs: 4_000 });
  } catch {
    // API offline: the token still expires on its own
  }
}

const refresh = (): Promise<void> => checkSession(true);

/* ------------------------------------------------------------------ */
/* React bindings                                                      */
/* ------------------------------------------------------------------ */

const getServerSnapshot = (): Session | null | undefined => undefined;

function useSessionSnapshot(): Session | null | undefined {
  return React.useSyncExternalStore<Session | null | undefined>(subscribeSession, getSession, getServerSnapshot);
}

/**
 * Starts the per-tab session lifecycle (background /me check, re-check when the tab regains
 * focus, expiry timer). `useAccount()` works with or without it; render it once near the root.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  React.useEffect(startLifecycle, []);
  return <>{children}</>;
}

/**
 * This tab's account. `status` is "loading" during the server render and hydration, then
 * "signed_in" or "signed_out" (read synchronously from sessionStorage, so a reload never
 * flashes the signed-out state).
 */
export function useAccount(): AuthState {
  const session = useSessionSnapshot();
  React.useEffect(startLifecycle, []);
  return React.useMemo<AuthState>(() => {
    const status: AuthStatus = session === undefined ? "loading" : session ? "signed_in" : "signed_out";
    return {
      status,
      account: session?.account ?? null,
      token: session?.token ?? null,
      expiresAt: session ? sessionExpiresAt(session) : null,
      signIn,
      signUp,
      signOut,
      refresh,
    };
  }, [session]);
}
