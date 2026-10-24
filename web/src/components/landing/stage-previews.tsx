"use client";

import * as React from "react";
import { motion, useMotionValue, useTransform, type MotionValue } from "motion/react";
import { getJSON } from "@/lib/api";
import { PreviewPanel } from "./feature-section";

/**
 * Scroll-driven previews for the two stages that have no small live widget elsewhere:
 * Prove (a skills profile filling in from workday moments) and Learn (GNN course picks). Both take a 0..1 MotionValue; without one they render their finished state.
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
/* Learn: courses picked by the GNN recommender                         */
/* ------------------------------------------------------------------ */

type Pick = { id: string; title: string; reason: string };
const FALLBACK_PICKS: Pick[] = [
  { id: "f1", title: "Introduction to Robotics", reason: "Teaches Technology Design for your next role" },
  { id: "f2", title: "SACA industry certifications", reason: "Teaches PLC basics for Robotics Technician" },
  { id: "f3", title: "Fluid Power and Pneumatics", reason: "Teaches Hydraulics for Machinery Mechanic" },
];

type RecItem = { kind: string; id: string; title: string; why?: string | null };

function shortTitle(t: string) {
  return t.replace(/\s*\([^)]*\)\s*$/, "").replace(/^Fluids 1:\s*/, "");
}
function shortReason(why?: string | null) {
  if (!why) return "Fits the skills you already have";
  const tail = why.split(";").pop()?.trim() ?? why;
  return tail.charAt(0).toUpperCase() + tail.slice(1);
}

function PickRow({ pick, i, p }: { pick: Pick; i: number; p: MotionValue<number> }) {
  const local = useTransform(p, (v) => clamp01((v - 0.02 - i * 0.1) / 0.18));
  const y = useTransform(local, [0, 1], [16, 0]);
  return (
    <motion.li style={{ opacity: local, y }} className="flex items-start gap-4 rounded-2xl border border-line bg-bg/60 p-4">
      <span className="font-mono text-[13px] text-accent tabular-nums">{String(i + 1).padStart(2, "0")}</span>
      <div className="min-w-0">
        <p className="truncate text-[16px] font-medium text-ink">{pick.title}</p>
        <p className="text-[14px] leading-snug text-ink-muted">{pick.reason}</p>
      </div>
    </motion.li>
  );
}

export function LearnPreview({ progress }: { progress?: MotionValue<number> }) {
  const p = useLocal(progress);
  const [picks, setPicks] = React.useState<Pick[]>(FALLBACK_PICKS);
  React.useEffect(() => {
    let live = true;
    getJSON<{ items?: RecItem[] }>("/api/graph/recommend/maya?model=gnn")
      .then((d) => {
        const courses = (d.items ?? []).filter((it) => it.kind === "course").slice(0, 3);
        if (live && courses.length === 3) setPicks(courses.map((c) => ({ id: c.id, title: shortTitle(c.title), reason: shortReason(c.why) })));
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);
  return (
    <PreviewPanel label="Courses picked for you" aside={<span className="text-sm text-ink-faint">Ranked by our GNN</span>}>
      <ul className="space-y-3">
        {picks.map((pk, i) => (
          <PickRow key={pk.id} pick={pk} i={i} p={p} />
        ))}
      </ul>
    </PreviewPanel>
  );
}
