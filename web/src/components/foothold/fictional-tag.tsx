import * as React from "react";
import { Drama } from "lucide-react";
import { cn } from "@/lib/utils";

export interface FictionalTagProps {
  /** default "Fictional" */
  label?: string;
  /** icon only on very tight layouts (the word stays available to screen readers) */
  compact?: boolean;
  className?: string;
}

/** Marks an invented person, employer or circle member. Required next to every persona name. */
export function FictionalTag({ label = "Fictional", compact = false, className }: FictionalTagProps) {
  return (
    <span
      className={cn(
        "label-mono inline-flex h-5 shrink-0 items-center gap-1 rounded-sm border border-dashed border-line-strong px-1.5 leading-none text-ink-muted",
        className,
      )}
    >
      <Drama aria-hidden="true" className="size-3" />
      <span className={cn(compact && "sr-only")}>{label}</span>
    </span>
  );
}
