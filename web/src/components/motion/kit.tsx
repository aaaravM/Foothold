"use client";

/**
 * Foothold motion kit (docs/research/inspiration.md). One easing, soft slow entrances,
 * quick physical hovers. Everything honours reduced motion through <MotionConfig
 * reducedMotion="user"> plus explicit checks, and never leaves content permanently hidden.
 */

import * as React from "react";
import {
  motion,
  useMotionValue,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
  type MotionValue,
} from "motion/react";
import { cn } from "@/lib/utils";

/** Expo-out: the one ease for entrances and glides. */
export const EASE = [0.16, 1, 0.3, 1] as const;
/** Curtain ease for wipes (menus, overlays). */
export const EASE_WIPE = [0.76, 0, 0.24, 1] as const;

const VIEWPORT = { once: true, margin: "0px 0px -10% 0px" } as const;

/* ------------------------------------------------------------------ */
/* Reveal: blur-lift entrance                                          */
/* ------------------------------------------------------------------ */

export interface RevealProps extends React.HTMLAttributes<HTMLDivElement> {
  delay?: number;
  y?: number;
  /** animate on mount instead of when scrolled into view */
  immediate?: boolean;
  as?: "div" | "section" | "li" | "span" | "p";
}

export function Reveal({ delay = 0, y = 22, immediate = false, as = "div", className, children, ...rest }: RevealProps) {
  const reduce = useReducedMotion();
  const Comp = motion[as] as typeof motion.div;
  const hidden = { opacity: 0, y, filter: "blur(8px)" };
  const shown = { opacity: 1, y: 0, filter: "blur(0px)" };
  return (
    <Comp
      className={className}
      initial={reduce ? false : hidden}
      {...(immediate ? { animate: shown } : { whileInView: shown, viewport: VIEWPORT })}
      transition={{ duration: 1.05, ease: EASE, delay }}
      {...(rest as Record<string, unknown>)}
    >
      {children}
    </Comp>
  );
}

/* ------------------------------------------------------------------ */
/* Split-word rise (headings)                                          */
/* ------------------------------------------------------------------ */

export interface SplitWordsProps {
  text: string;
  as?: "h1" | "h2" | "h3" | "p" | "span";
  className?: string;
  delay?: number;
  stagger?: number;
  immediate?: boolean;
  /** words (0-based) painted in the accent colour */
  accent?: number[];
  id?: string;
}

export function SplitWords({ text, as = "h2", className, delay = 0, stagger = 0.05, immediate = false, accent = [], id }: SplitWordsProps) {
  const reduce = useReducedMotion();
  const Comp = motion[as] as typeof motion.h2;
  const words = text.split(" ");
  return (
    <Comp
      id={id}
      aria-label={text}
      className={className}
      initial={reduce ? false : "hidden"}
      {...(immediate ? { animate: "shown" } : { whileInView: "shown", viewport: VIEWPORT })}
      transition={{ staggerChildren: stagger, delayChildren: delay }}
    >
      {words.map((w, i) => (
        <span key={`${w}-${i}`} aria-hidden="true" className="inline-block overflow-hidden pb-[0.12em] align-bottom">
          <motion.span
            className={cn("inline-block will-change-transform", accent.includes(i) && "text-accent")}
            variants={{ hidden: { y: "112%", rotate: 3 }, shown: { y: "0%", rotate: 0 } }}
            transition={{ duration: 1, ease: EASE }}
          >
            {w}
          </motion.span>
          {i < words.length - 1 ? " " : null}
        </span>
      ))}
    </Comp>
  );
}

/* ------------------------------------------------------------------ */
/* Scramble decode (short labels only)                                 */
/* ------------------------------------------------------------------ */

const GLYPHS = "01#%&*+=<>/|_-:;[]{}?!$@";

export interface ScrambleTextProps {
  text: string;
  className?: string;
  duration?: number;
  delay?: number;
  /** replay on hover of the nearest element */
  replayOnHover?: boolean;
}

export function ScrambleText({ text, className, duration = 900, delay = 0, replayOnHover = false }: ScrambleTextProps) {
  const reduce = useReducedMotion();
  const ref = React.useRef<HTMLSpanElement>(null);
  const [run, setRun] = React.useState(0);

  React.useEffect(() => {
    const el = ref.current;
    if (!el || reduce) {
      if (el) el.textContent = text;
      return;
    }
    let raf = 0;
    let start = 0;
    let last = 0;
    let seed = 7 + run;
    const rand = () => {
      seed = (seed * 9301 + 49297) % 233280;
      return seed / 233280;
    };
    const n = text.length;
    const tick = (now: number) => {
      if (!start) start = now + delay;
      const t = Math.max(0, (now - start) / duration);
      if (now - last >= 32 || t >= 1) {
        last = now;
        let out = "";
        for (let i = 0; i < n; i += 1) {
          const ch = text[i];
          if (ch === " " || t >= (i / n) * 0.65 + 0.35) out += ch;
          else out += GLYPHS[Math.floor(rand() * GLYPHS.length)];
        }
        el.textContent = out;
      }
      if (t < 1) raf = requestAnimationFrame(tick);
      else el.textContent = text;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [text, duration, delay, reduce, run]);

  return (
    <span
      className={cn("inline-block", className)}
      onMouseEnter={replayOnHover ? () => setRun((r) => r + 1) : undefined}
      aria-label={text}
    >
      <span ref={ref} aria-hidden="true">
        {text}
      </span>
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Text roll (buttons, nav)                                            */
/* ------------------------------------------------------------------ */

/** Letters roll up on hover of the closest `group` ancestor. Pure CSS (see globals .roll). */
export function TextRoll({ text, className }: { text: string; className?: string }) {
  return (
    <span className={cn("roll", className)} aria-label={text}>
      <span className="roll-row" aria-hidden="true">
        {Array.from(text).map((c, i) => (
          <span key={i} className="roll-ch" style={{ "--i": i } as React.CSSProperties}>
            <span className="roll-a">{c === " " ? " " : c}</span>
            <span className="roll-b">{c === " " ? " " : c}</span>
          </span>
        ))}
      </span>
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Swap arrow                                                          */
/* ------------------------------------------------------------------ */

export function SwapArrow({ className, dir = "right" }: { className?: string; dir?: "right" | "up-right" | "down" }) {
  const path =
    dir === "down" ? "M8 2v12M3 9l5 5 5-5" : dir === "up-right" ? "M4 12 12 4M5 4h7v7" : "M2 8h12M9 3l5 5-5 5";
  return (
    <span aria-hidden="true" className={cn("swap-arrow", `swap-${dir}`, className)}>
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
        <path d={path} />
      </svg>
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
        <path d={path} />
      </svg>
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Magnetic (one primary action per screen)                            */
/* ------------------------------------------------------------------ */

export function Magnetic({ children, strength = 0.28, className }: { children: React.ReactNode; strength?: number; className?: string }) {
  const reduce = useReducedMotion();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 220, damping: 16, mass: 0.4 });
  const sy = useSpring(y, { stiffness: 220, damping: 16, mass: 0.4 });
  const onMove = (e: React.PointerEvent<HTMLSpanElement>) => {
    if (reduce || e.pointerType !== "mouse") return;
    const r = e.currentTarget.getBoundingClientRect();
    x.set((e.clientX - (r.left + r.width / 2)) * strength);
    y.set((e.clientY - (r.top + r.height / 2)) * strength);
  };
  const reset = () => {
    x.set(0);
    y.set(0);
  };
  return (
    <motion.span className={cn("inline-flex", className)} style={{ x: sx, y: sy }} onPointerMove={onMove} onPointerLeave={reset}>
      {children}
    </motion.span>
  );
}

/* ------------------------------------------------------------------ */
/* Tilt card: 3D tilt + accent scan on hover                           */
/* ------------------------------------------------------------------ */

export interface TiltProps extends React.HTMLAttributes<HTMLDivElement> {
  max?: number;
}

export function Tilt({ max = 5, className, children, ...rest }: TiltProps) {
  const reduce = useReducedMotion();
  const rx = useMotionValue(0);
  const ry = useMotionValue(0);
  const srx = useSpring(rx, { stiffness: 160, damping: 18 });
  const sry = useSpring(ry, { stiffness: 160, damping: 18 });
  const onMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (reduce || e.pointerType !== "mouse") return;
    const r = e.currentTarget.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    ry.set(px * max * 2);
    rx.set(-py * max * 2);
  };
  const reset = () => {
    rx.set(0);
    ry.set(0);
  };
  return (
    <div className="[perspective:1200px]">
      <motion.div
        className={cn("tilt group relative", className)}
        style={{ rotateX: srx, rotateY: sry, transformStyle: "preserve-3d" }}
        onPointerMove={onMove}
        onPointerLeave={reset}
        {...(rest as Record<string, unknown>)}
      >
        {children}
        <span aria-hidden="true" className="tilt-scan" />
      </motion.div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Scroll-lit paragraph                                                */
/* ------------------------------------------------------------------ */

function LitWord({ word, progress, range, accent }: { word: string; progress: MotionValue<number>; range: [number, number]; accent: boolean }) {
  const opacity = useTransform(progress, range, [0.22, 1]);
  return (
    <motion.span style={{ opacity }} className={cn("inline", accent && "text-accent")}>
      {word}{" "}
    </motion.span>
  );
}

export function ScrollLit({ text, className, accent = [] }: { text: string; className?: string; accent?: number[] }) {
  const ref = React.useRef<HTMLParagraphElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 0.9", "end 0.55"] });
  const words = text.split(" ");
  const n = words.length;
  if (reduce) {
    return (
      <p ref={ref} className={className}>
        {text}
      </p>
    );
  }
  return (
    <p ref={ref} className={className} aria-label={text}>
      <span aria-hidden="true">
        {words.map((w, i) => {
          const start = i / n;
          const end = Math.min(1, start + (1 / n) * 1.7);
          return <LitWord key={`${w}-${i}`} word={w} progress={scrollYProgress} range={[start, end]} accent={accent.includes(i)} />;
        })}
      </span>
    </p>
  );
}
