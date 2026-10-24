/**
 * Per-tab sessions (docs/CONTRACTS.md section 13).
 *
 * The session lives in sessionStorage under "foothold.session" as {token, account, expires_at?}.
 * sessionStorage is scoped to one browser tab, so each tab signs in on its own: signing into
 * another account in a second tab never touches this one, and a reload keeps the tab's account.
 * Never cookies or localStorage.
 *
 * SSR-safe (every browser access is guarded) and free of React/API imports, so lib/api.ts can
 * read the token without an import cycle. React code should use `useAccount()` from
 * components/auth instead of calling these directly.
 */

export type AccountKind = "learner" | "employer";

/** Account shape returned by the API (CONTRACTS section 13). All demo accounts are fictional. */
export interface Account {
  id: string;
  kind: AccountKind;
  display_name: string;
  persona_id: string;
  email: string;
  initials: string;
  org?: string | null;
}

export interface Session {
  token: string;
  account: Account;
  /** ISO-8601 expiry from the API (the token carries it too) */
  expires_at?: string;
}

export const SESSION_STORAGE_KEY = "foothold.session";

/** Session length issued by the API (12 h). */
export const SESSION_HOURS = 12;

/* ------------------------------------------------------------------ */
/* Validation                                                          */
/* ------------------------------------------------------------------ */

function isNonEmptyString(v: unknown): v is string {
  return typeof v === "string" && v.length > 0;
}

export function isAccount(value: unknown): value is Account {
  if (!value || typeof value !== "object") return false;
  const a = value as Record<string, unknown>;
  return (
    isNonEmptyString(a.id) &&
    (a.kind === "learner" || a.kind === "employer") &&
    isNonEmptyString(a.display_name) &&
    isNonEmptyString(a.persona_id) &&
    isNonEmptyString(a.email) &&
    isNonEmptyString(a.initials) &&
    (a.org === undefined || a.org === null || typeof a.org === "string")
  );
}

function parseSession(raw: string | null): Session | null {
  if (!raw) return null;
  try {
    const v = JSON.parse(raw) as Record<string, unknown>;
    if (!v || typeof v !== "object" || !isNonEmptyString(v.token) || !isAccount(v.account)) return null;
    return {
      token: v.token,
      account: v.account,
      expires_at: typeof v.expires_at === "string" ? v.expires_at : undefined,
    };
  } catch {
    return null;
  }
}

/* ------------------------------------------------------------------ */
/* Expiry (read from the token payload; the API does the verifying)    */
/* ------------------------------------------------------------------ */

function base64UrlDecode(part: string): string | null {
  try {
    const b64 = part.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(part.length / 4) * 4, "=");
    return atob(b64);
  } catch {
    return null;
  }
}

/** Expiry of a session in epoch ms, from `expires_at` or the token's `exp` claim. */
export function sessionExpiresAt(session: Pick<Session, "token" | "expires_at">): number | null {
  if (session.expires_at) {
    const t = Date.parse(session.expires_at);
    if (Number.isFinite(t)) return t;
  }
  const body = session.token.split(".")[0];
  const json = body ? base64UrlDecode(body) : null;
  if (!json) return null;
  try {
    const exp = (JSON.parse(json) as { exp?: unknown }).exp;
    return typeof exp === "number" && Number.isFinite(exp) ? exp * 1000 : null;
  } catch {
    return null;
  }
}

export function isSessionExpired(session: Pick<Session, "token" | "expires_at">, now: number = Date.now()): boolean {
  const exp = sessionExpiresAt(session);
  return exp !== null && exp <= now;
}

/* ------------------------------------------------------------------ */
/* Store: sessionStorage + in-memory copy + same-tab listeners         */
/* ------------------------------------------------------------------ */

const listeners = new Set<() => void>();
const revalidators = new Set<() => void>();
let loaded = false;
let current: Session | null = null;

function emit(): void {
  listeners.forEach((l) => l());
}

function load(): void {
  if (loaded || typeof window === "undefined") return;
  loaded = true;
  try {
    current = parseSession(window.sessionStorage.getItem(SESSION_STORAGE_KEY));
  } catch {
    current = null; // storage blocked: memory-only session for this page view
  }
}

/** This tab's session, or null (always null on the server and once expired). Stable identity between changes. */
export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  load();
  if (current && isSessionExpired(current)) return null;
  return current;
}

/** Bearer token for API calls, or null. */
export function getSessionToken(): string | null {
  return getSession()?.token ?? null;
}

export function setSession(session: Session): void {
  if (typeof window === "undefined") return;
  loaded = true;
  current = { token: session.token, account: session.account, expires_at: session.expires_at };
  try {
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(current));
  } catch {
    // storage blocked: keep the in-memory session for this page view
  }
  emit();
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  loaded = true;
  const had = current !== null;
  current = null;
  try {
    window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
  } catch {
    // ignore
  }
  if (had) emit();
}

/** Subscribe to sign-in / sign-out in this tab (useSyncExternalStore-compatible). */
export function subscribeSession(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Ask the auth layer to re-check the session with the API (lib/api.ts calls this after a 401). */
export function requestSessionCheck(): void {
  revalidators.forEach((r) => r());
}

export function onSessionCheckRequested(listener: () => void): () => void {
  revalidators.add(listener);
  return () => {
    revalidators.delete(listener);
  };
}

/* ------------------------------------------------------------------ */
/* Routing helpers                                                     */
/* ------------------------------------------------------------------ */

/** Sheets that need an account of a given kind (CONTRACTS section 13). Everything else is public. */
const KIND_ROUTES: Readonly<Record<AccountKind, readonly string[]>> = {
  learner: ["/sim", "/path", "/graph", "/circle", "/inbox"],
  employer: ["/employers"],
};

function matchesRoute(pathname: string, route: string): boolean {
  return pathname === route || pathname.startsWith(`${route}/`);
}

/** The account kind a path is for, or null when it is public (/, /lab, /about, /signin ...). */
export function routeKind(pathname: string): AccountKind | null {
  for (const kind of ["learner", "employer"] as const) {
    if (KIND_ROUTES[kind].some((r) => matchesRoute(pathname, r))) return kind;
  }
  return null;
}

/** Where an account lands after sign-in: learners on SIM, employers on EMPLOYERS. */
export function homeFor(account: Pick<Account, "kind"> | null | undefined): string {
  if (account?.kind === "employer") return "/employers";
  if (account?.kind === "learner") return "/sim";
  return "/";
}

/** "Learner" or "Employer · Tri-Valley Freight". */
export function roleLabel(account: Pick<Account, "kind" | "org">): string {
  if (account.kind === "employer") return account.org ? `Employer · ${account.org}` : "Employer";
  return "Learner";
}

const LOCAL_ORIGIN = "http://foothold.invalid";

function hasControlCharOrBackslash(s: string): boolean {
  for (let i = 0; i < s.length; i += 1) {
    const c = s.charCodeAt(i);
    if (c < 0x20 || c === 0x7f || c === 0x5c) return true;
  }
  return false;
}

/** A same-site path from an untrusted `?next=` value, or null (absolute URLs, //host, /signin itself). */
export function safeNextPath(next: string | null | undefined): string | null {
  if (!next) return null;
  const raw = next.trim();
  if (!raw.startsWith("/") || raw.startsWith("//") || hasControlCharOrBackslash(raw)) return null;
  try {
    const url = new URL(raw, LOCAL_ORIGIN);
    if (url.origin !== LOCAL_ORIGIN) return null;
    if (matchesRoute(url.pathname, "/signin") || matchesRoute(url.pathname, "/signup")) return null;
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return null;
  }
}

/** "/signin?next=/inbox" (or plain "/signin" when there is nowhere useful to return to). */
export function signInHref(next?: string | null): string {
  const safe = safeNextPath(next);
  return safe && safe !== "/" ? `/signin?next=${encodeURIComponent(safe)}` : "/signin";
}

/** Post-sign-in destination: `next` if this account can open it, else the account's home. */
export function destinationFor(account: Pick<Account, "kind">, next?: string | null): string {
  const safe = safeNextPath(next);
  if (!safe) return homeFor(account);
  const kind = routeKind(safe.split(/[?#]/)[0]);
  if (kind && kind !== account.kind) return homeFor(account);
  return safe === "/" ? homeFor(account) : safe;
}

/* ------------------------------------------------------------------ */
/* Demo accounts (FICTIONAL)                                           */
/* ------------------------------------------------------------------ */

export interface DemoAccount {
  persona_id: string;
  kind: AccountKind;
  display_name: string;
  initials: string;
  org?: string;
  email: string;
  password: string;
  /** one-line situation */
  note: string;
}

/**
 * Fictional demo logins for the presenter's click-to-fill list on /signin. They mirror
 * DEMO_IDENTITIES in api/foothold/auth.py (emails on reserved example domains).
 */
export const DEMO_ACCOUNTS: readonly DemoAccount[] = [
  {
    persona_id: "maya",
    kind: "learner",
    display_name: "Maya Ortiz",
    initials: "MO",
    email: "maya.ortiz@example.com",
    password: "valley-maya-01",
    note: "High-school junior, first-gen, aiming for a UC",
  },
  {
    persona_id: "dev",
    kind: "learner",
    display_name: "Dev Sandhu",
    initials: "DS",
    email: "dev.sandhu@example.com",
    password: "valley-dev-02",
    note: "Warehouse picker, role being automated",
  },
  {
    persona_id: "luis",
    kind: "learner",
    display_name: "Luis Navarro",
    initials: "LN",
    email: "luis.navarro@example.com",
    password: "valley-luis-03",
    note: "High-school senior, diesel and farm equipment",
  },
  {
    persona_id: "tri_valley_freight",
    kind: "employer",
    display_name: "Tri-Valley Freight",
    initials: "TVF",
    org: "Tri-Valley Freight",
    email: "hiring@trivalleyfreight.example.org",
    password: "valley-freight-04",
    note: "Logistics employer, hiring through blind cards",
  },
];
