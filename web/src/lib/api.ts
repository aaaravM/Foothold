/**
 * Foothold web -> API client (docs/CONTRACTS.md sections 2, 6 and 9).
 *
 * - `getJSON` / `postJSON`: fetch with a timeout and typed `ApiError`s.
 * - `streamSSE`: POST a body and read the `text/event-stream` response with
 *   fetch + ReadableStream (not EventSource), parsing `event:` / `data:` lines
 *   across chunk boundaries, several events per chunk.
 *
 * Every page must degrade gracefully when the API is down: check
 * `isOfflineError(err)` and show "API offline" instead of crashing.
 *
 * Auth (CONTRACTS section 13): when this tab has a session, every request to the
 * Foothold API carries `Authorization: Bearer <token>` automatically (never sent to
 * other hosts). Pass `{ auth: false }` to skip it. A 401 on a request that carried
 * the token asks the auth layer to re-check the session with GET /api/auth/me.
 */
import { getSessionToken, requestSessionCheck } from "./auth";
import type { TraceEvent } from "./types";

/** Build-time fallback base (NEXT_PUBLIC_API_URL, else localhost). Prefer `resolveApiBase()`. */
export const API_URL: string = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

/* ------------------------------------------------------------------ */
/* Runtime API discovery                                               */
/* ------------------------------------------------------------------ */

export type ApiBaseSource = "query" | "localStorage" | "supabase" | "env" | "default";
export interface ApiBaseInfo {
  url: string;
  source: ApiBaseSource;
}

const API_STORAGE_KEY = "foothold.api";
const SUPABASE_URL = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/+$/, "");
const SUPABASE_KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";
const SUPABASE_TIMEOUT_MS = 2_000;

let resolvedBase: ApiBaseInfo | null = null;
let resolvingBase: Promise<ApiBaseInfo> | null = null;

function cleanBase(value: string | null | undefined): string | null {
  const v = (value ?? "").trim().replace(/\/+$/, "");
  return /^https?:\/\/[^\s/]+/i.test(v) ? v : null;
}

function readStoredBase(): string | null {
  try {
    return cleanBase(window.localStorage.getItem(API_STORAGE_KEY));
  } catch {
    return null;
  }
}

/** ?api=<url> saves an override for this browser; ?api=clear removes it. Returns the override, if any. */
function readQueryBase(): string | null {
  let param: string | null = null;
  try {
    param = new URLSearchParams(window.location.search).get("api");
  } catch {
    return null;
  }
  if (param === null) return null;
  if (param.trim().toLowerCase() === "clear") {
    try {
      window.localStorage.removeItem(API_STORAGE_KEY);
    } catch {
      // storage blocked: nothing to clear
    }
    return null;
  }
  const url = cleanBase(param);
  if (url) {
    try {
      window.localStorage.setItem(API_STORAGE_KEY, url);
    } catch {
      // storage blocked: the override still applies to this page load
    }
  }
  return url;
}

/** The API's current public URL from Supabase public_config (key 'api_url'). Null on any failure. */
async function readSupabaseBase(): Promise<string | null> {
  if (!SUPABASE_URL || !SUPABASE_KEY || process.env.NODE_ENV === "development") return null;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), SUPABASE_TIMEOUT_MS);
  try {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/public_config?key=eq.api_url&select=value`, {
      headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}`, Accept: "application/json" },
      signal: controller.signal,
      cache: "no-store",
    });
    if (!res.ok) return null;
    const rows = (await res.json()) as { value?: unknown }[];
    const value = Array.isArray(rows) && rows[0] && typeof rows[0].value === "string" ? rows[0].value : null;
    return cleanBase(value);
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Where the Foothold API lives, resolved once per page load:
 * ?api=<url> (saved to localStorage 'foothold.api'; ?api=clear removes it) -> localStorage ->
 * Supabase public_config 'api_url' (2 s timeout; skipped in development) -> NEXT_PUBLIC_API_URL -> http://localhost:8000.
 */
export function resolveApiBaseInfo(): Promise<ApiBaseInfo> {
  if (resolvedBase) return Promise.resolve(resolvedBase);
  if (typeof window === "undefined") return Promise.resolve({ url: API_URL, source: process.env.NEXT_PUBLIC_API_URL ? "env" : "default" });
  if (!resolvingBase) {
    resolvingBase = (async (): Promise<ApiBaseInfo> => {
      const fromQuery = readQueryBase();
      if (fromQuery) return { url: fromQuery, source: "query" };
      const stored = readStoredBase();
      if (stored) return { url: stored, source: "localStorage" };
      const remote = await readSupabaseBase();
      if (remote) return { url: remote, source: "supabase" };
      return { url: API_URL, source: process.env.NEXT_PUBLIC_API_URL ? "env" : "default" };
    })().then((info) => {
      resolvedBase = info;
      return info;
    });
  }
  return resolvingBase;
}

/** The resolved API base URL (memoized). */
export async function resolveApiBase(): Promise<string> {
  return (await resolveApiBaseInfo()).url;
}

/** Best current guess without waiting (the resolved base once known, else the build-time fallback). */
export function currentApiBase(): string {
  return resolvedBase?.url ?? API_URL;
}

export const DEFAULT_TIMEOUT_MS = 15_000;

export type ApiErrorKind =
  /** fetch rejected: API not running, DNS, CORS, connection reset */
  | "network"
  /** no response within the timeout */
  | "timeout"
  /** non-2xx response */
  | "http"
  /** response body was not the JSON we expected */
  | "parse"
  /** the caller's AbortSignal fired */
  | "aborted";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  readonly url: string;
  /** parsed JSON (or text) body for `http` errors; FastAPI puts the reason in `detail` */
  readonly body?: unknown;

  constructor(kind: ApiErrorKind, message: string, url: string, options?: { status?: number; body?: unknown; cause?: unknown }) {
    super(message, options?.cause !== undefined ? { cause: options.cause } : undefined);
    this.name = "ApiError";
    this.kind = kind;
    this.url = url;
    this.status = options?.status;
    this.body = options?.body;
  }

  /** FastAPI-style `{detail}` if present, else the message. */
  get detail(): string {
    const b = this.body;
    if (b && typeof b === "object" && "detail" in b) {
      const d = (b as { detail: unknown }).detail;
      if (typeof d === "string") return d;
      try {
        return JSON.stringify(d);
      } catch {
        return this.message;
      }
    }
    return this.message;
  }
}

export function isApiError(err: unknown): err is ApiError {
  return err instanceof ApiError;
}

/** True when the API looks unreachable (show "API offline"). */
export function isOfflineError(err: unknown): boolean {
  return isApiError(err) && (err.kind === "network" || err.kind === "timeout");
}

/** True when the caller cancelled (ignore it in UI). */
export function isAbortError(err: unknown): boolean {
  if (isApiError(err)) return err.kind === "aborted";
  return err instanceof DOMException && err.name === "AbortError";
}

/** Absolute URL for an API path ("/api/meta/careers" or "/health"). Absolute URLs pass through. */
export function apiUrl(path: string, base: string = currentApiBase()): string {
  if (/^https?:\/\//i.test(path)) return path;
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

export interface RequestOptions {
  /** default 15 000 ms; 0 disables the timeout */
  timeoutMs?: number;
  signal?: AbortSignal;
  headers?: Record<string, string>;
  /** attach this tab's session token (default true; only ever sent to the resolved API base) */
  auth?: boolean;
}

/** This tab's session token, for requests to our own API only. */
function sessionTokenFor(url: string, base: string, enabled: boolean | undefined): string | null {
  if (enabled === false) return null;
  if (url !== base && !url.startsWith(`${base}/`)) return null;
  return getSessionToken();
}

function authHeader(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

interface LinkedAbort {
  signal: AbortSignal;
  timedOut: () => boolean;
  /** restart the timer (used by streams as an idle timeout) */
  touch: () => void;
  /** stop the timer without aborting (e.g. once response headers arrived) */
  disarm: () => void;
  cleanup: () => void;
}

/** One AbortSignal that fires on the caller's signal or on our timer. */
function linkAbort(outer: AbortSignal | undefined, timeoutMs: number): LinkedAbort {
  const controller = new AbortController();
  let timedOut = false;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const arm = () => {
    if (timeoutMs > 0) {
      if (timer !== undefined) clearTimeout(timer);
      timer = setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, timeoutMs);
    }
  };
  const onOuterAbort = () => controller.abort();

  if (outer) {
    if (outer.aborted) controller.abort();
    else outer.addEventListener("abort", onOuterAbort, { once: true });
  }
  arm();

  const disarm = () => {
    if (timer !== undefined) clearTimeout(timer);
    timer = undefined;
  };

  return {
    signal: controller.signal,
    timedOut: () => timedOut,
    touch: arm,
    disarm,
    cleanup: () => {
      disarm();
      outer?.removeEventListener("abort", onOuterAbort);
    },
  };
}

async function readBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function requestJSON<T>(method: "GET" | "POST" | "PUT", path: string, body: unknown, options: RequestOptions = {}): Promise<T> {
  const base = await resolveApiBase();
  const url = apiUrl(path, base);
  const token = sessionTokenFor(url, base, options.auth);
  const link = linkAbort(options.signal, options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  try {
    let res: Response;
    try {
      res = await fetch(url, {
        method,
        headers: {
          Accept: "application/json",
          ...(method !== "GET" ? { "Content-Type": "application/json" } : {}),
          ...authHeader(token),
          ...options.headers,
        },
        body: method !== "GET" ? JSON.stringify(body ?? {}) : undefined,
        signal: link.signal,
        cache: "no-store",
      });
    } catch (cause) {
      if (link.timedOut()) throw new ApiError("timeout", `Request timed out: ${method} ${path}`, url, { cause });
      if (options.signal?.aborted) throw new ApiError("aborted", "Request cancelled", url, { cause });
      throw new ApiError("network", `API unreachable at ${base}`, url, { cause });
    }

    if (!res.ok) {
      if (res.status === 401 && token) requestSessionCheck();
      const errBody = await readBody(res).catch(() => undefined);
      throw new ApiError("http", `${method} ${path} failed with HTTP ${res.status}`, url, { status: res.status, body: errBody });
    }
    if (res.status === 204) return undefined as T;

    let text: string;
    try {
      text = await res.text();
    } catch (cause) {
      if (link.timedOut()) throw new ApiError("timeout", `Response timed out: ${method} ${path}`, url, { cause });
      if (options.signal?.aborted) throw new ApiError("aborted", "Request cancelled", url, { cause });
      throw new ApiError("network", "Connection dropped while reading the response", url, { cause });
    }
    if (!text) return undefined as T;
    try {
      return JSON.parse(text) as T;
    } catch (cause) {
      throw new ApiError("parse", `Invalid JSON from ${method} ${path}`, url, { status: res.status, body: text.slice(0, 500), cause });
    }
  } finally {
    link.cleanup();
  }
}

/** GET a JSON resource. Throws `ApiError`. */
export function getJSON<T>(path: string, options?: RequestOptions): Promise<T> {
  return requestJSON<T>("GET", path, undefined, options);
}

/** POST a JSON body and parse the JSON response. Throws `ApiError`. */
export function postJSON<T>(path: string, body: unknown, options?: RequestOptions): Promise<T> {
  return requestJSON<T>("POST", path, body, options);
}

/** PUT a JSON body and parse the JSON response. Throws `ApiError`. */
export function putJSON<T>(path: string, body: unknown, options?: RequestOptions): Promise<T> {
  return requestJSON<T>("PUT", path, body, options);
}

/* ------------------------------------------------------------------ */
/* Server-sent events over fetch                                       */
/* ------------------------------------------------------------------ */

export interface SSEMessage {
  /** value of the last `event:` field, "message" when absent */
  event: string;
  /** `data:` lines joined with "\n" */
  data: string;
  id?: string;
}

export interface SSEParser {
  /** feed decoded text; may contain partial lines and several events */
  push(chunk: string): void;
  /** flush at end of stream (dispatches a final event that lacks its blank line) */
  end(): void;
}

/**
 * Incremental parser for the text/event-stream format (WHATWG HTML, "Server-sent events").
 * Handles \n, \r\n and \r line endings (including a \r\n split across chunks),
 * comment lines (":"), multi-line data and the optional space after the colon.
 */
export function createSSEParser(onMessage: (msg: SSEMessage) => void): SSEParser {
  let buffer = "";
  let eventType = "";
  let dataLines: string[] = [];
  let lastEventId: string | undefined;

  const dispatch = () => {
    if (dataLines.length > 0) {
      onMessage({ event: eventType || "message", data: dataLines.join("\n"), id: lastEventId });
    }
    eventType = "";
    dataLines = [];
  };

  const processLine = (line: string) => {
    if (line === "") {
      dispatch();
      return;
    }
    if (line.charCodeAt(0) === 58 /* ":" comment */) return;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.charCodeAt(0) === 32 /* " " */) value = value.slice(1);
    switch (field) {
      case "event":
        eventType = value;
        break;
      case "data":
        dataLines.push(value);
        break;
      case "id":
        if (!value.includes("\u0000")) lastEventId = value;
        break;
      default:
        // "retry" and unknown fields are ignored (we do not reconnect).
        break;
    }
  };

  return {
    push(chunk: string) {
      if (!chunk) return;
      buffer += chunk;
      let start = 0;
      let i = 0;
      while (i < buffer.length) {
        const ch = buffer.charCodeAt(i);
        if (ch === 10 /* \n */) {
          processLine(buffer.slice(start, i));
          i += 1;
          start = i;
        } else if (ch === 13 /* \r */) {
          // A trailing \r might be the first half of \r\n: wait for the next chunk.
          if (i + 1 >= buffer.length) break;
          processLine(buffer.slice(start, i));
          i += buffer.charCodeAt(i + 1) === 10 ? 2 : 1;
          start = i;
        } else {
          i += 1;
        }
      }
      buffer = buffer.slice(start);
    },
    end() {
      if (buffer.endsWith("\r")) buffer = buffer.slice(0, -1);
      if (buffer.length > 0) processLine(buffer);
      buffer = "";
      dispatch();
    },
  };
}

export interface StreamOptions {
  /** max wait for response headers (default 15 000 ms) */
  connectTimeoutMs?: number;
  /** max silence between chunks once streaming (default 90 000 ms; 0 disables) */
  idleTimeoutMs?: number;
  headers?: Record<string, string>;
  /** attach this tab's session token (default true; only ever sent to the resolved API base) */
  auth?: boolean;
}

/**
 * POST `body` to `path` and call `onEvent` for every SSE message (CONTRACTS section 6).
 *
 * Resolves when the stream ends or when the caller aborts via `signal`.
 * Rejects with `ApiError` (network / timeout / http) if the request fails.
 * Malformed `data:` payloads are reported as `{type: "error"}` events, not thrown.
 */
export async function streamSSE(
  path: string,
  body: unknown,
  onEvent: (event: TraceEvent) => void,
  signal?: AbortSignal,
  options: StreamOptions = {},
): Promise<void> {
  const base = await resolveApiBase();
  const url = apiUrl(path, base);
  const token = sessionTokenFor(url, base, options.auth);
  const connectTimeout = options.connectTimeoutMs ?? DEFAULT_TIMEOUT_MS;
  const idleTimeout = options.idleTimeoutMs ?? 90_000;
  const link = linkAbort(signal, connectTimeout);

  try {
    let res: Response;
    try {
      res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream", ...authHeader(token), ...options.headers },
        body: JSON.stringify(body ?? {}),
        signal: link.signal,
        cache: "no-store",
      });
    } catch (cause) {
      if (signal?.aborted) return;
      if (link.timedOut()) throw new ApiError("timeout", `No response from ${path}`, url, { cause });
      throw new ApiError("network", `API unreachable at ${base}`, url, { cause });
    }
    // Headers arrived: the connect timeout no longer applies (the idle timeout below takes over).
    link.disarm();

    if (!res.ok) {
      if (res.status === 401 && token) requestSessionCheck();
      const errBody = await readBody(res).catch(() => undefined);
      throw new ApiError("http", `POST ${path} failed with HTTP ${res.status}`, url, { status: res.status, body: errBody });
    }
    if (!res.body) throw new ApiError("parse", "Streaming is not supported by this browser", url);

    // Switch the timer from "connect" to "idle" semantics.
    const idle = linkAbort(link.signal, idleTimeout);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    const parser = createSSEParser((msg) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(msg.data);
      } catch {
        onEvent({ type: "error", message: `Malformed ${msg.event} event from the server` });
        return;
      }
      if (!parsed || typeof parsed !== "object") {
        onEvent({ type: "error", message: `Unexpected ${msg.event} payload from the server` });
        return;
      }
      const record = parsed as Record<string, unknown>;
      if (typeof record.type !== "string") record.type = msg.event;
      onEvent(record as unknown as TraceEvent);
    });

    const onIdleAbort = () => {
      void reader.cancel().catch(() => undefined);
    };
    idle.signal.addEventListener("abort", onIdleAbort, { once: true });

    try {
      for (;;) {
        let chunk: ReadableStreamReadResult<Uint8Array>;
        try {
          chunk = await reader.read();
        } catch (cause) {
          if (signal?.aborted) return;
          if (idle.timedOut()) throw new ApiError("timeout", `Stream from ${path} went silent`, url, { cause });
          throw new ApiError("network", "Connection dropped while streaming", url, { cause });
        }
        if (chunk.done) break;
        if (signal?.aborted) return;
        if (idle.timedOut()) throw new ApiError("timeout", `Stream from ${path} went silent`, url);
        idle.touch();
        parser.push(decoder.decode(chunk.value, { stream: true }));
      }
      if (signal?.aborted) return;
      if (idle.timedOut()) throw new ApiError("timeout", `Stream from ${path} went silent`, url);
      parser.push(decoder.decode());
      parser.end();
    } finally {
      idle.signal.removeEventListener("abort", onIdleAbort);
      idle.cleanup();
      try {
        reader.releaseLock();
      } catch {
        // already released or errored
      }
    }
  } finally {
    link.cleanup();
  }
}
