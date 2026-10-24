/**
 * Shared Foothold primitives (docs/CONTRACTS.md section 8). Reuse, don't fork.
 * Import from "@/components/foothold" or from the individual files.
 * Motion primitives (PlotterPath, BracketFrame, DetailFrame, ...) live in "@/components/motion".
 * There is deliberately no command palette, API-status dot or persona switcher (CONTRACTS section 13).
 */
export { SheetFrame, type SheetFrameProps } from "./sheet-frame";
export { ChapterLabel, type ChapterLabelProps } from "./chapter-label";
export { MonoLabel, type MonoLabelProps, type MonoLabelTone } from "./mono-label";
export { RegistrationMarks, type RegistrationMarksProps } from "./registration-marks";
export { DimensionLine, type DimensionLineProps } from "./dimension-line";
export { TitleBlock, type TitleBlockProps } from "./title-block";
export { ProvenanceBadge, PROVENANCE_META, type ProvenanceBadgeProps } from "./provenance-badge";
export { FictionalTag, type FictionalTagProps } from "./fictional-tag";
export { SourceLink, type SourceLinkProps } from "./source-link";
export { MetricValue, NotTrainedYet, type MetricValueProps, type NotTrainedYetProps } from "./metric-value";
export { StatBar, type StatBarProps, type StatTone } from "./stat-bar";
export { TraitRadar, type TraitDatum, type TraitRadarProps } from "./trait-radar";
export { TracePanel, type TracePanelProps } from "./trace-panel";
export { useTrace, type UseTraceResult } from "./use-trace";
export { ThemeToggle, useTheme, type UseThemeResult } from "./theme-toggle";
