import * as React from "react";
import { cn } from "@/lib/utils";

export interface RegistrationMarksProps {
  /** "target" = circle + crosshair, "crop" = L-shaped corner ticks */
  variant?: "target" | "crop";
  /** mark size in px (default 14) */
  size?: number;
  /** distance from the container edge, any CSS length (default "-7px": centred on the border) */
  inset?: string;
  /** which corners to draw (default all four) */
  corners?: ReadonlyArray<"tl" | "tr" | "bl" | "br">;
  /** spin-and-snap in on mount, staggered per corner (CSS; skipped for reduced motion) */
  animated?: boolean;
  /** seconds before the first mark animates (default 0) */
  delay?: number;
  className?: string;
}

const ALL = ["tl", "tr", "bl", "br"] as const;

/**
 * Printer's registration marks at the corners of the nearest positioned ancestor.
 * Decorative only (aria-hidden). Parent needs `position: relative`.
 */
export function RegistrationMarks({
  variant = "target",
  size = 14,
  inset = "-7px",
  corners = ALL,
  animated = false,
  delay = 0,
  className,
}: RegistrationMarksProps) {
  const c = size / 2;
  const r = size * 0.28;
  return (
    <span aria-hidden="true" className={cn("pointer-events-none absolute inset-0 text-line-strong", className)}>
      {corners.map((corner, i) => {
        const pos: React.CSSProperties = {
          width: size,
          height: size,
          ...(corner.includes("t") ? { top: inset } : { bottom: inset }),
          ...(corner.includes("l") ? { left: inset } : { right: inset }),
          ...(animated ? ({ "--d": `${delay + i * 0.06}s` } as React.CSSProperties) : null),
        };
        return (
          <svg
            key={corner}
            className={cn("absolute", animated && "fh-sheet-mark")}
            style={pos}
            viewBox={`0 0 ${size} ${size}`}
            fill="none"
            stroke="currentColor"
            strokeWidth={1}
            shapeRendering="geometricPrecision"
          >
            {variant === "target" ? (
              <>
                <circle cx={c} cy={c} r={r} />
                <line x1={c} y1={0} x2={c} y2={size} />
                <line x1={0} y1={c} x2={size} y2={c} />
              </>
            ) : (
              <path
                d={
                  corner === "tl"
                    ? `M0.5 ${size} V0.5 H${size}`
                    : corner === "tr"
                      ? `M0 0.5 H${size - 0.5} V${size}`
                      : corner === "bl"
                        ? `M0.5 0 V${size - 0.5} H${size}`
                        : `M0 ${size - 0.5} H${size - 0.5} V0`
                }
              />
            )}
          </svg>
        );
      })}
    </span>
  );
}
