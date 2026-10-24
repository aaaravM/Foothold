export interface FictionalTagProps {
  label?: string;
  compact?: boolean;
  className?: string;
}

/** Retired: the app no longer labels people as fictional (the honesty note lives on /about). Renders nothing. */
export function FictionalTag(_props: FictionalTagProps) {
  void _props;
  return null;
}
