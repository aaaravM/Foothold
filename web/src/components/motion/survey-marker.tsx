"use client";

import * as React from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";
import { useReducedMotionSafe } from "./use-motion-env";

export interface SurveyMarkerProps {
  /** px (default 18) */
  size?: number;
  /** gold: the active benchmark */
  active?: boolean;
  /** increment to fire a ping ring (0 = none yet) */
  ping?: number;
  /** snaps in when this turns true (default true) */
  shown?: boolean;
  /** accessible name when the marker stands alone; omit when a visible label names it */
  label?: string;
  className?: string;
}

/**
 * Survey benchmark symbol (a quartered disc with cross ticks) that snaps in when `shown`
 * and sends out a ping ring each time `ping` increments. Reduced motion: no ping, no snap.
 */
export function SurveyMarker({ size = 18, active = false, ping = 0, shown = true, label, className }: SurveyMarkerProps) {
  const reduced = useReducedMotionSafe();
  return (
    <span
      className={cn("relative inline-flex shrink-0", active ? "text-accent" : "text-ink", className)}
      style={{ width: size, height: size }}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      {!reduced && ping > 0 ? (
        <motion.span
          key={ping}
          className="absolute inset-0 rounded-full border border-accent"
          initial={{ scale: 0.6, opacity: 0.9 }}
          animate={{ scale: 3.4, opacity: 0 }}
          transition={{ duration: 1.25, ease: [0.22, 1, 0.36, 1] }}
        />
      ) : null}
      <motion.svg
        viewBox="0 0 20 20"
        width={size}
        height={size}
        initial={false}
        animate={shown ? { scale: 1, opacity: 1 } : { scale: 0.2, opacity: 0 }}
        transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 560, damping: 24, mass: 0.7 }}
        className="relative overflow-visible"
      >
        <circle cx="10" cy="10" r="5.75" fill="var(--bg)" stroke="currentColor" strokeWidth="1.25" />
        <path d="M10 4.25 A5.75 5.75 0 0 1 15.75 10 H10 Z M10 15.75 A5.75 5.75 0 0 1 4.25 10 H10 Z" fill="currentColor" />
        <path d="M10 0.5v2.75M10 16.75v2.75M0.5 10h2.75M16.75 10h2.75" stroke="currentColor" strokeWidth="1.25" />
      </motion.svg>
    </span>
  );
}
