import * as React from "react";
import { cn } from "@/lib/utils";

export interface KineticWordmarkProps {
  /** default "Foothold" */
  text?: string;
  as?: "h1" | "h2" | "p" | "span" | "div";
  /** seconds before the first letter (default 0.05) */
  delay?: number;
  /** ms between letters (default 40, per the brief) */
  stagger?: number;
  /** seconds per letter reveal (default 0.8) */
  letterDuration?: number;
  /** seconds for the width axis to ease from condensed to wide (default 1.6) */
  widthDuration?: number;
  /** final Hubot Sans width axis (default 125; it starts at 75) */
  wdth?: number;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Kinetic wordmark: each letter reveals through a clip (40 ms stagger) while the Hubot Sans
 * width axis eases from condensed (75) to wide (125). Pure CSS, so it starts at first paint,
 * before hydration; reduced motion shows the final wide word at once (globals.css).
 * Screen readers get the plain word.
 */
export function KineticWordmark({
  text = "Foothold",
  as = "h1",
  delay = 0.05,
  stagger = 40,
  letterDuration = 0.8,
  widthDuration = 1.6,
  wdth = 125,
  className,
  style,
}: KineticWordmarkProps) {
  const Comp = as;
  const letters = Array.from(text);
  const vars = {
    "--wm-delay": `${delay}s`,
    "--wm-stagger": `${stagger}ms`,
    "--wm-letter-dur": `${letterDuration}s`,
    "--wm-wdth-dur": `${widthDuration}s`,
    "--wm-wdth": wdth,
    ...style,
  } as React.CSSProperties;

  return (
    <Comp className={cn("fh-wordmark", className)} style={vars}>
      <span className="sr-only">{text}</span>
      <span aria-hidden="true" className="fh-wordmark-word">
        {letters.map((ch, i) => (
          <span key={`${i}-${ch}`} className="fh-wordmark-letter" style={{ "--i": i } as React.CSSProperties}>
            {ch === " " ? " " : ch}
          </span>
        ))}
      </span>
    </Comp>
  );
}
