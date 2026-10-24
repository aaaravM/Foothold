"use client";

import * as React from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { useAccount } from "@/components/auth/auth-provider";
import { Brackets, drawLinkClass, techButtonClass } from "@/components/auth/parts";
import { KineticWordmark } from "@/components/motion/kinetic-wordmark";
import { ValleyClock } from "@/components/motion/valley-clock";
import { MonoLabel } from "@/components/foothold/mono-label";
import { ProvenanceBadge } from "@/components/foothold/provenance-badge";
import { SourceLink } from "@/components/foothold/source-link";
import { STOCKTON } from "@/lib/sheets";
import { ElevationProfile } from "./elevation-profile";

const PPIC_URL = "https://www.ppic.org/publication/pathways-to-college-completion-in-the-san-joaquin-valley/";
const THESIS = ["Try the job.", "Prove the skill.", "Get the foothold."];

function PrimaryAction() {
  const { account, status } = useAccount();
  const target =
    status !== "signed_in" || !account
      ? { href: "/signin", label: "Sign in to start" }
      : account.kind === "employer"
        ? { href: "/employers", label: "Open the employer desk" }
        : { href: "/sim", label: "Start a workday" };
  return (
    <Link href={target.href} className={techButtonClass}>
      <span>{target.label}</span>
      <span aria-hidden="true" className="font-mono">
        ↵
      </span>
      <Brackets offset={5} />
    </Link>
  );
}

function PpicBars() {
  const rows = [
    { label: "San Joaquin Valley", value: 26, accent: true },
    { label: "Rest of California", value: 35, accent: false },
  ];
  return (
    <dl className="space-y-2" aria-label="Share of ninth graders on a path to a bachelor's degree">
      {rows.map((r, i) => (
        <div key={r.label} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1">
          <dt className="text-xs text-ink-muted">{r.label}</dt>
          <dd className="font-mono text-xs text-ink tabular-nums">{r.value}%</dd>
          <div className="col-span-2 h-2 border border-line" aria-hidden="true">
            <div
              className={cn("fh-draw-x h-full", r.accent ? "bg-accent" : "bg-ink/70")}
              style={{ width: `${r.value}%`, "--d": `${1 + i * 0.2}s` } as React.CSSProperties}
            />
          </div>
        </div>
      ))}
    </dl>
  );
}

export function Hero() {
  return (
    <section aria-label="Cover" className="page-container relative overflow-x-clip pt-6 pb-10">
      <div className="label-mono flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3 text-ink-faint">
        <span>SHEET 00 · COVER · DWG-000 · REV B</span>
        <span className="flex flex-wrap gap-x-4">
          <ValleyClock />
          <span className="hidden sm:inline">
            {STOCKTON.lat} · {STOCKTON.lon}
          </span>
        </span>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-10 lg:grid-cols-12">
        <div className="min-w-0 lg:col-span-9">
          <KineticWordmark as="h1" className="max-w-full text-[clamp(3rem,13.5vw,13rem)] leading-[0.85] text-ink" />
          <p className="mt-6 max-w-[22ch] text-[clamp(1.6rem,3.6vw,2.75rem)] leading-[1.15] font-medium text-ink">
            {THESIS.map((s, i) => (
              <span key={s} className="fh-rise mr-[0.3em] inline-block" style={{ "--d": `${0.5 + i * 0.35}s` } as React.CSSProperties}>
                {i === 2 ? <span className="text-accent">{s}</span> : s}
              </span>
            ))}
          </p>
          <p className="mt-5 max-w-[56ch] text-[17px] leading-relaxed text-ink-muted">
            Career exploration for California&rsquo;s Central Valley. Work a simulated shift, earn skill evidence employers can see without your name on it, and get a
            plan that fits your hours, budget and commute.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-x-8 gap-y-4">
            <PrimaryAction />
            <a href="#try" className={drawLinkClass}>
              Try it here first ↓
            </a>
          </div>
        </div>

        <aside className="space-y-3 border-l border-line pl-4 lg:col-span-3 lg:self-end" aria-labelledby="note-1">
          <MonoLabel as="p" tone="accent" id="note-1">
            Note 1
          </MonoLabel>
          <p className="text-sm leading-relaxed text-ink">
            At current rates, only 26% of San Joaquin Valley ninth graders are on a path to a bachelor&rsquo;s degree, compared with 35% in the rest of California.
          </p>
          <PpicBars />
          <div className="flex flex-wrap items-center gap-2">
            <ProvenanceBadge status="REAL" href={PPIC_URL} />
            <SourceLink href={PPIC_URL} label="PPIC, Aug 2024" mono />
          </div>
        </aside>
      </div>

      <div className="mt-12">
        <ElevationProfile />
      </div>
    </section>
  );
}
