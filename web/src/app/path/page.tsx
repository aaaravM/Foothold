import type { Metadata } from "next";
import { MonoLabel } from "@/components/foothold/mono-label";
import { SheetFrame } from "@/components/foothold/sheet-frame";
import { getSheet, sheetFrameProps } from "@/lib/sheets";

export const metadata: Metadata = { title: "Path" };

// Placeholder from the shell build; the path slice replaces this page.
export default function PathPage() {
  return (
    <SheetFrame {...sheetFrameProps("path")} description={getSheet("path").description}>
      <MonoLabel as="p">Being built: this sheet is under construction.</MonoLabel>
    </SheetFrame>
  );
}
