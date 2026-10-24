import * as React from "react";
import { cn } from "@/lib/utils";

export type MonoLabelTone = "faint" | "muted" | "ink" | "accent" | "success" | "warning" | "danger" | "info";

const TONE: Record<MonoLabelTone, string> = {
  faint: "text-ink-faint",
  muted: "text-ink-muted",
  ink: "text-ink",
  accent: "text-accent",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
  info: "text-info",
};

type MonoLabelElement = "span" | "p" | "div" | "dt" | "dd" | "label" | "figcaption" | "h2" | "h3" | "h4" | "li";

export interface MonoLabelProps extends React.HTMLAttributes<HTMLElement> {
  as?: MonoLabelElement;
  tone?: MonoLabelTone;
  /** "xs" = 11px (default), "sm" = 12px */
  size?: "xs" | "sm";
  /** for `as="label"` */
  htmlFor?: string;
}

/** Uppercase, tracked, tabular mono label: "DWG-001", "SHEET 01 / SIM", "01 / 06". */
export function MonoLabel({ as = "span", tone = "faint", size = "xs", className, children, ...props }: MonoLabelProps) {
  const Comp = as as React.ElementType;
  return (
    <Comp className={cn("label-mono", size === "sm" && "text-xs leading-4", TONE[tone], className)} {...props}>
      {children}
    </Comp>
  );
}
