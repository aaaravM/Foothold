import * as React from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SourceLinkProps {
  href: string;
  label: React.ReactNode;
  /** mono uppercase styling for dense metadata rows */
  mono?: boolean;
  /** show the ↗ icon on external links (default true) */
  showIcon?: boolean;
  className?: string;
}

const EXTERNAL = /^(https?:)?\/\//i;

/** Citation / verification link. External links open in a new tab and say so to screen readers. */
export function SourceLink({ href, label, mono = false, showIcon = true, className }: SourceLinkProps) {
  const classes = cn(
    "inline-flex items-baseline gap-1 text-ink underline decoration-line-strong decoration-1 underline-offset-4 transition-colors hover:text-accent hover:decoration-accent",
    mono && "label-mono",
    className,
  );

  if (!EXTERNAL.test(href)) {
    return (
      <Link href={href} className={classes}>
        {label}
      </Link>
    );
  }

  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={classes}>
      <span>{label}</span>
      {showIcon ? <ArrowUpRight aria-hidden="true" className="size-3.5 shrink-0 self-center" /> : null}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}
