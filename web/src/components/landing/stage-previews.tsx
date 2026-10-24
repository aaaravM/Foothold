"use client";

import * as React from "react";
import { motion, useMotionValue, useTransform, type MotionValue } from "motion/react";
import { PreviewPanel } from "./feature-section";

/**
 * Scroll-driven previews for the two stages that have no small live widget elsewhere:
 * Prove (a skills profile filling in from workday moments) and Learn (the skills graph lighting
 * a route). Both take a 0..1 MotionValue; without one they render their finished state.
 */

const clamp01 = (n: number) => Math.max(0, Math.min(1, n));

function useLocal(progress?: MotionValue<number>) {
  const done = useMotionValue(1);
  return progress ?? done;
}

/* ------------------------------------------------------------------ */
/* Prove                                                                */
/* ------------------------------------------------------------------ */

const TRAITS = [
  { name: "Attention to detail", value: 0.86, from: "Checked the seal before loading" },
  { name: "Dependability", value: 0.74, from: "Covered the late driver" },
  { name: "Cooperation", value: 0.68, from: "Asked the lead first" },
  { name: "Stress tolerance", value: 0.55, from: "Kept the dock moving" },
  { name: "Problem solving", value: 0.47, from: "Split the crew" },
];

function TraitRow({ t, i, p }: { t: (typeof TRAITS)[number]; i: number; p: MotionValue<number> }) {
  const start = 0.08 + i * 0.12;
  const local = useTransform(p, (v) => clamp01((v - start) / 0.3));
  const scaleX = useTransform(local, (v) => v * t.value);
  const pct = useTransform(local, (v) => `${Math.round(v * t.value * 100)}`);
  const noteOpacity = useTransform(local, [0.6, 1], [0, 1]);
  return (
    <li className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-3 text-[15px]">
        <span className="text-ink">{t.name}</span>
        <motion.span className="font-mono text-[13px] text-ink-muted tabular-nums">{pct}</motion.span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-ink/10" aria-hidden="true">
        <motion.div className="h-full origin-left rounded-full bg-accent" style={{ scaleX }} />
      </div>
      <motion.p style={{ opacity: noteOpacity }} className="text-[13px] text-ink-faint">
        {t.from}
      </motion.p>
    </li>
  );
}

export function ProvePreview({ progress }: { progress?: MotionValue<number> }) {
  const p = useLocal(progress);
  const moments = useTransform(p, (v) => `${Math.round(clamp01(v / 0.85) * 12)}`);
  return (
    <PreviewPanel label="Skills profile" aside={<span className="text-sm text-ink-faint">Warehouse associate</span>}>
      <div className="mb-5 flex items-baseline gap-2">
        <motion.span className="font-display text-4xl font-semibold tracking-[-0.03em] text-ink tabular-nums">{moments}</motion.span>
        <span className="text-sm text-ink-muted">moments of evidence from one workday</span>
      </div>
      <ul className="space-y-4">
        {TRAITS.map((t, i) => (
          <TraitRow key={t.name} t={t} i={i} p={p} />
        ))}
      </ul>
    </PreviewPanel>
  );
}

/* ------------------------------------------------------------------ */
/* Learn                                                                */
/* ------------------------------------------------------------------ */

type GNode = { id: string; label: string; x: number; y: number; have?: boolean; route?: number };
const NODES: GNode[] = [
  { id: "a", label: "Safety habits", x: 70, y: 210, have: true },
  { id: "b", label: "Teamwork", x: 140, y: 90, have: true },
  { id: "c", label: "Forklift cert", x: 230, y: 250, route: 1 },
  { id: "d", label: "Inventory systems", x: 330, y: 150, route: 2 },
  { id: "e", label: "Basic electrical", x: 250, y: 50 },
  { id: "f", label: "PLC basics", x: 420, y: 60 },
  { id: "g", label: "Logistics lead", x: 470, y: 230, route: 3 },
];
const EDGES: [string, string, boolean][] = [
  ["a", "c", true],
  ["b", "c", false],
  ["b", "e", false],
  ["c", "d", true],
  ["e", "f", false],
  ["d", "f", false],
  ["d", "g", true],
];
const byId = Object.fromEntries(NODES.map((n) => [n.id, n]));

function Edge({ from, to, route, p, order }: { from: GNode; to: GNode; route: boolean; p: MotionValue<number>; order: number }) {
  const draw = useTransform(p, (v) => (route ? clamp01((v - 0.15 - order * 0.18) / 0.22) : 1));
  return (
    <>
      <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="currentColor" strokeOpacity={0.14} strokeWidth={1.5} />
      {route ? (
        <motion.line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="var(--accent)" strokeWidth={2.5} strokeLinecap="round" style={{ pathLength: draw }} />
      ) : null}
    </>
  );
}

function Node({ n, p }: { n: GNode; p: MotionValue<number> }) {
  const lit = useTransform(p, (v) => (n.have ? 1 : n.route ? clamp01((v - 0.2 - n.route * 0.18) / 0.12) : 0));
  const fill = useTransform(lit, (v) => (v > 0.5 ? "var(--accent)" : "var(--bg)"));
  const r = useTransform(lit, [0, 1], [7, 9]);
  const textOpacity = useTransform(lit, [0, 1], [0.55, 1]);
  return (
    <g>
      <motion.circle cx={n.x} cy={n.y} r={r} style={{ fill }} stroke={n.have || n.route ? "var(--accent)" : "currentColor"} strokeOpacity={n.have || n.route ? 1 : 0.3} strokeWidth={1.5} />
      <motion.text x={n.x} y={n.y + 26} textAnchor="middle" className="fill-current text-[13px]" stroke="var(--surface, var(--bg))" strokeWidth={5} strokeLinejoin="round" style={{ opacity: textOpacity, paintOrder: "stroke" }}>
        {n.label}
      </motion.text>
    </g>
  );
}

export function LearnPreview({ progress }: { progress?: MotionValue<number> }) {
  const p = useLocal(progress);
  const routeEdges = EDGES.filter((e) => e[2]);
  return (
    <PreviewPanel label="Skills graph" aside={<span className="text-sm text-ink-faint">Next steps from what you have</span>}>
      <svg viewBox="0 20 540 270" className="h-auto w-full text-ink" role="img" aria-label="Skills you have connect to a route: forklift certification, then inventory systems, then logistics lead.">
        {EDGES.map(([a, b, route]) => (
          <Edge key={`${a}${b}`} from={byId[a]} to={byId[b]} route={route} p={p} order={route ? routeEdges.findIndex((e) => e[0] === a && e[1] === b) : 0} />
        ))}
        {NODES.map((n) => (
          <Node key={n.id} n={n} p={p} />
        ))}
      </svg>
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-ink-muted">
        <span className="inline-flex items-center gap-2">
          <span aria-hidden="true" className="size-2.5 rounded-full bg-accent" /> You have it
        </span>
        <span className="inline-flex items-center gap-2">
          <span aria-hidden="true" className="size-2.5 rounded-full border border-accent" /> On your route
        </span>
      </div>
    </PreviewPanel>
  );
}
