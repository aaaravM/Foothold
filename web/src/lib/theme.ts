/**
 * Theme store: `data-theme="dark" | "light"` on <html>, persisted in localStorage.
 * The no-flash inline script (components/foothold/theme-script.tsx) applies the
 * stored value before first paint; this module keeps React in sync with it.
 *
 * `?theme=light` / `?theme=dark` in the URL forces a theme for that page view without
 * persisting it (used for screenshots and for sharing a link in the paper theme).
 */

export type Theme = "dark" | "light";

export const THEMES: readonly Theme[] = ["dark", "light"];
export const DEFAULT_THEME: Theme = "dark";
export const THEME_STORAGE_KEY = "foothold-theme";
export const THEME_QUERY_PARAM = "theme";

/** Display names: the light theme is called "paper". */
export const THEME_LABELS: Readonly<Record<Theme, string>> = { dark: "Dark", light: "Paper" };

export function isTheme(value: unknown): value is Theme {
  return value === "dark" || value === "light";
}

/**
 * Inline, dependency-free script for <head>. Keep it tiny and exception-safe.
 * Order: ?theme= query param, then localStorage, then the default.
 */
export const THEME_INIT_SCRIPT = `(function(){var t="${DEFAULT_THEME}";try{var m=/[?&]${THEME_QUERY_PARAM}=(dark|light)(?:&|#|$)/.exec(location.search);if(m){t=m[1]}else{var s=localStorage.getItem("${THEME_STORAGE_KEY}");if(s==="dark"||s==="light")t=s}}catch(e){}document.documentElement.setAttribute("data-theme",t)})()`;

/** Theme forced by the URL (`?theme=light|dark`), if any. */
export function readQueryTheme(): Theme | null {
  if (typeof window === "undefined") return null;
  try {
    const v = new URLSearchParams(window.location.search).get(THEME_QUERY_PARAM);
    return isTheme(v) ? v : null;
  } catch {
    return null;
  }
}

export function readStoredTheme(): Theme | null {
  try {
    const v = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isTheme(v) ? v : null;
  } catch {
    return null;
  }
}

/** What the page should show right now: URL override, else the stored choice, else null (keep current). */
export function readPreferredTheme(): Theme | null {
  return readQueryTheme() ?? readStoredTheme();
}

/** Current theme as rendered on <html>. */
export function getThemeSnapshot(): Theme {
  if (typeof document === "undefined") return DEFAULT_THEME;
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

export function getServerThemeSnapshot(): Theme {
  return DEFAULT_THEME;
}

export function applyTheme(theme: Theme, persist = true): void {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", theme);
  if (persist) {
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // storage blocked (private mode): the theme still applies for this page view
    }
  }
}

export function toggleTheme(): Theme {
  const next: Theme = getThemeSnapshot() === "dark" ? "light" : "dark";
  applyTheme(next);
  return next;
}

/**
 * Subscribe to theme changes from any source: our toggle, the inline script,
 * React's dev remount, or another tab (storage event).
 */
export function subscribeTheme(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => undefined;
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  const onStorage = (e: StorageEvent) => {
    // A URL override wins over choices made in other tabs.
    if (e.key === THEME_STORAGE_KEY && isTheme(e.newValue) && !readQueryTheme()) applyTheme(e.newValue, false);
  };
  window.addEventListener("storage", onStorage);
  return () => {
    observer.disconnect();
    window.removeEventListener("storage", onStorage);
  };
}
