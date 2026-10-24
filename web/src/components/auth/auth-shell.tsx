"use client";

import * as React from "react";
import { Reveal, SplitWords } from "@/components/motion/kit";

/** Shared frame for sign in / sign up: one big line on the left, the form on the right. */
export function AuthShell({ title, accent, lead, children, aside }: { title: string; accent?: number[]; lead: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <div className="page-container grid flex-1 grid-cols-1 items-start gap-10 py-[8svh] lg:grid-cols-12 lg:gap-16 lg:py-[12svh]">
      <div className="lg:col-span-6">
        <SplitWords as="h1" immediate text={title} accent={accent} className="max-w-[14ch] font-display text-[clamp(2.75rem,6vw,5.5rem)] leading-[0.94] font-bold tracking-[-0.045em] text-ink" />
        <Reveal immediate delay={0.45} className="mt-6 max-w-[40ch] text-[18px] leading-relaxed text-ink-muted">
          {lead}
        </Reveal>
        {aside ? (
          <Reveal immediate delay={0.6} className="mt-10 hidden lg:block">
            {aside}
          </Reveal>
        ) : null}
      </div>
      <Reveal immediate delay={0.25} y={30} className="lg:col-span-5 lg:col-start-8">
        <div className="soft-card p-6 sm:p-8">{children}</div>
      </Reveal>
    </div>
  );
}

export function FieldLabel({ htmlFor, children, hint }: { htmlFor: string; children: React.ReactNode; hint?: React.ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="mb-2 flex items-baseline justify-between gap-3 text-sm font-medium text-ink">
      <span>{children}</span>
      {hint ? <span className="text-xs font-normal text-ink-faint">{hint}</span> : null}
    </label>
  );
}
