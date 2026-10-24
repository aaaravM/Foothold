"use client";

import * as React from "react";
import { animate, motion, useMotionValue, useMotionValueEvent, useTransform, type Easing, type MotionValue } from "motion/react";
import { cn } from "@/lib/utils";
import { EASE_PLOT, useLatest, useReducedMotionSafe } from "./use-motion-env";

export interface PlotterPathProps {
  /** SVG path data in the parent <svg>'s user units. */
  d: string;
  /** Seconds for the full stroke (default 1.8; the brief allows 1.2-2.4). */
  duration?: number;
  /** Seconds before the pen starts (default 0). */
  delay?: number;
  /** Default: the plotter ease [0.65, 0, 0.35, 1]. */
  ease?: Easing;
  /** Start (true, default) or hold (false) the time-based drawing. Ignored when `progress` is given. */
  play?: boolean;
  /** Drive the drawing yourself (0..1), e.g. from useScroll/useSpring. Overrides duration/delay/play. */
  progress?: MotionValue<number>;
  /** Gold pen-head dot riding the tip (default true; never shown with reduced motion). */
  penHead?: boolean;
  /** Pen-head radius in user units (default 3.5). */
  penRadius?: number;
  /** Keep the pen head parked at the end after drawing (default false: it lifts off). */
  penRest?: boolean;
  /** Called once each time the time-based drawing completes. */
  onDrawn?: () => void;
  /** Change to redraw from zero. */
  replayKey?: string | number;
  strokeWidth?: number;
  strokeLinecap?: "butt" | "round" | "square";
  /** Classes for the stroke (e.g. "stroke-ink"); default stroke is currentColor. */
  className?: string;
  penClassName?: string;
}

/**
 * A stroke that draws itself like a pen plotter: SVG pathLength 0 -> 1 with the plotter ease,
 * plus a small gold pen head riding the leading tip. Render inside an <svg>.
 * Reduced motion: the finished stroke appears at once, without a pen head.
 */
export function PlotterPath({
  d,
  duration = 1.8,
  delay = 0,
  ease = EASE_PLOT,
  play = true,
  progress,
  penHead = true,
  penRadius = 3.5,
  penRest = false,
  onDrawn,
  replayKey,
  strokeWidth = 1.25,
  strokeLinecap = "butt",
  className,
  penClassName,
}: PlotterPathProps) {
  const reduced = useReducedMotionSafe();
  const pathRef = React.useRef<SVGPathElement>(null);
  const lengthRef = React.useRef(0);
  const own = useMotionValue(0);
  const p = progress ?? own;
  const penX = useMotionValue(0);
  const penY = useMotionValue(0);
  const easeRef = useLatest(ease);
  const onDrawnRef = useLatest(onDrawn);
  const easeKey = Array.isArray(ease) ? ease.join(",") : typeof ease === "function" ? "fn" : String(ease);

  // Time-based drawing (when nobody drives `progress`).
  React.useEffect(() => {
    if (progress) return;
    if (reduced) {
      own.set(1);
      return;
    }
    own.set(0);
    if (!play) return;
    const controls = animate(own, 1, {
      duration,
      delay,
      ease: easeRef.current,
      onComplete: () => onDrawnRef.current?.(),
    });
    return () => controls.stop();
  }, [progress, reduced, play, duration, delay, easeKey, replayKey, own, easeRef, onDrawnRef]);

  // Pen head follows the tip.
  const placePen = React.useCallback(
    (v: number) => {
      const el = pathRef.current;
      if (!el) return;
      if (!lengthRef.current) lengthRef.current = el.getTotalLength();
      const pt = el.getPointAtLength(Math.min(Math.max(v, 0), 1) * lengthRef.current);
      penX.set(pt.x);
      penY.set(pt.y);
    },
    [penX, penY],
  );
  useMotionValueEvent(p, "change", placePen);
  React.useLayoutEffect(() => {
    lengthRef.current = 0;
    placePen(p.get());
  }, [d, p, placePen]);

  // Hide the zero-length dot a round/square cap would leave at pathLength 0.
  const strokeOpacity = useTransform(p, (v) => (v <= 0.0005 ? 0 : 1));
  const penOpacity = useTransform(p, (v) => {
    if (v <= 0.001) return 0;
    if (penRest) return 1;
    return v >= 0.995 ? 0 : v > 0.96 ? (0.995 - v) / 0.035 : 1;
  });

  return (
    <g>
      <motion.path
        ref={pathRef}
        d={d}
        fill="none"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap={strokeLinecap}
        strokeLinejoin="round"
        className={className}
        style={{ pathLength: p, opacity: strokeOpacity }}
      />
      {penHead && !reduced ? (
        <motion.g aria-hidden="true" className={cn("pointer-events-none", penClassName)} style={{ opacity: penOpacity }}>
          <motion.circle cx={penX} cy={penY} r={penRadius * 2.6} fill="var(--accent)" fillOpacity={0.18} />
          <motion.circle cx={penX} cy={penY} r={penRadius} fill="var(--accent)" />
        </motion.g>
      ) : null}
    </g>
  );
}
