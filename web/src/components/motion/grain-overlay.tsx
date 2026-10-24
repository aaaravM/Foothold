import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Film grain over the whole viewport: a tiled SVG feTurbulence image at a few percent opacity
 * (token --grain-opacity per theme). Fixed, pointer-events none, rasterized once and tiled,
 * so it costs nothing per frame. Rendered once by app/layout.tsx.
 */
export function GrainOverlay({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("fh-grain", className)} />;
}
