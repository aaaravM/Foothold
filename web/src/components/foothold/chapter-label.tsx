import * as React from "react";
import { cn } from "@/lib/utils";
import { pad2 } from "@/lib/sheets";

export interface ChapterLabelProps {
  /** 1-based chapter number */
  index: number;
  total: number;
  /** short uppercase word, e.g. "TRY" */
  label: string;
  className?: string;
  as?: "p" | "span" | "div";
}

/** `[ C1 / TRY ]  01 / 06` — screen readers hear "Chapter 1 of 6: TRY". */
export function ChapterLabel({ index, total, label, className, as = "p" }: ChapterLabelProps) {
  const Comp = as;
  return (
    <Comp className={cn("label-mono flex flex-wrap items-baseline gap-x-4 gap-y-1 text-ink-faint", className)}>
      <span className="sr-only">{`Chapter ${index} of ${total}: ${label}`}</span>
      <span aria-hidden="true" className="text-accent">
        [ C{index} / {label.toUpperCase()} ]
      </span>
      <span aria-hidden="true" className="tabular-nums">
        {pad2(index)} / {pad2(total)}
      </span>
    </Comp>
  );
}
