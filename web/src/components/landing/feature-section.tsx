"use client";

import * as React from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { useAccount } from "@/components/auth/auth-provider";
import { Brackets, techButtonClass } from "@/components/auth/parts";
import { MonoLabel } from "@/components/foothold/mono-label";

export interface FeatureCtaProps {
  /** where a learner goes */
  href: string;
  label: string;
  /** where an employer goes instead (defaults to href) */
  employerHref?: string;
  employerLabel?: string;
}

/** One clear call to action: straight into the feature when signed in, through sign-in otherwise. */
export function FeatureCta({ href, label, employerHref, employerLabel }: FeatureCtaProps) {
  const { account, status } = useAccount();
  const signedIn = status === "signed_in" && !!account;
  const isEmployer = signedIn && account?.kind === "employer";
  const dest = isEmployer ? (employerHref ?? href) : href;
  const text = isEmployer ? (employerLabel ?? label) : label;
  const target = signedIn ? dest : `/signin?next=${encodeURIComponent(dest)}`;
  return (
    <Link href={target} className={cn(techButtonClass, "h-11")}>
      <span>{signedIn ? text : `Sign in · ${text}`}</span>
      <span aria-hidden="true" className="font-mono">
        →
      </span>
      <Brackets offset={5} />
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

/** A landing section: what you do in Foothold, with a live preview and one call to action. */
export function FeatureSection({ id, step, title, body, cta, children, flip = false }: FeatureSectionProps) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="grid scroll-mt-24 grid-cols-1 gap-6 border-b border-line py-12 lg:grid-cols-12 lg:gap-10">
      <div className={cn("flex flex-col gap-4 lg:col-span-5", flip && "lg:order-2")}>
        <MonoLabel as="p" tone="accent">
          {step}
        </MonoLabel>
        <h2 id={`${id}-title`} className="type-display-md text-ink">
          {title}
        </h2>
        <div className="max-w-[52ch] space-y-3 text-[17px] leading-relaxed text-ink-muted">{body}</div>
        <div className="mt-2">
          <FeatureCta {...cta} />
        </div>
      </div>
      <div className={cn("min-w-0 lg:col-span-7", flip && "lg:order-1")}>{children}</div>
    </section>
  );
}

/** Bordered panel that frames a live preview. */
export function PreviewPanel({ label, aside, children, className }: { label: string; aside?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("border border-line bg-bg", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2">
        <MonoLabel>{label}</MonoLabel>
        {aside ? <span className="flex flex-wrap items-center gap-2">{aside}</span> : null}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

export function PreviewOffline({ what }: { what: string }) {
  return (
    <p role="status" className="text-sm text-warning">
      API offline: the live {what} needs the Foothold API, which isn&rsquo;t reachable right now.
    </p>
  );
}
