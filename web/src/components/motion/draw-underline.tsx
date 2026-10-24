import * as React from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";

const EXTERNAL = /^(https?:)?\/\//i;

export interface DrawUnderlineProps extends Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, "href"> {
  href: string;
  /** keep a faint hairline under the link at rest (default true, so links stay recognizable) */
  rest?: boolean;
  /** color of the drawn line: "ink" (default, currentColor) or the gold "accent" */
  tone?: "ink" | "accent";
  /** keep the underline drawn (e.g. the current page) */
  drawn?: boolean;
  children: React.ReactNode;
}

/**
 * A text link whose underline draws left to right on hover and keyboard focus
 * (and retracts to the right when you leave). External links open in a new tab and say so.
 * For other elements, add the `link-draw` class directly.
 */
export function DrawUnderline({ href, rest = true, tone = "ink", drawn = false, className, children, ...props }: DrawUnderlineProps) {
  const classes = cn("link-draw", tone === "accent" && "[--ul-color:var(--accent)]", className);
  const data = { "data-rest": rest ? "hairline" : undefined, "data-drawn": drawn ? "true" : undefined };
  if (EXTERNAL.test(href)) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={classes} {...data} {...props}>
        {children}
        <span className="sr-only"> (opens in a new tab)</span>
      </a>
    );
  }
  return (
    <Link href={href} className={classes} {...data} {...props}>
      {children}
    </Link>
  );
}
