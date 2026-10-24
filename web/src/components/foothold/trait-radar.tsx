"use client";

import * as React from "react";
import { motion, useReducedMotion } from "motion/react";
import { cn } from "@/lib/utils";

export interface TraitDatum {
  id: string;
  /** full name, used in the screen-reader table */
  name: string;
  /** 0..1 */
  value: number;
  /** short axis label (traits.json `short`); derived from `name` when missing */
  short?: string;
  /** higher-order group (traits.json `group`); contiguous groups get a colored arc */
  group?: string;
}

export interface TraitRadarProps {
  traits: readonly TraitDatum[];
  /** trait id(s) to emphasize, e.g. the traits the last choice moved */
  highlight?: string | readonly string[];
  /** optional dashed overlay, e.g. a career's work-style profile */
  compare?: { label: string; values: Readonly<Record<string, number>> };
  /** visible caption and table caption */
  title?: string;
  /** legend name of the main shape (default "You") */
  valueLabel?: string;
  /** draw group arcs + legend when traits carry `group` (default true) */
  showGroups?: boolean;
  className?: string;
}

// Geometry in SVG user units. Extra horizontal room keeps long side labels inside the box.
const VB_X = -50;
const VB_W = 560;
const VB_H = 470;
const C_X = 230;
const C_Y = 235;
const R = 150;
const LABEL_R = R + 20;
const GROUP_R = R + 9;
const RINGS = [0.25, 0.5, 0.75, 1];
const GROUP_COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];
const STOP_WORDS = new Set(["to", "for", "and", "of", "the", "a"]);

const clamp01 = (v: number) => (Number.isFinite(v) ? Math.min(1, Math.max(0, v)) : 0);
const angleAt = (i: number, n: number) => -Math.PI / 2 + (i * 2 * Math.PI) / n;
const pointAt = (i: number, n: number, r: number): [number, number] => {
  const a = angleAt(i, n);
  return [C_X + r * Math.cos(a), C_Y + r * Math.sin(a)];
};
const f = (v: number) => v.toFixed(2);

function shapePath(values: readonly number[]): string {
  const n = values.length;
  if (n === 0) return "";
  return (
    values
      .map((v, i) => {
        const [x, y] = pointAt(i, n, R * clamp01(v));
        return `${i === 0 ? "M" : "L"}${f(x)} ${f(y)}`;
      })
      .join(" ") + " Z"
  );
}

function arcPath(a0: number, a1: number, r: number): string {
  const x0 = C_X + r * Math.cos(a0);
  const y0 = C_Y + r * Math.sin(a0);
  const x1 = C_X + r * Math.cos(a1);
  const y1 = C_Y + r * Math.sin(a1);
  const large = a1 - a0 > Math.PI ? 1 : 0;
  return `M${f(x0)} ${f(y0)} A${r} ${r} 0 ${large} 1 ${f(x1)} ${f(y1)}`;
}

function abbreviate(name: string): string {
  if (name.length <= 10) return name.toUpperCase();
  const words = name.split(/[\s-]+/).filter((w) => w && !STOP_WORDS.has(w.toLowerCase()));
  if (words.length <= 1) return name.slice(0, 8).toUpperCase();
  return words
    .map((w) => w.slice(0, 4))
    .join(" ")
    .toUpperCase();
}

const pct = (v: number | undefined) => (typeof v === "number" && Number.isFinite(v) ? `${Math.round(clamp01(v) * 100)}%` : "n/a");

/**
 * SVG radar for the 21 O*NET work styles (or any 0..1 profile).
 * The SVG is decorative for assistive tech; a visually hidden table carries the data.
 */
export function TraitRadar({
  traits,
  highlight,
  compare,
  title,
  valueLabel = "You",
  showGroups = true,
  className,
}: TraitRadarProps) {
  const reduce = useReducedMotion();
  const n = traits.length;
  const hl = React.useMemo(() => new Set(typeof highlight === "string" ? [highlight] : (highlight ?? [])), [highlight]);

  const groups = React.useMemo(() => {
    const runs: { name: string; start: number; end: number; color: string }[] = [];
    const colorOf = new Map<string, string>();
    traits.forEach((t, i) => {
      if (!t.group) return;
      if (!colorOf.has(t.group)) colorOf.set(t.group, GROUP_COLORS[colorOf.size % GROUP_COLORS.length]);
      const last = runs[runs.length - 1];
      if (last && last.name === t.group && last.end === i - 1) last.end = i;
      else runs.push({ name: t.group, start: i, end: i, color: colorOf.get(t.group) as string });
    });
    return { runs, colorOf };
  }, [traits]);

  if (n < 3) {
    return <p className={cn("label-mono text-ink-faint", className)}>Not enough traits to draw a profile.</p>;
  }

  const step = (2 * Math.PI) / n;
  const values = traits.map((t) => t.value);
  const mainPath = shapePath(values);
  const comparePath = compare ? shapePath(traits.map((t) => compare.values[t.id] ?? 0)) : null;
  const transition = reduce ? { duration: 0 } : { duration: 0.6, ease: [0.22, 1, 0.36, 1] as const };
  const drawGroups = showGroups && groups.runs.length > 0;

  return (
    <figure className={cn("w-full", className)}>
      {title ? <figcaption className="label-mono mb-3 text-ink-muted">{title}</figcaption> : null}

      <svg
        viewBox={`${VB_X} 0 ${VB_W} ${VB_H}`}
        className="h-auto w-full max-w-[560px] overflow-visible"
        aria-hidden="true"
        focusable="false"
      >
        {/* rings */}
        {RINGS.map((lvl) => (
          <path
            key={lvl}
            d={shapePath(Array.from({ length: n }, () => lvl))}
            fill="none"
            stroke={lvl === 1 ? "var(--line-strong)" : "var(--line)"}
            strokeWidth={1}
            vectorEffect="non-scaling-stroke"
          />
        ))}

        {/* axes */}
        {traits.map((t, i) => {
          const [x, y] = pointAt(i, n, R);
          const on = hl.has(t.id);
          return (
            <line
              key={`axis-${t.id}`}
              x1={C_X}
              y1={C_Y}
              x2={f(x)}
              y2={f(y)}
              stroke={on ? "var(--accent)" : "var(--line)"}
              strokeWidth={on ? 1.5 : 1}
              vectorEffect="non-scaling-stroke"
            />
          );
        })}

        {/* group arcs */}
        {drawGroups
          ? groups.runs.map((g) => {
              const gap = step * 0.14;
              const a0 = angleAt(g.start, n) - step / 2 + gap;
              const a1 = angleAt(g.end, n) + step / 2 - gap;
              return (
                <path
                  key={`${g.name}-${g.start}`}
                  d={arcPath(a0, a1, GROUP_R)}
                  fill="none"
                  stroke={g.color}
                  strokeWidth={3}
                  strokeLinecap="butt"
                />
              );
            })
          : null}

        {/* comparison profile */}
        {comparePath ? (
          <motion.path
            initial={false}
            animate={{ d: comparePath }}
            transition={transition}
            fill="none"
            stroke="var(--ink-muted)"
            strokeWidth={1.25}
            strokeDasharray="4 3"
            vectorEffect="non-scaling-stroke"
          />
        ) : null}

        {/* main profile */}
        <motion.path
          initial={false}
          animate={{ d: mainPath }}
          transition={transition}
          fill="var(--accent)"
          fillOpacity={0.16}
          stroke="var(--accent)"
          strokeWidth={1.75}
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />

        {/* vertices */}
        {traits.map((t, i) => {
          const [x, y] = pointAt(i, n, R * clamp01(t.value));
          const on = hl.has(t.id);
          return (
            <motion.circle
              key={`pt-${t.id}`}
              initial={false}
              animate={{ cx: x, cy: y, r: on ? 4.5 : 2.5 }}
              transition={transition}
              fill={on ? "var(--accent)" : "var(--background)"}
              stroke="var(--accent)"
              strokeWidth={1.5}
              vectorEffect="non-scaling-stroke"
            />
          );
        })}

        {/* labels */}
        {traits.map((t, i) => {
          const a = angleAt(i, n);
          const cos = Math.cos(a);
          const sin = Math.sin(a);
          const [x, y] = pointAt(i, n, LABEL_R);
          const anchor = Math.abs(cos) < 0.26 ? "middle" : cos > 0 ? "start" : "end";
          const dy = sin < -0.5 ? "-0.15em" : sin > 0.5 ? "0.85em" : "0.35em";
          const on = hl.has(t.id);
          return (
            <text
              key={`lbl-${t.id}`}
              x={f(x)}
              y={f(y)}
              dy={dy}
              textAnchor={anchor}
              fontFamily="var(--font-mono)"
              fontSize={10}
              letterSpacing="0.06em"
              fontWeight={on ? 700 : 400}
              fill={on ? "var(--accent)" : "var(--ink-faint)"}
            >
              {(t.short || abbreviate(t.name)).toUpperCase()}
            </text>
          );
        })}
      </svg>

      {/* legend */}
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2" aria-hidden="true">
        <span className="label-mono inline-flex items-center gap-2 text-ink-muted">
          <span className="h-2.5 w-4 border border-accent bg-accent/20" />
          {valueLabel}
        </span>
        {compare ? (
          <span className="label-mono inline-flex items-center gap-2 text-ink-muted">
            <span className="h-0 w-4 border-t border-dashed border-ink-muted" />
            {compare.label}
          </span>
        ) : null}
        {drawGroups
          ? Array.from(groups.colorOf.entries()).map(([name, color]) => (
              <span key={name} className="label-mono inline-flex items-center gap-2 text-ink-faint">
                <span className="h-[3px] w-4" style={{ background: color }} />
                {name}
              </span>
            ))
          : null}
      </div>

      <table className="sr-only">
        <caption>
          {title ?? "Work styles profile"}
          {compare ? `, compared with ${compare.label}` : ""}
        </caption>
        <thead>
          <tr>
            <th scope="col">Work style</th>
            <th scope="col">{valueLabel}</th>
            {compare ? <th scope="col">{compare.label}</th> : null}
          </tr>
        </thead>
        <tbody>
          {traits.map((t) => (
            <tr key={t.id}>
              <th scope="row">
                {t.name}
                {hl.has(t.id) ? " (highlighted)" : ""}
              </th>
              <td>{pct(t.value)}</td>
              {compare ? <td>{pct(compare.values[t.id])}</td> : null}
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
