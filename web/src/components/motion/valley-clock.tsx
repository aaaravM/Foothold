"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface ClockReading {
  hh: string;
  mm: string;
  ss: string;
  /** "PDT" / "PST" */
  zone: string;
  /** ISO instant for <time dateTime> */
  iso: string;
}

const TIME_ZONE = "America/Los_Angeles";

let formatter: Intl.DateTimeFormat | null = null;
function read(now: Date): ClockReading {
  formatter ??= new Intl.DateTimeFormat("en-US", {
    timeZone: TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
    timeZoneName: "short",
  });
  const parts = formatter.formatToParts(now);
  const get = (type: Intl.DateTimeFormatPartTypes) => parts.find((p) => p.type === type)?.value ?? "--";
  return { hh: get("hour"), mm: get("minute"), ss: get("second"), zone: get("timeZoneName"), iso: now.toISOString() };
}

/* One shared ticking store for every clock on the page, aligned to the second. */
let current: ClockReading | null = null;
let timer: ReturnType<typeof setTimeout> | null = null;
const listeners = new Set<() => void>();

function tick() {
  current = read(new Date());
  listeners.forEach((l) => l());
  timer = setTimeout(tick, 1000 - (Date.now() % 1000) + 5);
}

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  if (listeners.size === 1) {
    current = read(new Date());
    timer = setTimeout(tick, 1000 - (Date.now() % 1000) + 5);
  }
  return () => {
    listeners.delete(onChange);
    if (listeners.size === 0 && timer) {
      clearTimeout(timer);
      timer = null;
    }
  };
}

function getSnapshot(): ClockReading | null {
  return current;
}

function getServerSnapshot(): ClockReading | null {
  return null;
}

export interface ValleyClockProps {
  /** place name before the time (default "STOCKTON") */
  place?: string;
  /** show seconds (default true) */
  seconds?: boolean;
  className?: string;
}

/**
 * Live Valley clock for title bands: "STOCKTON 13:22:07 PDT" in America/Los_Angeles.
 * Hydration-safe: the server and the hydration pass print "--:--:--", then the client ticks
 * once a second from one shared timer. Not announced to screen readers on every tick.
 */
export function ValleyClock({ place = "STOCKTON", seconds = true, className }: ValleyClockProps) {
  const now = React.useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  return (
    <span className={cn("label-mono inline-flex items-baseline gap-[0.6em] whitespace-nowrap tabular-nums", className)}>
      <span>{place}</span>
      <time dateTime={now?.iso} className="text-ink">
        {now ? now.hh : "--"}
        <span className="text-ink-faint">:</span>
        {now ? now.mm : "--"}
        {seconds ? (
          <>
            <span className="text-ink-faint">:</span>
            <span className="text-ink-muted">{now ? now.ss : "--"}</span>
          </>
        ) : null}
      </time>
      <span>{now ? now.zone : "PT"}</span>
    </span>
  );
}
