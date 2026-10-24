"use client";

import * as React from "react";
import { motion, useReducedMotion } from "motion/react";
import { cn } from "@/lib/utils";
import { NotTrainedYet } from "@/components/foothold/metric-value";
import { PLOT_EASE, PlotPath, usePlotProgress } from "./plotter";
import type { Curve } from "./metrics";

export function fmtValue(v: number, asPercent: boolean, digits = 1): string {
  return asPercent ? `${(v * 100).toFixed(digits)}%` : Number.isInteger(v) ? String(v) : v.toFixed(digits + 1);
}

export interface BarRow {
  label: string;
  value: number | null;
  /** the model being measured (gold); baselines stay ink */
  primary?: boolean;
  sub?: string;
}

/**
 * Horizontal comparison bars, scaled to `max` (default: largest value). Missing values print
 * "not trained yet", never a bar. Bars grow by scaleX (transform only) and respect reduced motion.
 */
export function BarCompare({
  rows,
  max,
  percent = false,
  digits = 1,
  caption,
  className,
}: {
  rows: BarRow[];
  max?: number;
  percent?: boolean;
  digits?: number;
  caption?: string;
  className?: string;
}) {
  const reduce = useReducedMotion();
  const present = rows.map((r) => r.value).filter((v): v is number => v !== null);
  const top = max ?? (present.length ? Math.max(...present) : 1);
  return (
    <figure className={cn("space-y-2.5", className)}>
      {caption ? <figcaption className="label-mono text-ink-faint">{caption}</figcaption> : null}
      <dl className="space-y-2.5">
        {rows.map((r) => (
          <div key={r.label} className="grid grid-cols-[minmax(6.5rem,9rem)_1fr_auto] items-center gap-3">
            <dt className="truncate text-sm text-ink-muted" title={r.label}>
              {r.label}
              {r.sub ? <span className="block text-[11px] text-ink-faint">{r.sub}</span> : null}
            </dt>
            <div className="relative h-3 border border-line" aria-hidden="true">
              {r.value !== null && top > 0 ? (
                <motion.div
                  className={cn("absolute inset-y-0 left-0 origin-left", r.primary ? "bg-accent" : "bg-ink/70")}
                  style={{ width: `${Math.max(0, Math.min(1, r.value / top)) * 100}%` }}
                  initial={reduce ? false : { scaleX: 0 }}
                  whileInView={{ scaleX: 1 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.9, ease: PLOT_EASE }}
                />
              ) : null}
            </div>
            <dd className="min-w-[4.5rem] text-right font-mono text-sm text-ink tabular-nums">
              {r.value !== null ? fmtValue(r.value, percent, digits) : <NotTrainedYet className="text-xs" />}
            </dd>
          </div>
        ))}
      </dl>
    </figure>
  );
}

const SERIES_CLASS = ["text-accent", "text-ink", "text-ink-muted", "text-info"];

/** Accuracy-after-k style line chart drawn by the plotter. Data comes straight from metrics.json. */
export function LineCurve({ curve, percent, yLabel, className }: { curve: Curve; percent: boolean; yLabel: string; className?: string }) {
  const ref = React.useRef<SVGSVGElement>(null);
  const { progress } = usePlotProgress(ref, { duration: 1.8 });
  const W = 560;
  const H = 220;
  const pad = { l: 44, r: 12, t: 12, b: 32 };
  const xs = curve.xs;
  const all = curve.series.flatMap((s) => s.values.filter((v): v is number => v !== null));
  const yMax = percent ? 1 : Math.max(...all, 1);
  const yMin = percent ? 0 : Math.min(0, ...all);
  const x0 = xs[0];
  const x1 = xs[xs.length - 1];
  const sx = (x: number) => pad.l + ((x - x0) / Math.max(1e-9, x1 - x0)) * (W - pad.l - pad.r);
  const sy = (y: number) => pad.t + (1 - (y - yMin) / Math.max(1e-9, yMax - yMin)) * (H - pad.t - pad.b);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => yMin + t * (yMax - yMin));
  return (
    <figure className={cn("space-y-2", className)}>
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={`${yLabel} by ${curve.xLabel}, ${curve.series.map((s) => s.name).join(", ")}`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={W - pad.r} y1={sy(t)} y2={sy(t)} className="stroke-line" strokeWidth={1} />
            <text x={pad.l - 6} y={sy(t) + 3} textAnchor="end" className="fill-ink-faint font-mono" style={{ fontSize: 10 }}>
              {percent ? `${Math.round(t * 100)}%` : t.toFixed(1)}
            </text>
          </g>
        ))}
        {xs.map((x, i) =>
          xs.length <= 12 || i % Math.ceil(xs.length / 10) === 0 ? (
            <text key={x} x={sx(x)} y={H - 12} textAnchor="middle" className="fill-ink-faint font-mono" style={{ fontSize: 10 }}>
              {x}
            </text>
          ) : null,
        )}
        <text x={W - pad.r} y={H - 1} textAnchor="end" className="fill-ink-faint font-mono" style={{ fontSize: 9, letterSpacing: "0.1em" }}>
          {curve.xLabel.toUpperCase()}
        </text>
        {curve.series.map((s, si) => {
          const pts = s.values.map((v, i) => (v === null ? null : `${sx(xs[i])},${sy(v)}`)).filter(Boolean) as string[];
          if (pts.length < 2) return null;
          return <PlotPath key={s.name} d={`M${pts.join(" L")}`} progress={progress} className={SERIES_CLASS[si % SERIES_CLASS.length]} strokeWidth={si === 0 ? 2 : 1.4} />;
        })}
      </svg>
      <figcaption className="flex flex-wrap gap-x-4 gap-y-1">
        {curve.series.map((s, si) => (
          <span key={s.name} className="label-mono inline-flex items-center gap-1.5 text-ink-muted">
            <span aria-hidden="true" className={cn("inline-block h-0.5 w-4 bg-current", SERIES_CLASS[si % SERIES_CLASS.length])} />
            {s.name.replace(/_/g, " ")}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
