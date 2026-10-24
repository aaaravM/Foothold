"use client";

import { THEME_INIT_SCRIPT } from "@/lib/theme";

/**
 * No-flash theme script for <head> (Next.js guide "Preventing flash before hydration").
 * Runs during HTML parsing, before first paint: reads localStorage, defaults to dark.
 *
 * Rendered as text/javascript on the server and text/plain on the client, so React never
 * warns about client-rendered <script> tags (e.g. after Fast Refresh); suppressHydrationWarning
 * covers the type difference. <html> also needs suppressHydrationWarning because this script
 * changes data-theme before React hydrates.
 */
export function ThemeScript() {
  return (
    <script
      id="foothold-theme-init"
      type={typeof window === "undefined" ? "text/javascript" : "text/plain"}
      suppressHydrationWarning
      dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }}
    />
  );
}
