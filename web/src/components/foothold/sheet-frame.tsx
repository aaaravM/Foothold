import * as React from "react";
import { cn } from "@/lib/utils";
import type { Chapter } from "@/lib/sheets";
import { ChapterLabel } from "./chapter-label";
import { MonoLabel } from "./mono-label";
import { RegistrationMarks } from "./registration-marks";

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
 * A drawing sheet: hairline border, corner registration marks, a header row
 * "SHEET 01 / SIM · DWG-001" (+ chapter label), a title band and the body.
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
  const shortCode = code ?? (typeof title === "string" ? title.toUpperCase() : "");
  const Heading = headingLevel === 1 ? "h1" : "h2";

  return (
    <div className="px-3 py-5 sm:px-6 sm:py-8 lg:px-8">
      <section aria-labelledby={headingId} className={cn("relative mx-auto w-full max-w-[1440px] border border-line bg-background", className)}>
        <RegistrationMarks />
        <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1.5 border-b border-line px-4 py-2.5 sm:px-6">
          <MonoLabel as="p" tone="muted">
            SHEET {sheet}
            {shortCode ? ` / ${shortCode}` : ""}
            <span aria-hidden="true" className="px-2 text-ink-faint">
              ·
            </span>
            {dwg}
          </MonoLabel>
          {chapter ? <ChapterLabel index={chapter.index} total={chapter.total} label={chapter.label} /> : null}
        </header>

        <div className={cn("border-b border-line px-4 pt-10 pb-8 sm:px-6 lg:px-10 lg:pt-16 lg:pb-12", grid && "hairline-grid")}>
          <div className="flex flex-wrap items-end justify-between gap-6">
            <div className="max-w-4xl space-y-4">
              <Heading id={headingId} className="type-display-lg text-ink">
                {title}
              </Heading>
              {description ? <div className="max-w-2xl text-base text-ink-muted sm:text-lg">{description}</div> : null}
            </div>
            {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
          </div>
        </div>

        {children ? <div className={cn("px-4 py-8 sm:px-6 lg:px-10 lg:py-10", bodyClassName)}>{children}</div> : null}
      </section>
    </div>
  );
}
