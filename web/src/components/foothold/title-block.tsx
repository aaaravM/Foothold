import * as React from "react";
import { cn } from "@/lib/utils";
import { DRAWING } from "@/lib/sheets";

export interface TitleBlockProps {
  /** e.g. "DWG-001" */
  dwg: string;
  /** e.g. "SHEET 01 OF 07" (see sheetOfLabel in lib/sheets) */
  sheetOf: string;
  /** drawing title, e.g. "Foothold / Sim" */
  title?: string;
  rev?: string;
  scale?: string;
  drawnBy?: string;
  /** ISO date of the revision */
  date?: string;
  className?: string;
}

function Cell({ term, children, className }: { term: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-1 bg-background px-3 py-2.5", className)}>
      <dt className="label-mono text-ink-faint">{term}</dt>
      <dd className="truncate font-mono text-xs text-ink tabular-nums">{children}</dd>
    </div>
  );
}

/** Drawing title block: DWG / REV / SCALE / DRAWN BY / DATE / SHEET x OF 07. */
export function TitleBlock({
  dwg,
  sheetOf,
  title = "Foothold",
  rev = DRAWING.rev,
  scale = DRAWING.scale,
  drawnBy = DRAWING.drawnBy,
  date = DRAWING.date,
  className,
}: TitleBlockProps) {
  return (
    <dl
      aria-label="Drawing title block"
      className={cn(
        "grid grid-cols-2 gap-px border border-line bg-line sm:grid-cols-3 lg:grid-cols-[minmax(0,2fr)_repeat(6,minmax(0,1fr))]",
        className,
      )}
    >
      <Cell term="Title" className="col-span-2 sm:col-span-3 lg:col-span-1">
        <span className="font-sans text-sm font-medium tracking-normal normal-case">{title}</span>
      </Cell>
      <Cell term="DWG">{dwg}</Cell>
      <Cell term="REV">{rev}</Cell>
      <Cell term="Scale">{scale}</Cell>
      <Cell term="Drawn by">{drawnBy}</Cell>
      <Cell term="Date">
        <time dateTime={date}>{date}</time>
      </Cell>
      <Cell term="Sheet">{sheetOf.replace(/^SHEET\s+/i, "")}</Cell>
    </dl>
  );
}
