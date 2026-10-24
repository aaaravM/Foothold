"use client";

import * as React from "react";
import Link from "next/link";
import { animate, AnimatePresence, motion, useInView, useMotionValue, useMotionValueEvent, useReducedMotion, useScroll, useTransform, type MotionValue } from "motion/react";
import { cn } from "@/lib/utils";
import { EASE, Reveal, SwapArrow, TextRoll } from "@/components/motion/kit";
import { CirclePreview, PathPreview, TalentPreview, TryShiftPreview } from "./previews";
import { LearnPreview, ProvePreview } from "./stage-previews";

interface Stage {
  id: string;
  verb: string;
  title: string;
  line: string;
  href: string;
  cta: string;
  render: (p?: MotionValue<number>) => React.ReactNode;
}

const STAGES: Stage[] = [
  {
    id: "try",
    verb: "Try",
    title: "Work a real shift.",
    line: "Pick a Valley career and play a simulated day. Coworkers react to every call you make. Try this moment.",
    href: "/sim",
    cta: "Start a workday",
    render: () => <TryShiftPreview />,
  },
  {
    id: "prove",
    verb: "Prove",
    title: "Your skills, shown.",
    line: "Each choice becomes evidence. Your profile fills in from what you did, not what you claim.",
    href: "/sim",
    cta: "Build my profile",
    render: (p) => <ProvePreview progress={p} />,
  },
  {
    id: "plan",
    verb: "Plan",
    title: "A path that fits your week.",
    line: "Real programs near you that respect your hours, budget and drive. Move the slider.",
    href: "/path",
    cta: "Plan my path",
    render: () => <PathPreview />,
  },
  {
    id: "learn",
    verb: "Learn",
    title: "See what's next.",
    line: "The skills graph lights the shortest route from what you have to the job you want.",
    href: "/graph",
    cta: "Open my skills",
    render: (p) => <LearnPreview progress={p} />,
  },
  {
    id: "connect",
    verb: "Connect",
    title: "Get found, on your terms.",
    line: "Employers see your skills without your name. They ask. You decide.",
    href: "/inbox",
    cta: "Open my inbox",
    render: (p) => <TalentPreview progress={p} />,
  },
  {
    id: "belong",
    verb: "Belong",
    title: "You're not doing this alone.",
    line: "A small circle climbing the same way near you, and a coach for hard conversations.",
    href: "/circle",
    cta: "Find my circle",
    render: (p) => <CirclePreview progress={p} />,
  },
];

const N = STAGES.length;
const pad = (n: number) => String(n).padStart(2, "0");

function StageCta({ stage }: { stage: Stage }) {
  return (
    <Link href={stage.href} className="btn-ghost group">
      <TextRoll text={stage.cta} />
      <SwapArrow />
    </Link>
  );
}

/* ------------------------------------------------------------------ */
/* Static stack: phones, tablets and reduced motion                     */
/* ------------------------------------------------------------------ */

/** Plays a stage preview's 0..1 progress once it scrolls into view (stacked layout). */
function InViewPreview({ stage }: { stage: Stage }) {
  const ref = React.useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const p = useMotionValue(reduce ? 1 : 0);
  const seen = useInView(ref, { once: true, margin: "0px 0px -25% 0px" });
  React.useEffect(() => {
    if (!seen || reduce) return;
    const c = animate(p, 1, { duration: 2.4, ease: "easeOut" });
    return () => c.stop();
  }, [seen, reduce, p]);
  return <div ref={ref}>{stage.render(p)}</div>;
}

function StackedStages() {
  return (
    <div className="page-container space-y-[14svh] py-[10svh]">
      {STAGES.map((s, i) => (
        <section key={s.id} id={`stage-${s.id}`} aria-labelledby={`stage-${s.id}-title`} className="grid gap-8 lg:grid-cols-12 lg:items-center">
          <Reveal className="space-y-4 lg:col-span-5">
            <p className="text-sm text-ink-faint">
              <span className="font-mono tabular-nums text-accent">{pad(i + 1)}</span> · {s.verb}
            </p>
            <h2 id={`stage-${s.id}-title`} className="type-display-md text-ink">
              {s.title}
            </h2>
            <p className="max-w-[40ch] text-[17px] leading-relaxed text-ink-muted">{s.line}</p>
            <StageCta stage={s} />
          </Reveal>
          <Reveal delay={0.1} y={30} className="min-w-0 lg:col-span-7">
            <InViewPreview stage={s} />
          </Reveal>
        </section>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sticky stage: desktop with motion                                    */
/* ------------------------------------------------------------------ */

function StageLayer({ stage, index, active, progress }: { stage: Stage; index: number; active: number; progress: MotionValue<number> }) {
  const local = useTransform(progress, (v) => Math.max(0, Math.min(1, v * N - index)));
  const on = index === active;
  const ref = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (on) el.removeAttribute("inert");
    else el.setAttribute("inert", "");
  }, [on]);
  return (
    <motion.div
      ref={ref}
      aria-hidden={!on}
      initial={false}
      animate={
        on
          ? { opacity: 1, y: 0, scale: 1, filter: "blur(0px)", rotateX: 0 }
          : index < active
            ? { opacity: 0, y: -70, scale: 0.94, filter: "blur(8px)", rotateX: 8 }
            : { opacity: 0, y: 90, scale: 0.96, filter: "blur(8px)", rotateX: -8 }
      }
      transition={{ duration: 0.75, ease: EASE }}
      className={cn("absolute inset-0 flex items-center", !on && "pointer-events-none")}
      style={{ transformPerspective: 1400 }}
    >
      <div className="w-full">{stage.render(local)}</div>
    </motion.div>
  );
}

function Rail({ active, progress, onJump }: { active: number; progress: MotionValue<number>; onJump: (i: number) => void }) {
  const fill = useTransform(progress, [0, 1], [0, 1]);
  return (
    <nav aria-label="Stages" className="relative">
      <div aria-hidden="true" className="absolute top-2 bottom-2 left-[5px] w-px bg-ink/12">
        <motion.div className="h-full w-full origin-top bg-accent" style={{ scaleY: fill }} />
      </div>
      <ol className="space-y-1">
        {STAGES.map((s, i) => {
          const on = i === active;
          return (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => onJump(i)}
                aria-current={on ? "step" : undefined}
                className={cn(
                  "group relative flex items-center gap-4 rounded-full py-1.5 pr-3 text-left text-[15px] transition-colors duration-300",
                  on ? "text-ink" : i < active ? "text-ink-muted hover:text-ink" : "text-ink-faint hover:text-ink-muted",
                )}
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    "relative z-10 size-[11px] rounded-full border transition-all duration-300",
                    on ? "scale-125 border-accent bg-accent" : i < active ? "border-accent bg-bg" : "border-line-strong bg-bg",
                  )}
                />
                <span className="font-mono text-[12px] tabular-nums opacity-70">{pad(i + 1)}</span>
                <span className={cn("transition-transform duration-300", on && "translate-x-1")}>{s.verb}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function StickyStages() {
  const ref = React.useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });
  const [active, setActive] = React.useState(0);
  useMotionValueEvent(scrollYProgress, "change", (v) => {
    const i = Math.max(0, Math.min(N - 1, Math.floor(v * N)));
    setActive((cur) => (cur === i ? cur : i));
  });

  const jump = (i: number) => {
    const el = ref.current;
    if (!el) return;
    const top = el.getBoundingClientRect().top + window.scrollY;
    const span = el.offsetHeight - window.innerHeight;
    window.scrollTo({ top: top + span * ((i + 0.35) / N), behavior: "smooth" });
  };

  const stage = STAGES[active];
  const words = stage.title.split(" ");

  return (
    <div ref={ref} style={{ height: `${N * 85 + 15}svh` }} className="relative">
      <div className="sticky top-[var(--nav-h)] h-[calc(100svh-var(--nav-h))]">
        <div className="page-container grid h-full grid-cols-12 items-center gap-10">
          <div className="col-span-5 flex h-full flex-col justify-center gap-12 py-10">
            <Rail active={active} progress={scrollYProgress} onJump={jump} />
            <div className="min-h-[15rem]" aria-live="polite">
              <AnimatePresence mode="wait" initial={false}>
                <motion.div key={stage.id} exit={{ opacity: 0, y: -14, filter: "blur(4px)" }} transition={{ duration: 0.25, ease: EASE }}>
                  <h2 className="type-display-md text-ink">
                    {words.map((w, wi) => (
                      <span key={wi} className="mr-[0.25em] inline-block overflow-hidden pb-[0.08em] align-bottom last:mr-0">
                        <motion.span
                          className="inline-block"
                          initial={{ y: "105%" }}
                          animate={{ y: "0%" }}
                          transition={{ duration: 0.6, ease: EASE, delay: 0.04 * wi }}
                        >
                          {w}
                        </motion.span>
                      </span>
                    ))}
                  </h2>
                  <motion.p
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, ease: EASE, delay: 0.18 }}
                    className="mt-4 max-w-[38ch] text-[17px] leading-relaxed text-ink-muted"
                  >
                    {stage.line}
                  </motion.p>
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4, delay: 0.3 }} className="mt-6">
                    <StageCta stage={stage} />
                  </motion.div>
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
          <div className="relative col-span-7 h-full max-h-[46rem]">
            {STAGES.map((s, i) => (
              <StageLayer key={s.id} stage={s} index={i} active={active} progress={scrollYProgress} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function useWide() {
  const [wide, setWide] = React.useState(false);
  React.useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px) and (min-height: 640px)");
    const on = () => setWide(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return wide;
}

/** The app's six stages, played by scrolling (sticky stage on desktop, a calm stack otherwise). */
export function StageScroll() {
  const reduce = useReducedMotion();
  const wide = useWide();
  return (
    <section id="stages" aria-label="How Foothold works" className="relative">
      {wide && !reduce ? <StickyStages /> : <StackedStages />}
    </section>
  );
}
