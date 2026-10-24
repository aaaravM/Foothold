"use client";

import * as React from "react";
import { animate, motion, useInView, useMotionValue, useMotionValueEvent, useReducedMotion, useTransform, type MotionValue } from "motion/react";
import { cn } from "@/lib/utils";

/** DESIGN_DIRECTION section 4: plotter ease and durations. */
export const PLOT_EASE = [0.65, 0, 0.35, 1] as const;

/**
 * Progress 0 -> 1 that starts when `ref` scrolls into view (once).
 * Reduced motion: jumps to 1 immediately (final state, no pen head).
 */
export function usePlotProgress(ref: React.RefObject<Element | null>, { duration = 1.6, delay = 0 } = {}) {
  const reduce = useReducedMotion();
  const inView = useInView(ref, { once: true, margin: "0px 0px -8% 0px" });
  const progress = useMotionValue(reduce ? 1 : 0);
  React.useEffect(() => {
    if (reduce) {
      progress.set(1);
      return;
    }
    if (!inView) return;
    const controls = animate(progress, 1, { duration, delay, ease: PLOT_EASE });
    return () => controls.stop();
  }, [inView, reduce, progress, duration, delay]);
  return { progress, reduce: !!reduce, inView };
}

/** An SVG path that draws itself as `progress` goes 0 -> 1. */
export function PlotPath({
  d,
  progress,
  className,
  strokeWidth = 1.5,
  dashed = false,
  linecap = "round",
  pathRef,
}: {
  d: string;
  progress: MotionValue<number>;
  className?: string;
  strokeWidth?: number;
  dashed?: boolean;
  linecap?: "round" | "butt" | "square";
  pathRef?: React.Ref<SVGPathElement>;
}) {
  if (dashed) {
    // pathLength animation and dash arrays fight each other; dashed guides reveal by opacity instead.
    return <DashedPath d={d} progress={progress} className={className} strokeWidth={strokeWidth} />;
  }
  return (
    <motion.path
      ref={pathRef}
      d={d}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap={linecap}
      strokeLinejoin="round"
      className={className}
      style={{ pathLength: progress }}
    />
  );
}

function DashedPath({ d, progress, className, strokeWidth }: { d: string; progress: MotionValue<number>; className?: string; strokeWidth: number }) {
  const opacity = useTransform(progress, [0, 0.6, 1], [0, 0.4, 1]);
  return (
    <motion.path
      d={d}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeDasharray="4 4"
      vectorEffect="non-scaling-stroke"
      className={className}
      style={{ opacity }}
    />
  );
}

/**
 * The gold pen head riding the leading tip of a straight segment (x0,y0) -> (x1,y1).
 * Hidden for reduced motion and once the stroke is finished.
 */
export function PenHead({
  progress,
  from,
  to,
  reduce,
  r = 3,
}: {
  progress: MotionValue<number>;
  from: [number, number];
  to: [number, number];
  reduce: boolean;
  r?: number;
}) {
  const cx = useTransform(progress, (p) => from[0] + (to[0] - from[0]) * p);
  const cy = useTransform(progress, (p) => from[1] + (to[1] - from[1]) * p);
  const opacity = useTransform(progress, (p) => (p > 0.001 && p < 0.999 ? 1 : 0));
  if (reduce) return null;
  return <motion.circle cx={cx} cy={cy} r={r} className="fill-accent" style={{ opacity }} />;
}

/** Pen head that follows an arbitrary path element by length. */
export function PathPenHead({ pathRef, progress, reduce }: { pathRef: React.RefObject<SVGPathElement | null>; progress: MotionValue<number>; reduce: boolean }) {
  const [pt, setPt] = React.useState<{ x: number; y: number; visible: boolean }>({ x: 0, y: 0, visible: false });
  useMotionValueEvent(progress, "change", (p) => {
    const el = pathRef.current;
    if (!el) return;
    try {
      const len = el.getTotalLength();
      const q = el.getPointAtLength(len * p);
      setPt({ x: q.x, y: q.y, visible: p > 0.001 && p < 0.999 });
    } catch {
      // path not laid out yet
    }
  });
  if (reduce || !pt.visible) return null;
  return <circle cx={pt.x} cy={pt.y} r={3} className="fill-accent" />;
}

/** Count-up for REAL values only (600-900 ms, tabular numerals). Never use it for placeholders. */
export function CountUp({
  value,
  format,
  duration = 0.8,
  className,
}: {
  value: number;
  format: (n: number) => string;
  duration?: number;
  className?: string;
}) {
  const ref = React.useRef<HTMLSpanElement>(null);
  const reduce = useReducedMotion();
  const inView = useInView(ref, { once: true, margin: "0px 0px -5% 0px" });
  const mv = useMotionValue(reduce ? value : 0);
  const [shown, setShown] = React.useState(() => format(reduce ? value : 0));
  useMotionValueEvent(mv, "change", (n) => setShown(format(n)));
  React.useEffect(() => {
    if (reduce) {
      mv.jump(value);
      return;
    }
    if (!inView) return;
    const controls = animate(mv, value, { duration, ease: [0.16, 1, 0.3, 1] });
    return () => controls.stop();
  }, [inView, reduce, value, duration, mv]);
  return (
    <span ref={ref} className={cn("tabular-nums", className)}>
      <span aria-hidden="true">{shown}</span>
      <span className="sr-only">{format(value)}</span>
    </span>
  );
}
