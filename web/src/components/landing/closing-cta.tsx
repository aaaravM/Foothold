"use client";

import * as React from "react";
import Link from "next/link";
import { useAccount } from "@/components/auth/auth-provider";
import { homeFor } from "@/lib/auth";
import { Magnetic, Reveal, SplitWords, SwapArrow, TextRoll } from "@/components/motion/kit";

export function ClosingCta() {
  const { account, status } = useAccount();
  const signedIn = status === "signed_in" && !!account;
  return (
    <section aria-labelledby="closing-title" className="page-container py-[18svh]">
      <div className="flex flex-col items-start gap-8">
        <SplitWords id="closing-title" text="Start your first shift." accent={[3]} className="max-w-[16ch] type-display-lg text-ink" />
        <Reveal delay={0.2} className="flex flex-wrap items-center gap-3">
          <Magnetic>
            <Link href={signedIn ? homeFor(account) : "/signup"} className="btn-primary group">
              <TextRoll text={signedIn ? "Pick up where you left off" : "Create your account"} />
              <SwapArrow />
            </Link>
          </Magnetic>
          {!signedIn ? (
            <Link href="/signin" className="btn-ghost group">
              <TextRoll text="I have an account" />
            </Link>
          ) : null}
        </Reveal>
      </div>
    </section>
  );
}
