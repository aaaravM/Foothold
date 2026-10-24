"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { useMediaQuery, useReducedMotionSafe } from "./use-motion-env";

/** CSS px to millimetres at the CSS reference 96 px per inch. */
export const MM_PER_PX = 25.4 / 96;

export interface CrosshairCursorProps {
  /** Show the mono X/Y readout next to the pointer (default true). */
  readout?: boolean;
  /** Unit conversion for the readout (default CSS px -> mm). */
  mmPerPx?: number;
  /** Hide the native cursor in the scoped area (default false: it becomes a thin crosshair). */
  hideNativeCursor?: boolean;
  className?: string;
}

function fmt(n: number): string {
  return n.toFixed(1).padStart(5, "0");
}

/**
 * CAD-style crosshair scoped to its parent element (the parent must be `position: relative`):
 * full-bleed hairlines through the pointer plus a mono readout of x/y on the sheet in mm.
 * Mouse and pen only (`pointer: fine`); never rendered on touch screens or with reduced motion.
 * Updates write transforms directly (no React re-render per move).
 */
export function CrosshairCursor({ readout = true, mmPerPx = MM_PER_PX, hideNativeCursor = false, className }: CrosshairCursorProps) {
  const reduced = useReducedMotionSafe();
  const fine = useMediaQuery("(pointer: fine)");
  const enabled = fine && !reduced;

  const layerRef = React.useRef<HTMLDivElement>(null);
  const vRef = React.useRef<HTMLDivElement>(null);
  const hRef = React.useRef<HTMLDivElement>(null);
  const boxRef = React.useRef<HTMLDivElement>(null);
  const readRef = React.useRef<HTMLDivElement>(null);
  const textRef = React.useRef<HTMLSpanElement>(null);

  React.useEffect(() => {
    if (!enabled) return;
    const layer = layerRef.current;
    const host = layer?.parentElement;
    const v = vRef.current;
    const h = hRef.current;
    const box = boxRef.current;
    if (!layer || !host || !v || !h || !box) return;

    let raf = 0;
    let x = 0;
    let y = 0;
    let w = 0;
    let hgt = 0;

    const paint = () => {
      raf = 0;
      v.style.transform = `translate3d(${x}px,0,0)`;
      h.style.transform = `translate3d(0,${y}px,0)`;
      box.style.transform = `translate3d(${x - 5}px,${y - 5}px,0)`;
      const read = readRef.current;
      const text = textRef.current;
      if (read && text) {
        text.textContent = `X ${fmt(x * mmPerPx)}  Y ${fmt(y * mmPerPx)} MM`;
        const flipX = x > w - 220;
        const flipY = y > hgt - 48;
        read.style.transform = `translate3d(${flipX ? x - 14 : x + 14}px,${flipY ? y - 14 : y + 14}px,0) translate(${flipX ? "-100%" : "0"},${flipY ? "-100%" : "0"})`;
      }
    };

    const onMove = (e: PointerEvent) => {
      if (e.pointerType === "touch") return;
      const r = host.getBoundingClientRect();
      x = e.clientX - r.left;
      y = e.clientY - r.top;
      w = r.width;
      hgt = r.height;
      layer.dataset.on = "true";
      if (!raf) raf = requestAnimationFrame(paint);
    };
    const onLeave = () => {
      layer.dataset.on = "false";
    };

    const prevCursor = host.style.cursor;
    host.style.cursor = hideNativeCursor ? "none" : "crosshair";
    host.addEventListener("pointermove", onMove, { passive: true });
    host.addEventListener("pointerleave", onLeave);
    return () => {
      if (raf) cancelAnimationFrame(raf);
      host.removeEventListener("pointermove", onMove);
      host.removeEventListener("pointerleave", onLeave);
      host.style.cursor = prevCursor;
    };
  }, [enabled, hideNativeCursor, mmPerPx]);

  if (!enabled) return null;

  return (
    <div
      ref={layerRef}
      aria-hidden="true"
      data-on="false"
      className={cn(
        "pointer-events-none absolute inset-0 z-[5] overflow-hidden opacity-0 transition-opacity duration-200 data-[on=true]:opacity-100",
        className,
      )}
    >
      <div ref={vRef} className="absolute inset-y-0 left-0 w-px bg-ink/20 will-change-transform" />
      <div ref={hRef} className="absolute inset-x-0 top-0 h-px bg-ink/20 will-change-transform" />
      <div ref={boxRef} className="absolute top-0 left-0 size-[11px] border border-ink/70 will-change-transform" />
      {readout ? (
        <div ref={readRef} className="absolute top-0 left-0 will-change-transform">
          <span
            ref={textRef}
            className="label-mono block border border-line bg-background px-1.5 py-0.5 whitespace-pre text-ink-muted"
          >
            X 000.0  Y 000.0 MM
          </span>
        </div>
      ) : null}
    </div>
  );
}
