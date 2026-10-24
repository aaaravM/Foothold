"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MonoLabel } from "@/components/foothold/mono-label";
import { homeFor, roleLabel, signInHref, type Account, type AccountKind } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { useAccount, useDevTokenPending } from "./auth-provider";
import { Brackets, techButtonClass } from "./parts";

export interface RequireAccountProps {
  /** account kind this sheet is for; omit to accept any signed-in account */
  kind?: AccountKind;
  children: (account: Account) => React.ReactNode;
  className?: string;
}

function Panel({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section
      aria-labelledby="access-required-title"
      className={cn("relative max-w-xl border border-line-strong bg-surface p-6 sm:p-8", className)}
    >
      <span aria-hidden="true" className="absolute -top-px -left-px size-3 border-t-2 border-l-2 border-accent" />
      <span aria-hidden="true" className="absolute -right-px -bottom-px size-3 border-r-2 border-b-2 border-accent" />
      <MonoLabel as="p" tone="accent">
        Access required
      </MonoLabel>
      <h2 id="access-required-title" className="mt-3 font-display text-2xl leading-tight text-ink sm:text-3xl">
        {title}
      </h2>
      <div className="mt-4 space-y-5 text-ink-muted">{children}</div>
    </section>
  );
}

/**
 * Guard for account-only sheets (CONTRACTS section 13). Renders children with the account when
 * this tab is signed in with the right kind, otherwise a drawing-style "ACCESS REQUIRED" panel
 * with a sign-in link that returns here (?next=).
 */
export function RequireAccount({ kind, children, className }: RequireAccountProps) {
  const { status, account } = useAccount();
  const devPending = useDevTokenPending();
  const pathname = usePathname() || "/";

  if (status === "loading" || (status === "signed_out" && devPending)) {
    return (
      <div className={cn("py-10", className)} aria-busy="true">
        <MonoLabel as="p">Checking this tab&apos;s session…</MonoLabel>
      </div>
    );
  }

  const here = `${pathname}${typeof window !== "undefined" ? window.location.search : ""}`;

  if (!account) {
    return (
      <Panel title="Sign in to open this sheet." className={className}>
        <p>
          Each browser tab keeps its own session, so you can sign in here without affecting your other tabs.
        </p>
        <Link href={signInHref(here)} className={cn(techButtonClass, "w-full sm:w-auto")}>
          <span>Sign in</span>
          <span aria-hidden="true" className="font-mono text-xs">
            ↵
          </span>
          <Brackets offset={5} />
        </Link>
      </Panel>
    );
  }

  if (kind && account.kind !== kind) {
    return (
      <Panel title={kind === "learner" ? "This sheet is for learner accounts." : "This sheet is for employer accounts."} className={className}>
        <p>
          This tab is signed in as {account.display_name} ({roleLabel(account)}). Open another tab and sign in with a{" "}
          {kind} account, or go to your own home sheet.
        </p>
        <Link href={homeFor(account)} className={cn(techButtonClass, "w-full sm:w-auto")}>
          <span>Go to my sheet</span>
          <span aria-hidden="true" className="font-mono text-xs">
            ↵
          </span>
          <Brackets offset={5} />
        </Link>
      </Panel>
    );
  }

  return <>{children(account)}</>;
}
