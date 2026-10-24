import * as React from "react";
import { Hourglass } from "lucide-react";
import { cn } from "@/lib/utils";

export interface NotTrainedYetProps {
  /** what produces the number, read by screen readers, e.g. "Run ml/train_career_fit.py" */
  hint?: string;
  className?: string;
}

/** Placeholder for a metric that metrics.json does not have yet. Never show an invented number instead. */
export function NotTrainedYet({ hint = "This number appears once the training script has written it to metrics.json.", className }: NotTrainedYetProps) {
  return (
    <span
      className={cn(
        "label-mono inline-flex h-6 items-center gap-1.5 rounded-sm border border-dashed border-line-strong px-2 leading-none text-ink-muted",
        className,
      )}
    >
      <Hourglass aria-hidden="true" className="size-3" />
      <span>not trained yet</span>
      <span className="sr-only">. {hint}</span>
    </span>
  );
}

export interface MetricValueProps {
  /** from ml/artifacts/metrics.json; null / undefined / NaN renders <NotTrainedYet /> */
  value: number | null | undefined;
  /** fraction digits (default 2) */
  digits?: number;
  /** appended after the number, e.g. " ms" or "%" */
  suffix?: string;
  prefix?: string;
  /** multiply by 100 and append "%" (for 0..1 rates) */
  percent?: boolean;
  /** hint passed to NotTrainedYet */
  notTrainedHint?: string;
  className?: string;
}

/** A metric in mono tabular figures, or "not trained yet" when the value is missing. */
export function MetricValue({ value, digits = 2, suffix, prefix, percent = false, notTrainedHint, className }: MetricValueProps) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return <NotTrainedYet hint={notTrainedHint} className={className} />;
  }
  const shown = percent ? value * 100 : value;
  const formatted = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(shown);
  const unit = percent ? "%" : suffix;
  return (
    <span className={cn("font-mono text-ink tabular-nums", className)}>
      {prefix}
      {formatted}
      {unit ? <span className="text-ink-muted">{unit}</span> : null}
    </span>
  );
}
