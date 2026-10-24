"use client";

import * as React from "react";
import { useHydrated } from "@/components/motion/use-motion-env";
import { PlotterPath } from "@/components/motion/plotter-path";

/** Schematic elevation profile: valley floor (Stockton, Lodi) up into the Sierra foothills. Not to scale. */
const PTS: [number, number][] = [
  [0, 222],
  [120, 222],
  [300, 220],
  [440, 214],
  [560, 196],
  [660, 176],
  [760, 150],
  [860, 124],
  [960, 92],
  [1060, 68],
  [1130, 52],
  [1200, 44],
];

function yAt(x: number): number {
  for (let i = 1; i < PTS.length; i++) {
    const [x0, y0] = PTS[i - 1];
    const [x1, y1] = PTS[i];
    if (x <= x1) return y0 + ((x - x0) / (x1 - x0)) * (y1 - y0);
  }
  return PTS[PTS.length - 1][1];
}

export const BENCHMARKS = [
  { id: "try", label: "TRY", x: 170 },
  { id: "prove", label: "PROVE", x: 380 },
  { id: "plan", label: "PLAN", x: 600 },
  { id: "learn", label: "LEARN", x: 790 },
  { id: "connect", label: "CONNECT", x: 960 },
  { id: "belong", label: "BELONG", x: 1120 },
] as const;

export function ElevationProfile() {
  const hydrated = useHydrated();
  const d = `M${PTS.map((p) => p.join(",")).join(" L")}`;
  const ground = `${d} L1200,260 L0,260 Z`;
  return (
    <figure className="relative">
      <svg viewBox="0 0 1200 260" className="h-auto w-full overflow-visible text-ink" role="group" aria-label="Schematic elevation profile from the valley floor into the Sierra foothills, with six benchmarks that link to each chapter">
        <path d={ground} className="fill-ink/[0.04]" />
        {[60, 120, 180, 240].map((y) => (
          <line key={y} x1={0} x2={1200} y1={y} y2={y} className="stroke-line" strokeWidth={1} strokeDasharray="2 6" />
        ))}
        {hydrated ? <PlotterPath d={d} duration={2.2} delay={0.3} /> : <path d={d} fill="none" stroke="currentColor" strokeWidth={1.5} className="opacity-0" />}
        <text x={120} y={246} textAnchor="middle" className="fill-ink-muted font-mono" style={{ fontSize: 11, letterSpacing: "0.12em" }}>
          STOCKTON
        </text>
        <text x={300} y={246} textAnchor="middle" className="fill-ink-muted font-mono" style={{ fontSize: 11, letterSpacing: "0.12em" }}>
          LODI
        </text>
        <text x={1196} y={96} textAnchor="end" className="fill-ink-muted font-mono" style={{ fontSize: 11, letterSpacing: "0.12em" }}>
          SIERRA FOOTHILLS
        </text>
        {BENCHMARKS.map((b, i) => {
          const y = yAt(b.x);
          return (
            <a key={b.id} href={`#${b.id}`} className="group focus:outline-none" aria-label={`${b.label}: jump to chapter ${i + 1}`}>
              <g className="fh-fade" style={{ "--d": `${0.6 + i * 0.25}s` } as React.CSSProperties}>
                <line x1={b.x} x2={b.x} y1={y - 10} y2={y - 46} className="stroke-line-strong" strokeWidth={1} />
                <path d={`M${b.x - 6},${y} L${b.x},${y - 9} L${b.x + 6},${y} Z`} className="fill-bg stroke-ink group-hover:fill-accent group-focus-visible:fill-accent" strokeWidth={1.2} />
                <rect x={b.x - 42} y={y - 70} width={84} height={22} className="fill-transparent stroke-transparent group-focus-visible:stroke-accent" strokeWidth={1.5} />
                <text x={b.x} y={y - 54} textAnchor="middle" className="fill-ink font-mono group-hover:fill-accent" style={{ fontSize: 12, letterSpacing: "0.12em" }}>
                  {String(i + 1).padStart(2, "0")} {b.label}
                </text>
              </g>
            </a>
          );
        })}
      </svg>
      <ol className="mt-3 grid grid-cols-3 gap-2 sm:hidden" aria-label="Chapters">
        {BENCHMARKS.map((b, i) => (
          <li key={b.id}>
            <a href={`#${b.id}`} className="label-mono block border border-line px-2 py-2 text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent">
              {String(i + 1).padStart(2, "0")} {b.label}
            </a>
          </li>
        ))}
      </ol>
      <figcaption className="label-mono mt-2 flex justify-between text-ink-faint">
        <span>Elevation profile · valley floor to foothills</span>
        <span>SCHEMATIC · NTS</span>
      </figcaption>
    </figure>
  );
}
