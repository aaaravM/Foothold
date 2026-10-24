import * as React from "react";
import { cn } from "@/lib/utils";

export interface DimensionLineProps {
  /** the measurement text, e.g. "18 MONTHS" or "4.2 KM" */
  label: React.ReactNode;
  orientation?: "horizontal" | "vertical";
  /** "accent" draws the line in gold; default is line-strong */
  tone?: "default" | "accent";
  className?: string;
}

function Arrow({ dir }: { dir: "left" | "right" | "up" | "down" }) {
  const d =
    dir === "left" ? "M7 1 L1 4 L7 7" : dir === "right" ? "M1 1 L7 4 L1 7" : dir === "up" ? "M1 7 L4 1 L7 7" : "M1 1 L4 7 L7 1";
  return (
    <svg viewBox="0 0 8 8" className="size-2 shrink-0" fill="none" stroke="currentColor" strokeWidth={1}>
      <path d={d} />
    </svg>
  );
}

/**
 * Drafting dimension line: |<—— label ——>|.
 * The label is real text (read by screen readers); the arrows and ticks are decorative.
 */
export function DimensionLine({ label, orientation = "horizontal", tone = "default", className }: DimensionLineProps) {
  const stroke = tone === "accent" ? "text-accent" : "text-line-strong";
  if (orientation === "vertical") {
    return (
      <div className={cn("inline-flex h-full min-h-24 flex-col items-center", className)}>
        <span aria-hidden="true" className={cn("h-px w-3 bg-current", stroke)} />
        <span aria-hidden="true" className={cn("flex flex-1 flex-col items-center", stroke)}>
          <Arrow dir="up" />
          <span className="w-px flex-1 bg-current" />
        </span>
        <span className="label-mono py-1 text-ink-muted [writing-mode:vertical-rl]">{label}</span>
        <span aria-hidden="true" className={cn("flex flex-1 flex-col items-center", stroke)}>
          <span className="w-px flex-1 bg-current" />
          <Arrow dir="down" />
        </span>
        <span aria-hidden="true" className={cn("h-px w-3 bg-current", stroke)} />
      </div>
    );
  }
  return (
    <div className={cn("flex w-full items-center", className)}>
      <span aria-hidden="true" className={cn("h-3 w-px bg-current", stroke)} />
      <span aria-hidden="true" className={cn("flex flex-1 items-center", stroke)}>
        <Arrow dir="left" />
        <span className="-ml-px h-px flex-1 bg-current" />
      </span>
      <span className="label-mono shrink-0 px-2 text-ink-muted">{label}</span>
      <span aria-hidden="true" className={cn("flex flex-1 items-center", stroke)}>
        <span className="-mr-px h-px flex-1 bg-current" />
        <Arrow dir="right" />
      </span>
      <span aria-hidden="true" className={cn("h-3 w-px bg-current", stroke)} />
    </div>
  );
}
