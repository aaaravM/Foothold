"use client";

import * as React from "react";
import { usePathname } from "next/navigation";

/**
 * Foothold's ambient signature: one fixed dot grid behind every page. Dots warm toward the
 * accent near the pointer, the grid drifts slowly with scroll, and on story pages the dots
 * gather into a "formation" (a rising staircase, a ring) that morphs between routes.
 * 30 fps cap, paused when the tab is hidden, static for reduced motion, pointer-events none.
 */

type Formation = "steps" | "ring" | "none";

function formationFor(pathname: string | null): { kind: Formation; strength: number } {
  const p = pathname ?? "/";
  if (p === "/") return { kind: "steps", strength: 1 };
  if (p.startsWith("/signup") || p.startsWith("/signin") || p.startsWith("/onboarding")) return { kind: "none", strength: 0.8 };
  if (p.startsWith("/circle")) return { kind: "ring", strength: 0.55 };
  return { kind: "none", strength: 0.55 };
}

function parseColor(v: string, fallback: [number, number, number]): [number, number, number] {
  const s = v.trim();
  const m = /^#([0-9a-f]{6})$/i.exec(s);
  if (!m) return fallback;
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** 0..1 how strongly a dot at (x, y) belongs to a formation (viewport px). */
function maskAt(kind: Formation, x: number, y: number, w: number, h: number): number {
  if (kind === "none") return 0;
  if (kind === "ring") {
    const cx = w * 0.78;
    const cy = h * 0.42;
    const r = Math.min(w, h) * 0.26;
    const d = Math.abs(Math.hypot(x - cx, y - cy) - r);
    return Math.max(0, 1 - d / 26);
  }
  // steps: a staircase rising from lower-middle to upper-right (the wordmark's shape)
  const x0 = w * (w < 760 ? 0.08 : 0.5);
  const x1 = w * 0.97;
  const y0 = h * 0.86;
  const y1 = h * 0.2;
  if (x < x0 - 30 || x > x1 + 30) return 0;
  const steps = 4;
  const sw = (x1 - x0) / steps;
  const sh = (y0 - y1) / steps;
  let best = 1e9;
  for (let i = 0; i < steps; i += 1) {
    const yi = y0 - i * sh;
    const xa = x0 + i * sw;
    const xb = xa + sw;
    // tread
    if (x >= xa && x <= xb) best = Math.min(best, Math.abs(y - yi));
    // riser at xb
    if (y <= yi && y >= yi - sh) best = Math.min(best, Math.abs(x - xb));
  }
  return Math.max(0, 1 - best / 22);
}

export function DotField() {
  const pathname = usePathname();
  const ref = React.useRef<HTMLCanvasElement>(null);
  const target = React.useRef(formationFor(pathname));

  React.useEffect(() => {
    target.current = formationFor(pathname);
  }, [pathname]);

  React.useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const GAP = 22;
    let w = 0;
    let h = 0;
    let dpr = 1;
    let raf = 0;
    let last = 0;
    let running = true;
    const pointer = { x: -9999, y: -9999, tx: -9999, ty: -9999 };
    // formation morph state
    let fromKind: Formation = target.current.kind;
    let toKind: Formation = target.current.kind;
    let fromStrength = target.current.strength;
    let toStrength = target.current.strength;
    let morphStart = 0;
    let ink: [number, number, number] = [244, 244, 241];
    let accent: [number, number, number] = [231, 178, 74];

    const readColors = () => {
      const cs = getComputedStyle(document.documentElement);
      ink = parseColor(cs.getPropertyValue("--ink"), ink);
      accent = parseColor(cs.getPropertyValue("--accent"), accent);
    };

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (now: number) => {
      const t = target.current;
      if (t.kind !== toKind || t.strength !== toStrength) {
        fromKind = toKind;
        fromStrength = toStrength;
        toKind = t.kind;
        toStrength = t.strength;
        morphStart = now;
      }
      const m = reduce ? 1 : Math.min(1, (now - morphStart) / 1200);
      const me = 1 - Math.pow(1 - m, 3);
      pointer.x += (pointer.tx - pointer.x) * 0.18;
      pointer.y += (pointer.ty - pointer.y) * 0.18;
      const scroll = reduce ? 0 : window.scrollY * 0.15;
      const off = scroll % GAP;
      const isLight = document.documentElement.dataset.theme === "light";
      const base = isLight ? 0.1 : 0.07;
      const strength = fromStrength + (toStrength - fromStrength) * me;
      // the formation fades out with scroll so it never sits under reading text
      const fade = Math.max(0, 1 - window.scrollY / (h * 0.9));
      ctx.clearRect(0, 0, w, h);
      for (let y = GAP / 2 - off; y < h + GAP; y += GAP) {
        for (let x = GAP / 2; x < w; x += GAP) {
          const fa = fromKind === "none" ? 0 : maskAt(fromKind, x, y + scroll * 0.0, w, h);
          const fb = toKind === "none" ? 0 : maskAt(toKind, x, y, w, h);
          const f = (fa * (1 - me) + fb * me) * fade;
          const dx = x - pointer.x;
          const dy = y - pointer.y;
          const r = Math.sqrt(dx * dx + dy * dy);
          let p = 0;
          if (r < 300 && !reduce) p = (1 - r / 300) * (0.55 + 0.45 * Math.sin(r / 38 - now / 520));
          const a = (base + f * 0.75) * strength + Math.max(0, p) * 0.5;
          const mix = Math.min(1, f * 0.85 + Math.max(0, p));
          const cr = ink[0] + (accent[0] - ink[0]) * mix;
          const cg = ink[1] + (accent[1] - ink[1]) * mix;
          const cb = ink[2] + (accent[2] - ink[2]) * mix;
          const size = 1.1 + f * 1.3 + Math.max(0, p) * 0.9;
          ctx.fillStyle = `rgba(${cr | 0},${cg | 0},${cb | 0},${Math.min(0.9, a)})`;
          ctx.fillRect(x - size / 2, y - size / 2, size, size);
        }
      }
    };

    const loop = (now: number) => {
      if (!running) return;
      raf = requestAnimationFrame(loop);
      if (now - last < 33) return;
      last = now;
      draw(now);
    };

    readColors();
    resize();
    const onResize = () => {
      resize();
      if (reduce) draw(performance.now());
    };
    const onMove = (e: PointerEvent) => {
      if (e.pointerType !== "mouse") return;
      pointer.tx = e.clientX;
      pointer.ty = e.clientY;
      if (pointer.x < -9000) {
        pointer.x = e.clientX;
        pointer.y = e.clientY;
      }
    };
    const onLeave = () => {
      pointer.tx = -9999;
      pointer.ty = -9999;
    };
    const onVis = () => {
      if (document.hidden) {
        running = false;
        cancelAnimationFrame(raf);
      } else if (!reduce && !running) {
        running = true;
        raf = requestAnimationFrame(loop);
      }
    };
    const themeObs = new MutationObserver(() => {
      readColors();
      if (reduce) draw(performance.now());
    });
    themeObs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    window.addEventListener("resize", onResize);
    window.addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("pointerleave", onLeave);
    document.addEventListener("visibilitychange", onVis);
    if (reduce) {
      running = false;
      draw(performance.now());
    } else {
      raf = requestAnimationFrame(loop);
    }
    return () => {
      running = false;
      cancelAnimationFrame(raf);
      themeObs.disconnect();
      window.removeEventListener("resize", onResize);
      window.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerleave", onLeave);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);

  return <canvas ref={ref} aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10" />;
}
