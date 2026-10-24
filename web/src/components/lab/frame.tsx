"use client";

import * as React from "react";
import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";
import { MonoLabel } from "@/components/foothold/mono-label";
import { RegistrationMarks } from "@/components/foothold/registration-marks";
import { PLOT_EASE } from "./plotter";

/**
 * Detail callout symbol from drafting: a circle split by a rule, detail letter above,
 * sheet number below. The circle is plotted when the frame scrolls into view.
 */
export function DetailBubble({ letter, sheet, size = 56, className }: { letter: string; sheet: string; size?: number; className?: string }) {
  const reduce = useReducedMotion();
  const r = size / 2 - 1.5;
  const c = size / 2;
  return (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} className={cn("shrink-0 overflow-visible text-ink", className)} aria-hidden="true">
      <motion.circle
        cx={c}
        cy={c}
        r={r}
        fill="var(--bg)"
        stroke="currentColor"
        strokeWidth={1.25}
        initial={reduce ? false : { pathLength: 0, rotate: -90 }}
        whileInView={{ pathLength: 1, rotate: -90 }}
        viewport={{ once: true }}
        transition={{ duration: 1.1, ease: PLOT_EASE }}
        style={{ originX: "50%", originY: "50%" }}
      />
      <motion.line
        x1={c - r + 3}
        x2={c + r - 3}
        y1={c + 2}
        y2={c + 2}
        stroke="currentColor"
        strokeWidth={1}
        initial={reduce ? false : { pathLength: 0 }}
        whileInView={{ pathLength: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5, delay: 0.7, ease: PLOT_EASE }}
      />
      <text x={c} y={c - 4} textAnchor="middle" className="fill-ink font-display" style={{ fontSize: size * 0.36, fontWeight: 700 }}>
        {letter}
      </text>
      <text x={c} y={c + 14} textAnchor="middle" className="fill-ink-muted font-mono" style={{ fontSize: size * 0.16, letterSpacing: "0.08em" }}>
        {sheet}
      </text>
    </svg>
  );
}

export type FrameStatus = "trained" | "partial" | "not_trained" | "loading" | "offline";

const STATUS_COPY: Record<FrameStatus, { label: string; className: string }> = {
  trained: { label: "Measured", className: "text-success border-success/50" },
  partial: { label: "Partly measured", className: "text-warning border-warning/50" },
  not_trained: { label: "Not trained yet", className: "text-ink-muted border-line-strong border-dashed" },
  loading: { label: "Reading metrics", className: "text-ink-faint border-line" },
  offline: { label: "API offline", className: "text-warning border-warning/50" },
};

export function StatusTag({ status, className }: { status: FrameStatus; className?: string }) {
  const s = STATUS_COPY[status];
  return (
    <span className={cn("label-mono inline-flex h-5 items-center gap-1.5 rounded-sm border px-1.5 leading-none whitespace-nowrap", s.className, className)}>
      <span aria-hidden="true" className={cn("size-1.5 rounded-full bg-current", status === "loading" && "animate-pulse")} />
      {s.label}
    </span>
  );
}

export interface DetailFrameProps {
  id: string;
  letter: string;
  sheet: string;
  title: string;
  /** "MLP vs cosine baseline" */
  kicker: string;
  usedOn?: { label: string; href: string };
  status: FrameStatus;
  badges?: React.ReactNode;
  /** left column: what it is, training data, how it's measured */
  aside: React.ReactNode;
  /** right column: readouts and charts */
  children: React.ReactNode;
  /** bottom row: reproduce command + footnotes */
  footer?: React.ReactNode;
  className?: string;
}

/** One drawing-style detail frame per model (SHEET 06). */
export function DetailFrame({ id, letter, sheet, title, kicker, usedOn, status, badges, aside, children, footer, className }: DetailFrameProps) {
  const headingId = `${id}-title`;
  return (
    <article id={id} aria-labelledby={headingId} className={cn("relative scroll-mt-24 border border-line bg-background", className)}>
      <RegistrationMarks variant="crop" size={12} inset="-6px" />
      <header className="flex flex-wrap items-center gap-x-5 gap-y-3 border-b border-line px-4 py-4 sm:px-6">
        <DetailBubble letter={letter} sheet={sheet} />
        <div className="min-w-0 flex-1 space-y-1">
          <MonoLabel as="p" tone="muted">
            Detail {letter}
            <span aria-hidden="true" className="px-2 text-ink-faint">
              ·
            </span>
            {kicker}
          </MonoLabel>
          <h3 id={headingId} className="type-display-md text-ink">
            {title}
          </h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {badges}
          <StatusTag status={status} />
        </div>
      </header>
      <div className="grid lg:grid-cols-12">
        <div className="space-y-5 border-b border-line px-4 py-6 sm:px-6 lg:col-span-4 lg:border-r lg:border-b-0">
          {usedOn ? (
            <p className="label-mono text-ink-faint">
              Used on{" "}
              <Link href={usedOn.href} className="text-ink underline decoration-line-strong underline-offset-4 transition-colors hover:text-accent hover:decoration-accent">
                {usedOn.label}
              </Link>
            </p>
          ) : null}
          {aside}
        </div>
        <div className="min-w-0 space-y-8 px-4 py-6 sm:px-6 lg:col-span-8">{children}</div>
      </div>
      {footer ? <footer className="border-t border-line">{footer}</footer> : null}
    </article>
  );
}

/** Labelled paragraph in a frame's left column. */
export function AsideBlock({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <MonoLabel as="h4">{term}</MonoLabel>
      <div className="text-[15px] leading-relaxed text-ink-muted">{children}</div>
    </div>
  );
}

/** `$ python ml/train_career_fit.py` with a copy button. The command text comes from metrics.json. */
export function ReproduceCommand({ command, pending, meta }: { command: string | null; pending?: string; meta?: React.ReactNode }) {
  const [copied, setCopied] = React.useState(false);
  React.useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 1600);
    return () => clearTimeout(t);
  }, [copied]);
  const copy = async () => {
    if (!command) return;
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
    } catch {
      // clipboard blocked: the command stays selectable
    }
  };
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
      <MonoLabel tone="faint" className="shrink-0">
        Reproduce
      </MonoLabel>
      {command ? (
        <code className="min-w-0 flex-1 overflow-x-auto font-mono text-[12.5px] whitespace-pre text-ink">
          <span aria-hidden="true" className="text-accent select-none">
            ${" "}
          </span>
          {command}
        </code>
      ) : (
        <span className="min-w-0 flex-1 text-sm text-ink-muted">{pending}</span>
      )}
      {meta ? <span className="label-mono text-ink-faint">{meta}</span> : null}
      {command ? (
        <button
          type="button"
          onClick={copy}
          className="label-mono inline-flex h-7 items-center gap-1.5 rounded-sm border border-line-strong px-2 text-ink-muted transition-colors hover:border-accent hover:text-ink"
          aria-label={copied ? "Command copied" : "Copy reproduce command"}
        >
          {copied ? <Check aria-hidden="true" className="size-3" /> : <Copy aria-hidden="true" className="size-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      ) : null}
    </div>
  );
}

/** Big real number with a footnote mark (DESIGN_DIRECTION section 3). */
export function Readout({
  label,
  children,
  sub,
  footnote,
  emphasis = false,
  className,
}: {
  label: string;
  children: React.ReactNode;
  sub?: React.ReactNode;
  footnote?: string;
  emphasis?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("min-w-0 space-y-1.5", className)}>
      <MonoLabel as="p">{label}</MonoLabel>
      <p className={cn("font-display leading-none text-ink", emphasis ? "text-[clamp(2.75rem,6vw,4.25rem)]" : "text-[clamp(1.75rem,3.4vw,2.5rem)]")} style={{ fontVariationSettings: '"wdth" 80', fontWeight: 600 }}>
        {children}
        {footnote ? (
          <sup className="ml-1 align-super font-mono text-[11px] font-normal text-accent">
            <a href={`#${footnote}`} className="hover:underline" aria-label="Source note">
              {footnote.replace(/^.*-/, "")}
            </a>
          </sup>
        ) : null}
      </p>
      {sub ? <p className="text-sm text-ink-muted">{sub}</p> : null}
    </div>
  );
}

/** "All recorded values" disclosure: every scalar in the metrics block, so nothing the script wrote is hidden. */
export function RecordedValues({ rows, source }: { rows: { path: string; value: string }[]; source: string }) {
  if (!rows.length) return null;
  return (
    <details className="group border-t border-line">
      <summary className="label-mono flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-ink-faint transition-colors hover:text-ink sm:px-6">
        <span>
          All recorded values <span className="text-ink-muted">({rows.length})</span>
        </span>
        <span aria-hidden="true" className="transition-transform group-open:rotate-45">
          +
        </span>
      </summary>
      <div className="overflow-x-auto px-4 pb-4 sm:px-6">
        <table className="w-full border-collapse text-left">
          <caption className="label-mono pb-2 text-left text-ink-faint">{source}</caption>
          <tbody>
            {rows.map((r) => (
              <tr key={r.path} className="border-t border-line">
                <th scope="row" className="py-1.5 pr-4 font-mono text-[11.5px] font-normal text-ink-muted">
                  {r.path}
                </th>
                <td className="py-1.5 text-right font-mono text-[11.5px] text-ink tabular-nums">{r.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
