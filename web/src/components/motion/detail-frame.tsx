"use client";

import * as React from "react";
import { motion, useInView } from "motion/react";
import { cn } from "@/lib/utils";
import { EASE_PLOT, useReducedMotionSafe } from "./use-motion-env";

export interface DetailBubbleProps {
  /** detail letter, e.g. "A" */
  letter: string;
  /** sheet where the detail is drawn, e.g. "01" (lower half of the bubble) */
  sheet?: string;
  /** px (default 34) */
  size?: number;
  active?: boolean;
  className?: string;
}

/** Drafting detail bubble: a circle split by a hairline, letter above, sheet number below. */
export function DetailBubble({ letter, sheet, size = 34, active = false, className }: DetailBubbleProps) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "relative inline-flex shrink-0 flex-col items-center justify-center rounded-full border bg-background font-mono leading-none tabular-nums",
        active ? "border-accent text-accent" : "border-ink text-ink",
        className,
      )}
      style={{ width: size, height: size }}
    >
      {sheet ? (
        <>
          <span className="text-[11px] font-semibold">{letter}</span>
          <span className={cn("my-[3px] h-px w-[70%]", active ? "bg-accent" : "bg-ink")} />
          <span className="text-[8px] tracking-[0.08em] text-ink-muted">{sheet}</span>
        </>
      ) : (
        <span className="text-[12px] font-semibold">{letter}</span>
      )}
    </span>
  );
}

type DetailElement = "section" | "div" | "figure" | "article" | "aside";

export interface DetailFrameProps {
  /** detail letter (default "A") */
  letter?: string;
  /** sheet reference shown in the bubble's lower half, e.g. "01" */
  sheet?: string;
  /** short title after "DETAIL A", e.g. "Sample shift" */
  title?: React.ReactNode;
  /** right side of the tag row, e.g. "SCALE NTS" or a ProvenanceBadge */
  meta?: React.ReactNode;
  /** when the frame draws in: on scroll into view (default), on mount, or never (static) */
  draw?: "view" | "mount" | "none";
  /** gold bubble (the active detail) */
  active?: boolean;
  as?: DetailElement;
  id?: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
  className?: string;
  bodyClassName?: string;
  children?: React.ReactNode;
}

const EDGE_TRANSITION = { duration: 0.42, ease: EASE_PLOT };

/**
 * "DETAIL A" frame from drawing conventions, to host a widget or figure: a hairline frame
 * that the pen traces clockwise when it scrolls into view, corner ticks, and a tag row with
 * the detail bubble. Use instead of a generic card. Reduced motion: drawn at once.
 */
export function DetailFrame({
  letter = "A",
  sheet,
  title,
  meta,
  draw = "view",
  active = false,
  as = "section",
  id,
  className,
  bodyClassName,
  children,
  ...aria
}: DetailFrameProps) {
  const reduced = useReducedMotionSafe();
  const ref = React.useRef<HTMLElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.15 });
  const Comp = as as React.ElementType;
  const drawn = reduced || draw === "none" || draw === "mount" || inView;
  const instant = reduced || draw === "none";
  const edge = (delay: number) => (instant ? { duration: 0 } : { ...EDGE_TRANSITION, delay });

  return (
    <Comp ref={ref} id={id} className={cn("relative", className)} {...aria}>
      <span aria-hidden="true" className="pointer-events-none absolute inset-0">
        <motion.span
          className="absolute inset-x-0 top-0 h-px origin-left bg-line-strong"
          initial={instant ? false : { scaleX: 0 }}
          animate={{ scaleX: drawn ? 1 : 0 }}
          transition={edge(0)}
        />
        <motion.span
          className="absolute inset-y-0 right-0 w-px origin-top bg-line-strong"
          initial={instant ? false : { scaleY: 0 }}
          animate={{ scaleY: drawn ? 1 : 0 }}
          transition={edge(0.32)}
        />
        <motion.span
          className="absolute inset-x-0 bottom-0 h-px origin-right bg-line-strong"
          initial={instant ? false : { scaleX: 0 }}
          animate={{ scaleX: drawn ? 1 : 0 }}
          transition={edge(0.6)}
        />
        <motion.span
          className="absolute inset-y-0 left-0 w-px origin-bottom bg-line-strong"
          initial={instant ? false : { scaleY: 0 }}
          animate={{ scaleY: drawn ? 1 : 0 }}
          transition={edge(0.88)}
        />
        {(["-left-[5px] -top-[5px]", "-right-[5px] -top-[5px]", "-left-[5px] -bottom-[5px]", "-right-[5px] -bottom-[5px]"] as const).map((pos, i) => (
          <motion.svg
            key={pos}
            viewBox="0 0 10 10"
            className={cn("absolute size-[10px] text-ink-faint", pos)}
            initial={instant ? false : { opacity: 0 }}
            animate={{ opacity: drawn ? 1 : 0 }}
            transition={instant ? { duration: 0 } : { delay: 0.2 + i * 0.08, duration: 0.2 }}
          >
            <path d="M5 0v10M0 5h10" stroke="currentColor" strokeWidth="1" />
          </motion.svg>
        ))}
      </span>

      <div className="relative flex items-center gap-3 px-4 pt-4 sm:px-5">
        <DetailBubble letter={letter} sheet={sheet} active={active} />
        <p className="label-mono flex min-w-0 flex-wrap items-baseline gap-x-2 text-ink-muted">
          <span className="text-ink">DETAIL {letter}</span>
          {title ? (
            <>
              <span aria-hidden="true" className="text-ink-faint">
                ·
              </span>
              <span className="truncate">{title}</span>
            </>
          ) : null}
        </p>
        {meta ? <div className="label-mono ml-auto flex shrink-0 items-center gap-2 text-ink-faint">{meta}</div> : null}
      </div>
      <div className={cn("relative px-4 pt-4 pb-5 sm:px-5", bodyClassName)}>{children}</div>
    </Comp>
  );
}
