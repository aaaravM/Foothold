"use client";

/**
 * Small motion kit for the app screens (Sim, Path, Employers, Inbox, Circle, Skills).
 * Expo-out easing, soft blur-lift entrances, a scramble decode for short labels, a pointer tilt
 * for cards. Everything respects prefers-reduced-motion.
 */
import * as React from "react";
import { motion, useMotionValue, useReducedMotion, useSpring, useTransform, type HTMLMotionProps } from "motion/react";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

export const EASE = [0.16, 1, 0.3, 1] as const;

/** Blur-lift entrance. Use `delay` or wrap siblings in <Stagger>. */
export function Reveal({
  delay = 0,
  y = 18,
  className,
  children,
  inView = false,
  ...rest
}: { delay?: number; y?: number; inView?: boolean } & HTMLMotionProps<"div">) {
  const reduce = useReducedMotion();
  const from = reduce ? { opacity: 0 } : { opacity: 0, y, filter: "blur(8px)" };
  const to = reduce ? { opacity: 1 } : { opacity: 1, y: 0, filter: "blur(0px)" };
  const t = { duration: reduce ? 0.2 : 0.9, ease: EASE, delay };
  return inView ? (
    <motion.div initial={from} whileInView={to} viewport={{ once: true, margin: "0px 0px -10% 0px" }} transition={t} className={className} {...rest}>
      {children}
    </motion.div>
  ) : (
    <motion.div initial={from} animate={to} transition={t} className={className} {...rest}>
      {children}
    </motion.div>
  );
}

export const staggerParent = (stagger = 0.06, delayChildren = 0) => ({
  hidden: {},
  show: { transition: { staggerChildren: stagger, delayChildren } },
});
export const staggerChild = {
  hidden: { opacity: 0, y: 16, filter: "blur(6px)" },
  show: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.8, ease: EASE } },
};

/** Quiet sentence-case kicker: accent dot, words, a hairline that draws in. */
export function Kicker({ children, className }: { children: React.ReactNode; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <p className={cn("flex items-center gap-2.5 text-sm text-ink-muted", className)}>
      <span aria-hidden="true" className="size-1.5 rounded-full bg-accent" />
      <span>{children}</span>
      <motion.span
        aria-hidden="true"
        className="h-px w-10 origin-left bg-line-strong"
        initial={reduce ? false : { scaleX: 0 }}
        animate={{ scaleX: 1 }}
        transition={{ duration: 1.2, ease: EASE, delay: 0.2 }}
      />
    </p>
  );
}

const GLYPHS = "01#%&*+=<>/|_-:;[]{}?!$@";

/** Decodes a short label from random glyphs. Replays when `replayKey` changes. */
export function ScrambleText({ text, duration = 900, replayKey, className }: { text: string; duration?: number; replayKey?: unknown; className?: string }) {
  const reduce = useReducedMotion();
  const [out, setOut] = React.useState(text);
  React.useEffect(() => {
    if (reduce || text.length > 40) return;
    let raf = 0;
    let last = 0;
    const t0 = performance.now();
    const n = text.length;
    const tick = (now: number) => {
      const t = Math.min(1, (now - t0) / duration);
      if (now - last > 32 || t === 1) {
        last = now;
        let s = "";
        for (let i = 0; i < n; i++) {
          const ch = text[i];
          if (ch === " " || t >= (i / n) * 0.65 + 0.35) s += ch;
          else s += GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
        }
        setOut(s);
      }
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [text, duration, replayKey, reduce]);
  return (
    <span className={className} aria-label={text}>
      <span aria-hidden="true">{reduce || text.length > 40 ? text : out}</span>
    </span>
  );
}

/** Pointer tilt (fine pointers only), spring {160, 18}. Children render inside. */
export function TiltCard({ className, children, max = 5, ...rest }: { max?: number } & HTMLMotionProps<"div">) {
  const reduce = useReducedMotion();
  const px = useMotionValue(0.5);
  const py = useMotionValue(0.5);
  const sx = useSpring(px, { stiffness: 160, damping: 18 });
  const sy = useSpring(py, { stiffness: 160, damping: 18 });
  const rotateY = useTransform(sx, [0, 1], [-max, max]);
  const rotateX = useTransform(sy, [0, 1], [max, -max]);
  const glowX = useTransform(sx, (v) => `${v * 100}%`);
  const glowY = useTransform(sy, (v) => `${v * 100}%`);
  const onMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (reduce || e.pointerType !== "mouse") return;
    const r = e.currentTarget.getBoundingClientRect();
    px.set((e.clientX - r.left) / r.width);
    py.set((e.clientY - r.top) / r.height);
  };
  const onLeave = () => {
    px.set(0.5);
    py.set(0.5);
  };
  return (
    <motion.div
      onPointerMove={onMove}
      onPointerLeave={onLeave}
      style={reduce ? undefined : { rotateX, rotateY, transformPerspective: 1200, ["--gx" as string]: glowX, ["--gy" as string]: glowY }}
      className={cn("relative", className)}
      {...rest}
    >
      {children}
    </motion.div>
  );
}

/** Animated number that tweens between values (for stats and money). */
export function Tween({ value, format = (n) => String(Math.round(n)), className }: { value: number; format?: (n: number) => string; className?: string }) {
  const reduce = useReducedMotion();
  const mv = useMotionValue(value);
  const spring = useSpring(mv, { stiffness: 90, damping: 20 });
  const [shown, setShown] = React.useState(value);
  React.useEffect(() => {
    mv.set(value);
  }, [value, mv, reduce]);
  React.useEffect(() => spring.on("change", (v) => setShown(v)), [spring]);
  return <span className={cn("tabular-nums", className)}>{format(reduce ? value : shown)}</span>;
}

/** Arrow that swaps out/in on group hover. */
export function SwapArrow({ className }: { className?: string }) {
  return (
    <span aria-hidden="true" className={cn("relative inline-block size-[0.9em] shrink-0 overflow-hidden", className)}>
      <span className="absolute inset-0 grid place-items-center transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:translate-x-full"><ArrowRight className="size-full" strokeWidth={2} /></span>
      <span className="absolute inset-0 grid -translate-x-full place-items-center transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:translate-x-0">
        <ArrowRight className="size-full" strokeWidth={2} />
      </span>
    </span>
  );
}

/** Primary pill button class (one per screen). */
export const primaryPill =
  "group relative inline-flex items-center gap-3 overflow-hidden rounded-full bg-accent px-6 py-3 text-sm font-medium text-accent-ink transition-[transform,box-shadow] duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] hover:shadow-[0_0_0_6px_color-mix(in_oklab,var(--accent)_18%,transparent)] active:scale-[0.98] disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent";
export const ghostPill =
  "group inline-flex items-center gap-2 rounded-full border border-line px-4 py-2 text-sm text-ink transition-colors duration-300 hover:border-line-strong hover:bg-surface disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";
export const softCard = "rounded-2xl border border-line bg-surface/40";

const QUIET_TONE: Record<string, string> = {
  faint: "text-ink-faint",
  muted: "text-ink-muted",
  ink: "text-ink",
  accent: "text-accent",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
  info: "text-info",
};

/** Drop-in replacement for MonoLabel on app screens: sentence case, small, calm (no tracked uppercase). */
export function QuietLabel({
  as = "span",
  tone = "faint",
  size,
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLElement> & { as?: string; tone?: string; size?: "xs" | "sm"; htmlFor?: string }) {
  const Comp = as as React.ElementType;
  void size;
  return (
    <Comp className={cn("text-[13px] leading-5", QUIET_TONE[tone] ?? "text-ink-faint", className)} {...props}>
      {children}
    </Comp>
  );
}
