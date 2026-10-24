import * as React from "react";
import { cn } from "@/lib/utils";
import { RegistrationMarks } from "@/components/foothold/registration-marks";

export interface SheetIntroProps {
  /** draw the four border hairlines (default true) */
  border?: boolean;
  /** registration targets at the corners (default true) */
  marks?: boolean;
  className?: string;
}

/**
 * Sheet intro for a drawing frame: the border hairlines draw from the corners (~420 ms) while
 * the registration marks spin and snap in, before the content rises in (see `fh-sheet-content`,
 * `fh-rule` in globals.css). The whole intro finishes under 1 s. Pure CSS: it plays at first
 * paint and again whenever the sheet is shown; reduced motion shows the finished frame.
 * Place inside a `position: relative` element that has no border of its own.
 */
export function SheetIntro({ border = true, marks = true, className }: SheetIntroProps) {
  return (
    <span aria-hidden="true" className={cn("pointer-events-none absolute inset-0", className)}>
      {border ? (
        <>
          <span className="fh-sheet-line" data-edge="top" />
          <span className="fh-sheet-line" data-edge="right" />
          <span className="fh-sheet-line" data-edge="bottom" />
          <span className="fh-sheet-line" data-edge="left" />
        </>
      ) : null}
      {marks ? <RegistrationMarks animated /> : null}
    </span>
  );
}
