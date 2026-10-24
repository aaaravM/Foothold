"use client";

import * as React from "react";
import { motion, useReducedMotion } from "motion/react";
import { LocateFixed } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Place } from "@/lib/profile";
import { EASE } from "@/components/motion/kit";

/* Rough frame of the Central Valley (Sacramento to Bakersfield). */
const LAT_N = 38.85;
const LAT_S = 35.05;
const LON_W = -121.85;
const LON_E = -118.75;
const W = 300;
const H = 360;

function project(lat: number, lon: number): [number, number] {
  return [((lon - LON_W) / (LON_E - LON_W)) * W, ((LAT_N - lat) / (LAT_N - LAT_S)) * H];
}

/** Dots that sketch the valley floor: a band along the Sacramento to Bakersfield axis. */
function valleyDots(): [number, number][] {
  const [ax, ay] = project(38.75, -121.55);
  const [bx, by] = project(35.15, -118.95);
  const len = Math.hypot(bx - ax, by - ay);
  const out: [number, number][] = [];
  for (let y = 6; y < H; y += 12) {
    for (let x = 6; x < W; x += 12) {
      const t = ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / (len * len);
      if (t < -0.02 || t > 1.02) continue;
      const px = ax + t * (bx - ax);
      const py = ay + t * (by - ay);
      const d = Math.hypot(x - px, y - py);
      const half = 34 + Math.sin(t * Math.PI) * 26;
      if (d < half) out.push([x, y]);
    }
  }
  return out;
}

const DOTS = valleyDots();

export function haversineKm(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const r = 6371;
  const dLat = ((bLat - aLat) * Math.PI) / 180;
  const dLon = ((bLon - aLon) * Math.PI) / 180;
  const s = Math.sin(dLat / 2) ** 2 + Math.cos((aLat * Math.PI) / 180) * Math.cos((bLat * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(s));
}

export function nearestPlace(places: Place[], lat: number, lon: number): Place | null {
  let best: Place | null = null;
  let bestD = Infinity;
  for (const p of places) {
    const d = haversineKm(lat, lon, p.lat, p.lon);
    if (d < bestD) {
      bestD = d;
      best = p;
    }
  }
  return best;
}

/** "Use my location": browser geolocation, matched to the nearest Foothold place. */
export function useLocate(places: Place[], onFound: (p: Place) => void) {
  const [state, setState] = React.useState<"idle" | "busy" | "denied">("idle");
  const locate = React.useCallback(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setState("denied");
      return;
    }
    setState("busy");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const p = nearestPlace(places, pos.coords.latitude, pos.coords.longitude);
        setState("idle");
        if (p) onFound(p);
      },
      () => setState("denied"),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 600_000 },
    );
  }, [places, onFound]);
  return { state, locate };
}

export interface PlacePickerProps {
  places: Place[];
  value: string | null;
  onChange: (id: string) => void;
  className?: string;
}

/** A dot map of the valley plus a list of towns. Hover a town to find it on the map. */
export function PlacePicker({ places, value, onChange, className }: PlacePickerProps) {
  const reduce = useReducedMotion();
  const [hover, setHover] = React.useState<string | null>(null);
  const onFound = React.useCallback((p: Place) => onChange(p.id), [onChange]);
  const { state, locate } = useLocate(places, onFound);
  const focus = hover ?? value;
  const selected = places.find((p) => p.id === value) ?? null;

  return (
    <div className={cn("grid gap-6 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] md:items-center", className)}>
      <div className="relative mx-auto w-full max-w-[300px]">
        <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={selected ? `Map: ${selected.name} selected` : "Map of the Central Valley"}>
          {DOTS.map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r={1.1} className="fill-ink/20" />
          ))}
          {places.map((p) => {
            const [x, y] = project(p.lat, p.lon);
            const on = p.id === value;
            const hot = p.id === focus;
            return (
              <g key={p.id} className="cursor-pointer" onClick={() => onChange(p.id)} onMouseEnter={() => setHover(p.id)} onMouseLeave={() => setHover(null)}>
                <circle cx={x} cy={y} r={12} fill="transparent" />
                <motion.circle
                  cx={x}
                  cy={y}
                  initial={false}
                  animate={{ r: on ? 6 : hot ? 4.5 : 3 }}
                  transition={{ duration: 0.5, ease: EASE }}
                  className={on || hot ? "fill-accent" : "fill-ink/60"}
                />
                {on && !reduce ? (
                  <motion.circle
                    cx={x}
                    cy={y}
                    r={6}
                    fill="none"
                    className="stroke-accent"
                    strokeWidth={1.2}
                    initial={{ r: 6, opacity: 0.9 }}
                    animate={{ r: 22, opacity: 0 }}
                    transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut" }}
                  />
                ) : null}
                {hot ? (
                  <text x={x + 10} y={y + 4} className="fill-ink text-[11px] font-medium">
                    {p.name}
                  </text>
                ) : null}
              </g>
            );
          })}
        </svg>
      </div>

      <div className="min-w-0">
        <div role="radiogroup" aria-label="Your town" className="flex flex-wrap gap-2">
          {places.map((p) => {
            const on = p.id === value;
            return (
              <button
                key={p.id}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => onChange(p.id)}
                onMouseEnter={() => setHover(p.id)}
                onMouseLeave={() => setHover(null)}
                onFocus={() => setHover(p.id)}
                onBlur={() => setHover(null)}
                className={cn(
                  "relative isolate rounded-full border px-3.5 py-1.5 text-sm transition-colors duration-300",
                  on ? "border-transparent text-accent-ink" : "border-line text-ink-muted hover:border-line-strong hover:text-ink",
                )}
              >
                {on ? (
                  <motion.span layoutId="place-chip" className="absolute inset-0 -z-10 rounded-full bg-accent" transition={{ duration: 0.6, ease: EASE }} />
                ) : null}
                {p.name}
              </button>
            );
          })}
        </div>
        <button
          type="button"
          onClick={locate}
          disabled={state === "busy"}
          className="group mt-5 inline-flex items-center gap-2 text-sm text-ink-muted transition-colors hover:text-ink"
        >
          <LocateFixed aria-hidden="true" className={cn("size-4", state === "busy" && "animate-spin")} />
          {state === "busy" ? "Finding you…" : state === "denied" ? "Location unavailable, pick a town" : "Use my location"}
        </button>
        <p className="mt-3 min-h-5 text-sm text-ink-faint" aria-live="polite">
          {selected ? `${selected.name}, ${selected.county} County` : ""}
        </p>
      </div>
    </div>
  );
}
