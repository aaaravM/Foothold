"use client";

import * as React from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";

export type StatTone = "accent" | "success" | "warning" | "danger" | "info" | "ink";

const FILL: Record<StatTone, string> = {
  accent: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
  ink: "bg-ink",
};

export interface StatBarProps {
  label: string;
  value: number;
  /** default 100 */
  max?: number;
  tone?: StatTone;
  /** change since the last step, shown as +6 / −3 */
  delta?: number | null;
  /** true when a rising value is bad (e.g. stress): +delta shows as a warning */
  invertDelta?: boolean;
  /** show "value/max" on the right (default true) */
  showValue?: boolean;
  /** custom screen-reader value, default "62 of 100" */
  valueText?: string;
  className?: string;
}

/** Labelled horizontal meter (sim stats, fit scores). Fill animates with Motion; respects reduced motion. */
export function StatBar({
  label,
  value,
  max = 100,
  tone = "accent",
  delta,
  invertDelta = false,
  showValue = true,
  valueText,
  className,
}: StatBarProps) {
  const labelId = React.useId();
  const safeMax = max > 0 ? max : 100;
  const clamped = Math.min(Math.max(Number.isFinite(value) ? value : 0, 0), safeMax);
  const ratio = clamped / safeMax;
  const shown = Math.round(clamped);
  const hasDelta = typeof delta === "number" && delta !== 0;
  const deltaGood = hasDelta && (invertDelta ? (delta as number) < 0 : (delta as number) > 0);

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-baseline justify-between gap-3">
        <span id={labelId} className="label-mono text-ink-muted">
          {label}
        </span>
        <span className="flex items-baseline gap-2 font-mono text-xs tabular-nums">
          {hasDelta ? (
            <span className={deltaGood ? "text-success" : "text-warning"}>
              {(delta as number) > 0 ? `+${delta}` : `−${Math.abs(delta as number)}`}
            </span>
          ) : null}
          {showValue ? (
            <span className="text-ink">
              {shown}
              <span className="text-ink-faint">/{safeMax}</span>
            </span>
          ) : null}
        </span>
      </div>
      <div
        role="meter"
        aria-labelledby={labelId}
        aria-valuemin={0}
        aria-valuemax={safeMax}
        aria-valuenow={clamped}
        aria-valuetext={valueText ?? `${shown} of ${safeMax}`}
        className="relative h-2 overflow-hidden rounded-[1px] bg-surface-2 ring-1 ring-line ring-inset"
      >
        <motion.div
          className={cn("absolute inset-0 origin-left", FILL[tone])}
          initial={false}
          animate={{ scaleX: ratio }}
          transition={{ type: "spring", stiffness: 160, damping: 24, mass: 0.6 }}
        />
        <span aria-hidden="true" className="pointer-events-none absolute inset-0">
          {[25, 50, 75].map((p) => (
            <span key={p} className="absolute inset-y-0 w-px bg-background/60" style={{ left: `${p}%` }} />
          ))}
        </span>
      </div>
    </div>
  );
}
