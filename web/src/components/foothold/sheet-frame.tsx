import * as React from "react";
import { cn } from "@/lib/utils";
import type { Chapter } from "@/lib/sheets";

export interface SheetFrameProps {
  /** "01".."07", "00" or "DEMO" */
  sheet: string;
  /** "DWG-001" */
  dwg: string;
  /** page title, rendered as the page heading */
  title: React.ReactNode;
  /** short code in the header row ("SIM"); defaults to the uppercased string title */
  code?: string;
  chapter?: Chapter;
  /** lede under the title */
  description?: React.ReactNode;
  /** right side of the title band (buttons, status) */
  actions?: React.ReactNode;
  children?: React.ReactNode;
  /** heading level of the title (default 1: one SheetFrame per page) */
  headingLevel?: 1 | 2;
  /** hairline grid behind the title band (default true) */
  grid?: boolean;
  /** heading id (default derived from dwg) */
  id?: string;
  className?: string;
  bodyClassName?: string;
}

/**
 * A page section: hairline border, a title band and the body. (sheet/dwg/code/chapter props are
 * kept for compatibility; no drawing metadata is rendered.)
 * Server-compatible; use one per page with headingLevel 1.
 */
export function SheetFrame({
  sheet,
  dwg,
  title,
  code,
  chapter,
  description,
  actions,
  children,
  headingLevel = 1,
  grid = true,
  id,
  className,
  bodyClassName,
}: SheetFrameProps) {
  const headingId = id ?? `sheet-${dwg.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-title`;
  void sheet;
  void code;
  void chapter;
  const Heading = headingLevel === 1 ? "h1" : "h2";

  void grid;

  return (
    <section aria-labelledby={headingId} className={cn("page-container relative w-full", className)}>
      <div className="pt-[7svh] pb-8 lg:pt-[9svh] lg:pb-10">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-4xl space-y-4">
            <Heading id={headingId} className="fh-mask-in type-display-lg text-ink">
              {title}
            </Heading>
            {description ? <div className="fh-soft-in max-w-2xl text-base text-ink-muted sm:text-lg">{description}</div> : null}
          </div>
          {actions ? <div className="fh-soft-in flex flex-wrap items-center gap-2">{actions}</div> : null}
        </div>
      </div>

      {children ? <div className={cn("fh-soft-in pb-16 [--d:0.25s]", bodyClassName)}>{children}</div> : null}
    </section>
  );
}
