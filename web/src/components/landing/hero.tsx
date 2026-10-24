"use client";

import * as React from "react";
import Link from "next/link";
import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import { useAccount } from "@/components/auth/auth-provider";
import { KineticWordmark } from "@/components/motion/kinetic-wordmark";
import { Magnetic, SwapArrow, TextRoll } from "@/components/motion/kit";

const THESIS = ["Try the job.", "Prove the skill.", "Get the foothold."];

function PrimaryAction() {
  const { account, status } = useAccount();
  const target =
    status !== "signed_in" || !account
      ? { href: "/signup", label: "Start free" }
      : account.kind === "employer"
        ? { href: "/employers", label: "Open employer desk" }
        : { href: "/sim", label: "Start a workday" };
  return (
    <Magnetic>
      <Link href={target.href} className="btn-primary group">
        <TextRoll text={target.label} />
        <SwapArrow />
      </Link>
    </Magnetic>
  );
}

/**
 * The opening: the kinetic wordmark (letters clip in while the Hubot Sans width axis spreads
 * from condensed to wide), the three-line thesis rising beneath it, one action. As you scroll
 * away the word drifts up and softens, handing over to the stage sequence below.
 */
export function Hero() {
  const ref = React.useRef<HTMLElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const wordY = useTransform(scrollYProgress, [0, 1], [0, reduce ? 0 : -120]);
  const wordFade = useTransform(scrollYProgress, [0, 0.75], [1, reduce ? 1 : 0.15]);
  const restY = useTransform(scrollYProgress, [0, 1], [0, reduce ? 0 : -40]);
  const cueFade = useTransform(scrollYProgress, [0, 0.15], [1, 0]);

  return (
    <section
      ref={ref}
      aria-label="Foothold"
      className="page-container relative flex min-h-[calc(100svh-var(--nav-h))] flex-col justify-center overflow-x-clip pt-10 pb-24"
    >
      <p className="kicker fh-rise" style={{ "--d": "0.1s" } as React.CSSProperties}>
        Careers in California&rsquo;s Central Valley
      </p>

      <motion.div style={{ y: wordY, opacity: wordFade }} className="mt-6 min-w-0">
        <KineticWordmark as="h1" className="max-w-full text-[clamp(4.2rem,17.5vw,17rem)] text-ink" />
      </motion.div>

      <motion.div style={{ y: restY }} className="mt-8 grid gap-8 lg:grid-cols-12 lg:items-end">
        <p className="text-[clamp(1.6rem,3.4vw,2.9rem)] leading-[1.1] font-medium tracking-[-0.02em] text-ink lg:col-span-7">
          {THESIS.map((s, i) => (
            <span key={s} className="fh-rise mr-[0.3em] inline-block" style={{ "--d": `${0.7 + i * 0.3}s` } as React.CSSProperties}>
              {i === 2 ? <span className="text-accent">{s}</span> : s}
            </span>
          ))}
        </p>
        <div className="fh-rise space-y-6 lg:col-span-5 lg:pb-1" style={{ "--d": "1.6s" } as React.CSSProperties}>
          <p className="max-w-[42ch] text-[17px] leading-relaxed text-ink-muted">
            Work a real-feeling shift with AI coworkers, get a plan that fits your week, and let employers find you for what you can do.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <PrimaryAction />
            <a href="#stages" className="btn-ghost group">
              <TextRoll text="See how it works" />
              <SwapArrow dir="down" />
            </a>
          </div>
        </div>
      </motion.div>

      <motion.div
        style={{ opacity: cueFade }}
        aria-hidden="true"
        className="fh-fade pointer-events-none absolute bottom-6 left-1/2 hidden -translate-x-1/2 flex-col items-center gap-2 text-xs text-ink-faint sm:flex"
      >
        <span>Scroll</span>
        <span className="fh-scroll-cue relative h-10 w-px overflow-hidden bg-ink/15" />
      </motion.div>
    </section>
  );
}
