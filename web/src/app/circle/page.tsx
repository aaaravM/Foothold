import type { Metadata } from "next";
import { MonoLabel } from "@/components/foothold/mono-label";
import { SheetFrame } from "@/components/foothold/sheet-frame";
import { getSheet, sheetFrameProps } from "@/lib/sheets";

export const metadata: Metadata = { title: "Circle" };

// Placeholder from the shell build; the circle slice replaces this page.
export default function CirclePage() {
  return (
    <SheetFrame {...sheetFrameProps("circle")} description={getSheet("circle").description}>
      <MonoLabel as="p">Being built: this sheet is under construction.</MonoLabel>
    </SheetFrame>
  );
}
