"use client";

import * as React from "react";
import { useReducedMotionConfig } from "motion/react";

/** The brief's plotter ease: cubic-bezier(0.65, 0, 0.35, 1). */
export const EASE_PLOT = [0.65, 0, 0.35, 1] as const;
/** Settle ease for small UI moves. */
export const EASE_OUT = [0.22, 1, 0.36, 1] as const;

/**
 * True when motion should be skipped (OS "reduce motion", honored through
 * <MotionConfig reducedMotion="user">). False on the server and during hydration.
 */
export function useReducedMotionSafe(): boolean {
  return useReducedMotionConfig() ?? false;
}

const noopSubscribe = () => () => undefined;

/** False during SSR and hydration, true afterwards (no setState-in-effect needed). */
export function useHydrated(): boolean {
  return React.useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
}

/** matchMedia as an external store; `serverValue` is used for SSR and hydration. */
export function useMediaQuery(query: string, serverValue = false): boolean {
  const subscribe = React.useCallback(
    (onChange: () => void) => {
      const mql = window.matchMedia(query);
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    },
    [query],
  );
  return React.useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => serverValue,
  );
}

/**
 * Seconds to wait so a JS-driven move starts `at` seconds after navigation start, in step
 * with the CSS first-paint moves. Call it inside effects only (it reads the clock).
 */
export function delayFromNavStart(at: number, min = 0): number {
  if (typeof performance === "undefined") return Math.max(min, at);
  return Math.max(min, at - performance.now() / 1000);
}

/** Keeps the latest value in a ref without writing refs during render. */
export function useLatest<T>(value: T): React.RefObject<T> {
  const ref = React.useRef(value);
  React.useLayoutEffect(() => {
    ref.current = value;
  });
  return ref;
}

/** Element size via ResizeObserver (0 x 0 until measured on the client). */
export function useElementSize<T extends Element>(): [React.RefCallback<T>, { width: number; height: number }] {
  const [size, setSize] = React.useState({ width: 0, height: 0 });
  const observer = React.useRef<ResizeObserver | null>(null);
  const ref = React.useCallback((node: T | null) => {
    observer.current?.disconnect();
    observer.current = null;
    if (!node) return;
    const ro = new ResizeObserver((entries) => {
      const box = entries[0]?.contentRect;
      if (!box) return;
      const width = Math.round(box.width);
      const height = Math.round(box.height);
      setSize((prev) => (prev.width === width && prev.height === height ? prev : { width, height }));
    });
    ro.observe(node);
    observer.current = ro;
  }, []);
  return [ref, size];
}
