export interface ChapterLabelProps {
  index: number;
  total: number;
  label: string;
  className?: string;
  as?: "p" | "span" | "div";
}

/** Retired drawing metadata ("[ C1 / TRY ] 01 / 06"). Renders nothing. */
export function ChapterLabel(_props: ChapterLabelProps) {
  void _props;
  return null;
}
