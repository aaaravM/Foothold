/**
 * Foothold motion system (docs/DESIGN_DIRECTION.md section 4). Each move draws something,
 * reveals structure or responds to the user; all respect prefers-reduced-motion and animate
 * only transform, opacity, pathLength, clip-path and font variations.
 *
 *   PlotterPath      d, duration=1.8, delay, ease, play, progress?, penHead, penRest, onDrawn
 *   KineticWordmark  text="Foothold", as, delay, stagger=40ms, wdth=125 (CSS, first paint)
 *   CrosshairCursor  readout, mmPerPx (scoped to its positioned parent; pointer: fine only)
 *   CountUp          value (REAL numbers only), decimals, duration=0.8, prefix, suffix, play
 *   BracketFrame     as, active, size, inset, color  |  Brackets + BRACKET_HOST for links/buttons
 *   DrawUnderline    href, tone, rest, drawn  |  class `link-draw` for any element
 *   GrainOverlay     (layout) feTurbulence film grain, fixed, pointer-events none
 *   GridOverlay      (layout) 4/8/12-column hairline overlay, G toggles
 *   SurveyMarker     size, active, ping (increment), shown
 *   Callout          n, title, meta, leader {side, length}  |  CalloutBubble, LeaderPath, LeaderLine
 *   DetailFrame      letter, sheet, title, meta, draw="view"  |  DetailBubble
 *   ValleyClock      place="STOCKTON", seconds (America/Los_Angeles, hydration-safe)
 *   SheetIntro       border, marks (CSS sheet border + registration marks, under 1 s)
 */
export { PlotterPath, type PlotterPathProps } from "./plotter-path";
export { KineticWordmark, type KineticWordmarkProps } from "./kinetic-wordmark";
export { CrosshairCursor, MM_PER_PX, type CrosshairCursorProps } from "./crosshair-cursor";
export { CountUp, type CountUpProps } from "./count-up";
export { BracketFrame, Brackets, BRACKET_HOST, type BracketFrameProps, type BracketsProps } from "./bracket-frame";
export { DrawUnderline, type DrawUnderlineProps } from "./draw-underline";
export { GrainOverlay } from "./grain-overlay";
export { GridOverlay } from "./grid-overlay";
export { SurveyMarker, type SurveyMarkerProps } from "./survey-marker";
export {
  Callout,
  CalloutBubble,
  LeaderLine,
  LeaderPath,
  pointsToPath,
  type CalloutBubbleProps,
  type CalloutProps,
  type LeaderLineProps,
  type LeaderPathProps,
  type Point,
} from "./callout";
export { DetailFrame, DetailBubble, type DetailFrameProps, type DetailBubbleProps } from "./detail-frame";
export { ValleyClock, type ValleyClockProps, type ClockReading } from "./valley-clock";
export { SheetIntro, type SheetIntroProps } from "./sheet-intro";
export {
  EASE_OUT,
  EASE_PLOT,
  delayFromNavStart,
  useElementSize,
  useHydrated,
  useLatest,
  useMediaQuery,
  useReducedMotionSafe,
} from "./use-motion-env";
