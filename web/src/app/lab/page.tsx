import type { Metadata } from "next";
import { MonoLabel } from "@/components/foothold/mono-label";
import { SheetFrame } from "@/components/foothold/sheet-frame";
import { getSheet, sheetFrameProps } from "@/lib/sheets";

export const metadata: Metadata = { title: "Lab" };

// Placeholder from the shell build; the lab slice replaces this page.
export default function LabPage() {
  return (
    <SheetFrame {...sheetFrameProps("lab")} description={getSheet("lab").description}>
      <MonoLabel as="p">Being built: this sheet is under construction.</MonoLabel>
    </SheetFrame>
  );
}
