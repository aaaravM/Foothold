import type { Metadata } from "next";
import { MonoLabel } from "@/components/foothold/mono-label";
import { SheetFrame } from "@/components/foothold/sheet-frame";
import { getSheet, sheetFrameProps } from "@/lib/sheets";

export const metadata: Metadata = { title: "Graph" };

// Placeholder from the shell build; the graph slice replaces this page.
export default function GraphPage() {
  return (
    <SheetFrame {...sheetFrameProps("graph")} description={getSheet("graph").description}>
      <MonoLabel as="p">Being built: this sheet is under construction.</MonoLabel>
    </SheetFrame>
  );
}
