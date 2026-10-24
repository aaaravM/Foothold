import * as React from "react";
import { cn } from "@/lib/utils";

const CORNERS = ["tl", "tr", "bl", "br"] as const;

/** Class for any element that should host <Brackets/> (links, buttons, frames). */
export const BRACKET_HOST = "bk-host";

export interface BracketsProps {
  /** extra classes for each corner */
  className?: string;
}

/**
 * The four corner brackets. Place them as direct children of an element with the
 * `bk-host` class; they snap in (about 150 ms) on hover and on keyboard focus.
 * Tune with CSS variables on the host: --bk-size, --bk-inset, --bk-color, --bk-w.
 */
export function Brackets({ className }: BracketsProps) {
  return (
    <>
      {CORNERS.map((c) => (
        <span key={c} aria-hidden="true" className={cn("bk", className)} data-corner={c} />
      ))}
    </>
  );
}

type FrameElement = "span" | "div" | "li" | "figure" | "section";

export interface BracketFrameProps extends React.HTMLAttributes<HTMLElement> {
  as?: FrameElement;
  /** keep the brackets shown (e.g. the selected item) */
  active?: boolean;
  /** bracket arm length in px (default 7) */
  size?: number;
  /** offset from the frame edge in px; negative sits outside (default -4) */
  inset?: number;
  /** CSS color (default the gold accent) */
  color?: string;
  /** stroke width in px (default 1.5) */
  weight?: number;
}

/**
 * Wraps content in a frame whose corner brackets snap in on hover / focus-visible.
 * For a link or button, put `className={BRACKET_HOST}` on it and render <Brackets/> inside instead.
 */
export function BracketFrame({
  as = "span",
  active = false,
  size,
  inset,
  color,
  weight,
  className,
  style,
  children,
  ...rest
}: BracketFrameProps) {
  const Comp = as as React.ElementType;
  const vars: Record<string, string> = {};
  if (size !== undefined) vars["--bk-size"] = `${size}px`;
  if (inset !== undefined) vars["--bk-inset"] = `${inset}px`;
  if (color !== undefined) vars["--bk-color"] = color;
  if (weight !== undefined) vars["--bk-w"] = `${weight}px`;
  return (
    <Comp
      className={cn(BRACKET_HOST, className)}
      data-bk={active ? "on" : undefined}
      style={{ ...(vars as React.CSSProperties), ...style }}
      {...rest}
    >
      {children}
      <Brackets />
    </Comp>
  );
}
