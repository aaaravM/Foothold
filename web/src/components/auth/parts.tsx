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
export function Brackets(props: BracketsProps) {
  // Corner brackets were part of the old drawing-set look; kept as a no-op so callers don't change.
  void props;
  return null;
}

/** Primary technical button (ink slab, mono return glyph, brackets outside). Pair with <Brackets offset={5} />. */
export const techButtonClass =
  "group/bracket group relative inline-flex h-12 items-center justify-between gap-4 rounded-full bg-ink px-6 text-[0.95rem] font-semibold text-bg " +
  "transition-[background-color,color,opacity,transform] duration-500 [transition-timing-function:var(--ease-expo)] hover:bg-accent hover:text-accent-ink active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-70 " +
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
        "relative grid shrink-0 place-items-center rounded-full bg-accent font-sans leading-none font-semibold text-accent-ink uppercase",
        size === "sm" && "size-7 text-[0.625rem]",
        size === "md" && "size-10 text-[0.7rem]",
        size === "lg" && "size-12 text-xs",
        className,
      )}
    >
      {employer ? <span className="absolute inset-[2px] rounded-full border border-accent-ink/30" /> : null}
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
