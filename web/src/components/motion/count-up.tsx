"use client";

import * as React from "react";
import { animate, useInView } from "motion/react";
import { cn } from "@/lib/utils";
import { EASE_OUT, useLatest, useReducedMotionSafe } from "./use-motion-env";

export interface CountUpProps {
  /**
   * A REAL number only: from the API, ml/artifacts/metrics.json, data/processed (with provenance)
   * or a VERIFIED item in docs/research/stats.md. Never pass a placeholder.
   */
  value: number;
  /** fraction digits (default 0) */
  decimals?: number;
  /** seconds (default 0.8; the brief allows 0.6-0.9) */
  duration?: number;
  /** seconds before counting starts (default 0) */
  delay?: number;
  /** start value (default 0) */
  from?: number;
  prefix?: string;
  suffix?: string;
  /** Count when this is true and the number is on screen (default true). */
  play?: boolean;
  locale?: string;
  className?: string;
}

/**
 * Counts up to a real value in tabular figures when it scrolls into view.
 * The server HTML already holds the final value (no-JS and reduced motion show it as is);
 * screen readers always read the final value. Updates write the existing text node directly,
 * so there is no React re-render per frame.
 */
export function CountUp({
  value,
  decimals = 0,
  duration = 0.8,
  delay = 0,
  from = 0,
  prefix = "",
  suffix = "",
  play = true,
  locale = "en-US",
  className,
}: CountUpProps) {
  const reduced = useReducedMotionSafe();
  const viewRef = React.useRef<HTMLSpanElement>(null);
  const textRef = React.useRef<HTMLSpanElement>(null);
  const inView = useInView(viewRef, { once: true, margin: "0px 0px -8% 0px" });
  const format = React.useMemo(() => {
    const nf = new Intl.NumberFormat(locale, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
    return (n: number) => `${prefix}${nf.format(n)}${suffix}`;
  }, [locale, decimals, prefix, suffix]);
  const formatRef = useLatest(format);
  const finalText = format(value);
  const run = play && inView && !reduced && Number.isFinite(value);

  React.useEffect(() => {
    const node = textRef.current?.firstChild;
    if (!run || !node || node.nodeType !== Node.TEXT_NODE) return;
    const write = (n: number) => {
      node.nodeValue = formatRef.current(n);
    };
    write(from);
    const controls = animate(from, value, { duration, delay, ease: EASE_OUT, onUpdate: write });
    return () => {
      controls.stop();
      write(value);
    };
  }, [run, from, value, duration, delay, formatRef]);

  return (
    <span ref={viewRef} className={cn("tabular-nums", className)}>
      <span ref={textRef} aria-hidden="true">
        {finalText}
      </span>
      <span className="sr-only">{finalText}</span>
    </span>
  );
}
