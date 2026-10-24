"use client";

import * as React from "react";
import { Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  applyTheme,
  getServerThemeSnapshot,
  getThemeSnapshot,
  readPreferredTheme,
  subscribeTheme,
  THEME_LABELS,
  type Theme,
} from "@/lib/theme";

export interface UseThemeResult {
  /** "dark" | "light" (light is shown to people as "Paper") */
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggle: () => void;
}

/**
 * Foothold's theme hook. Use this instead of next-themes' useTheme (there is no next-themes
 * provider; next-themes is only installed as a dependency of shadcn's sonner).
 */
export function useTheme(): UseThemeResult {
  const theme = React.useSyncExternalStore(subscribeTheme, getThemeSnapshot, getServerThemeSnapshot);
  const setTheme = React.useCallback((t: Theme) => applyTheme(t), []);
  const toggle = React.useCallback(() => applyTheme(getThemeSnapshot() === "dark" ? "light" : "dark"), []);
  return { theme, setTheme, toggle };
}

/**
 * Re-applies the preferred theme (?theme= override, else the stored choice) before paint
 * after React's dev-mode remount resets <html> attributes (no-op in production).
 * Rendered once by <Providers>.
 */
export function ThemeSync() {
  React.useLayoutEffect(() => {
    const preferred = readPreferredTheme();
    if (preferred && preferred !== getThemeSnapshot()) applyTheme(preferred, false);
  }, []);
  return null;
}

export interface ThemeToggleProps {
  className?: string;
  /** show the name of the current theme next to the icon */
  showLabel?: boolean;
}

/** Dark ↔ Paper switch. The accessible name says what pressing it will do. */
export function ThemeToggle({ className, showLabel = false }: ThemeToggleProps) {
  const { theme, toggle } = useTheme();
  const next: Theme = theme === "dark" ? "light" : "dark";
  const label = `Switch to ${THEME_LABELS[next].toLowerCase()} theme`;
  return (
    <Button
      type="button"
      variant="ghost"
      size={showLabel ? "sm" : "icon"}
      onClick={toggle}
      aria-label={label}
      className={cn("text-ink-muted hover:text-ink", className)}
    >
      {theme === "dark" ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
      {showLabel ? <span className="label-mono">{THEME_LABELS[theme]}</span> : null}
    </Button>
  );
}
