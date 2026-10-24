"use client";

import * as React from "react";
import { motion, useInView, type MotionValue } from "motion/react";
import { cn } from "@/lib/utils";
import { PlotterPath } from "./plotter-path";
import { EASE_OUT, useReducedMotionSafe } from "./use-motion-env";

export type Point = readonly [number, number];

/** "M x0 y0 L x1 y1 ..." for a leader polyline. */
export function pointsToPath(points: readonly Point[]): string {
  return points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`).join(" ");
}

export interface LeaderPathProps {
  /** polyline in the parent <svg>'s units, drawn from the first point (the anchor) to the last */
  points: readonly Point[];
  /** draw now (default true) */
  play?: boolean;
  /** seconds (default 0) */
  delay?: number;
  /** seconds (default 0.6) */
  duration?: number;
  /** dot at the anchor ("start"), at the label end ("end"), both, or none (default "start") */
  dot?: "start" | "end" | "both" | "none";
  /** drive the drawing yourself (0..1) */
  progress?: MotionValue<number>;
  /** small pen head on the tip while drawing (default false) */
  penHead?: boolean;
  strokeWidth?: number;
  className?: string;
}

/** A drafting leader line (SVG <g>): a thin polyline that draws itself, with terminal dots. */
export function LeaderPath({
  points,
  play = true,
  delay = 0,
  duration = 0.6,
  dot = "start",
  progress,
  penHead = false,
  strokeWidth = 1,
  className,
}: LeaderPathProps) {
  const reduced = useReducedMotionSafe();
  if (points.length < 2) return null;
  const d = pointsToPath(points);
  const first = points[0];
  const last = points[points.length - 1];
  const dots: Array<{ key: string; p: Point; at: number }> = [];
  if (dot === "start" || dot === "both") dots.push({ key: "s", p: first, at: delay });
  if (dot === "end" || dot === "both") dots.push({ key: "e", p: last, at: delay + duration * 0.9 });

  return (
    <g className={className}>
      <PlotterPath d={d} play={play} delay={delay} duration={duration} progress={progress} penHead={penHead} penRadius={2.25} strokeWidth={strokeWidth} />
      {dots.map(({ key, p, at }) => (
        <motion.circle
          key={key}
          cx={p[0]}
          cy={p[1]}
          fill="currentColor"
          initial={reduced ? false : { r: 0 }}
          animate={{ r: play || reduced ? 2.25 : 0 }}
          transition={reduced ? { duration: 0 } : { delay: at, duration: 0.25, ease: EASE_OUT }}
        />
      ))}
    </g>
  );
}

export interface LeaderLineProps extends LeaderPathProps {
  /** classes for the overlay <svg> (it fills its positioned parent) */
  svgClassName?: string;
}

/** LeaderPath in its own overlay <svg> that fills the nearest positioned parent; points are in px. */
export function LeaderLine({ svgClassName, ...props }: LeaderLineProps) {
  return (
    <svg aria-hidden="true" className={cn("pointer-events-none absolute inset-0 h-full w-full overflow-visible", svgClassName)}>
      <LeaderPath {...props} />
    </svg>
  );
}

export interface CalloutBubbleProps {
  n: number | string;
  /** px (default 22) */
  size?: number;
  active?: boolean;
  className?: string;
}

/** Numbered callout bubble: a hairline circle with a mono figure. Decorative (aria-hidden). */
export function CalloutBubble({ n, size = 22, active = false, className }: CalloutBubbleProps) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full border bg-background font-mono text-[10px] leading-none tabular-nums",
        active ? "border-accent text-accent" : "border-line-strong text-ink",
        className,
      )}
      style={{ width: size, height: size }}
    >
      {n}
    </span>
  );
}

type CalloutElement = "aside" | "div" | "figure" | "section";

export interface CalloutProps {
  n: number | string;
  /** header text (default `NOTE {n}`) */
  title?: React.ReactNode;
  /** right side of the header row (e.g. a ProvenanceBadge) */
  meta?: React.ReactNode;
  /** leader line leaving the bubble toward what the note explains */
  leader?: { side: "left" | "right" | "up"; length: number };
  /** seconds before the leader draws once the callout is in view (default 0.1) */
  delay?: number;
  /** hold the leader until true (default true: draw on view) */
  play?: boolean;
  as?: CalloutElement;
  id?: string;
  className?: string;
  children?: React.ReactNode;
}

/**
 * Numbered margin note: bubble + "NOTE 1" header + body, with an optional leader line drawn
 * from the bubble when the note scrolls into view.
 */
export function Callout({ n, title, meta, leader, delay = 0.1, play = true, as = "aside", id, className, children }: CalloutProps) {
  const ref = React.useRef<HTMLElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.25 });
  const Comp = as as React.ElementType;

  let leaderSvg: React.ReactNode = null;
  if (leader) {
    const L = Math.max(0, leader.length);
    const style: React.CSSProperties =
      leader.side === "left"
        ? { right: "100%", top: "50%", width: L, height: 1 }
        : leader.side === "right"
          ? { left: "100%", top: "50%", width: L, height: 1 }
          : { left: "50%", bottom: "100%", width: 1, height: L };
    const points: Point[] =
      leader.side === "left"
        ? [
            [L, 0],
            [0, 0],
          ]
        : leader.side === "right"
          ? [
              [0, 0],
              [L, 0],
            ]
          : [
              [0, L],
              [0, 0],
            ];
    leaderSvg = (
      <svg aria-hidden="true" className="pointer-events-none absolute overflow-visible text-line-strong" style={style}>
        <LeaderPath points={points} play={play && inView} delay={delay} duration={0.55} dot="end" />
      </svg>
    );
  }

  return (
    <Comp ref={ref} id={id} className={cn("relative", className)}>
      <div className="flex items-center gap-2.5">
        <span className="relative inline-flex">
          <CalloutBubble n={n} active />
          {leaderSvg}
        </span>
        <span className="label-mono text-ink">{title ?? `NOTE ${n}`}</span>
        {meta ? <span className="ml-auto flex items-center">{meta}</span> : null}
      </div>
      {children}
    </Comp>
  );
}
