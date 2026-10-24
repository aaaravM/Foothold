"use client";

import * as React from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { useAccount } from "@/components/auth/auth-provider";
import { Reveal, SplitWords, SwapArrow, TextRoll } from "@/components/motion/kit";

export interface FeatureCtaProps {
  /** where a learner goes */
  href: string;
  label: string;
  /** where an employer goes instead (defaults to href) */
  employerHref?: string;
  employerLabel?: string;
}

/** One clear call to action: straight into the feature when signed in, through sign-up otherwise. */
export function FeatureCta({ href, label, employerHref, employerLabel }: FeatureCtaProps) {
  const { account, status } = useAccount();
  const signedIn = status === "signed_in" && !!account;
  const isEmployer = signedIn && account?.kind === "employer";
  const dest = isEmployer ? (employerHref ?? href) : href;
  const text = isEmployer ? (employerLabel ?? label) : label;
  const target = signedIn ? dest : `/signup?next=${encodeURIComponent(dest)}`;
  return (
    <Link href={target} className="btn-ghost group">
      <TextRoll text={text} />
      <SwapArrow />
    </Link>
  );
}

export interface FeatureSectionProps {
  id: string;
  step: string;
  title: string;
  body: React.ReactNode;
  cta: FeatureCtaProps;
  /** live preview shown beside the text */
  children: React.ReactNode;
  flip?: boolean;
}

/** A landing chapter: what you do in Foothold, a live preview, one call to action. */
export function FeatureSection({ id, step, title, body, cta, children, flip = false }: FeatureSectionProps) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="grid scroll-mt-24 grid-cols-1 items-center gap-10 py-[8svh] lg:grid-cols-12 lg:gap-16">
      <div className={cn("flex flex-col gap-5 lg:col-span-5", flip && "lg:order-2")}>
        <Reveal>
          <span className="kicker">{step}</span>
        </Reveal>
        <SplitWords id={`${id}-title`} text={title} className="type-display-md text-ink" />
        <Reveal delay={0.1} className="max-w-[46ch] space-y-3 text-[17px] leading-relaxed text-ink-muted">
          {body}
        </Reveal>
        <Reveal delay={0.2} className="mt-1">
          <FeatureCta {...cta} />
        </Reveal>
      </div>
      <Reveal delay={0.15} y={36} className={cn("min-w-0 lg:col-span-7", flip && "lg:order-1")}>
        {children}
      </Reveal>
    </section>
  );
}

/** Soft panel that frames a live preview. */
export function PreviewPanel({ label, aside, children, className }: { label: string; aside?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("soft-card overflow-hidden", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2 px-5 pt-4">
        <span className="inline-flex items-center gap-2 text-sm text-ink-muted">
          <span aria-hidden="true" className="size-1.5 rounded-full bg-accent" />
          {label}
        </span>
        {aside ? <span className="flex flex-wrap items-center gap-2">{aside}</span> : null}
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

export function PreviewOffline({ what }: { what: string }) {
  return (
    <p role="status" className="text-sm text-ink-muted">
      The live {what} will appear here once Foothold is reachable.
    </p>
  );
}
