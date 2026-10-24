"use client";

import * as React from "react";
import { motion, useReducedMotion } from "motion/react";
import { cn } from "@/lib/utils";
import type { Account } from "@/lib/auth";

/** Plotter easing from docs/DESIGN_DIRECTION.md section 4. */
export const PLOT_EASE = [0.65, 0, 0.35, 1] as const;

/* ------------------------------------------------------------------ */
/* Bracket hover                                                       */
/* ------------------------------------------------------------------ */

export interface BracketsProps {
  className?: string;
  /** keep the brackets drawn (e.g. while a menu is open) */
  active?: boolean;
  /** distance outside the element's box in px (default 1: on a 1px border) */
  offset?: number;
}

/**
 * Corner brackets that snap in (150 ms) when the nearest `group/bracket` ancestor is
 * hovered or keyboard-focused. Decorative; the parent needs `position: relative`.
 */
export function Brackets({ className, active = false, offset = 1 }: BracketsProps) {
  const corner =
    "absolute size-[7px] border-current opacity-0 transition-[opacity,translate] duration-150 ease-out " +
    "group-hover/bracket:translate-x-0 group-hover/bracket:translate-y-0 group-hover/bracket:opacity-100 " +
    "group-focus-visible/bracket:translate-x-0 group-focus-visible/bracket:translate-y-0 group-focus-visible/bracket:opacity-100";
  const on = active ? "translate-x-0 translate-y-0 opacity-100" : undefined;
  return (
    <span aria-hidden="true" className={cn("pointer-events-none absolute text-ink", className)} style={{ inset: -offset }}>
      <span className={cn(corner, "top-0 left-0 -translate-x-1 -translate-y-1 border-t border-l", on)} />
      <span className={cn(corner, "top-0 right-0 translate-x-1 -translate-y-1 border-t border-r", on)} />
      <span className={cn(corner, "bottom-0 left-0 -translate-x-1 translate-y-1 border-b border-l", on)} />
      <span className={cn(corner, "right-0 bottom-0 translate-x-1 translate-y-1 border-r border-b", on)} />
    </span>
  );
}

/** Primary technical button (ink slab, mono return glyph, brackets outside). Pair with <Brackets offset={5} />. */
export const techButtonClass =
  "group/bracket relative inline-flex h-12 items-center justify-between gap-6 bg-ink px-5 text-[0.95rem] font-medium text-bg " +
  "transition-[background-color,color,opacity] duration-150 hover:bg-ink/90 disabled:cursor-not-allowed disabled:opacity-70 " +
  "focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent";

/** Quiet text link whose underline draws left to right on hover/focus. */
export const drawLinkClass =
  "relative inline-flex items-center gap-1.5 text-sm text-ink-muted transition-colors hover:text-ink focus-visible:text-ink " +
  "after:absolute after:inset-x-0 after:-bottom-0.5 after:h-px after:origin-left after:scale-x-0 after:bg-current " +
  "after:transition-transform after:duration-200 after:ease-out hover:after:scale-x-100 focus-visible:after:scale-x-100";

/* ------------------------------------------------------------------ */
/* Initials stamp                                                      */
/* ------------------------------------------------------------------ */

export interface InitialsProps {
  account: Pick<Account, "initials" | "kind">;
  size?: "sm" | "md" | "lg";
  className?: string;
}

/** Initials in a hairline square. Employers get a double rule (an organisation stamp). */
export function Initials({ account, size = "sm", className }: InitialsProps) {
  const employer = account.kind === "employer";
  return (
    <span
      aria-hidden="true"
      className={cn(
        "relative grid shrink-0 place-items-center border border-line-strong bg-surface-2 font-mono leading-none font-medium tracking-[0.04em] text-ink uppercase tabular-nums",
        size === "sm" && "size-7 text-[0.625rem]",
        size === "md" && "size-10 text-[0.7rem]",
        size === "lg" && "size-12 text-xs",
        className,
      )}
    >
      {employer ? <span className="absolute inset-[2px] border border-line" /> : null}
      <span className="relative">{account.initials}</span>
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Plotter path                                                        */
/* ------------------------------------------------------------------ */

export interface PlotPathProps extends Omit<React.SVGProps<SVGPathElement>, "ref" | "pathLength" | "initial" | "animate" | "transition"> {
  d: string;
  delay?: number;
  duration?: number;
}

/** An SVG path drawn by the pen plotter (pathLength 0 -> 1). Final state instantly with reduced motion. */
export function PlotPath({ d, delay = 0, duration = 1.2, ...rest }: PlotPathProps) {
  const reduce = useReducedMotion();
  return (
    <motion.path
      d={d}
      initial={reduce ? false : { pathLength: 0, opacity: 0 }}
      animate={{ pathLength: 1, opacity: 1 }}
      transition={{ pathLength: { delay, duration, ease: PLOT_EASE }, opacity: { delay, duration: 0.01 } }}
      {...(rest as Record<string, unknown>)}
    />
  );
}
