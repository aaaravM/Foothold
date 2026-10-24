import type { Metadata } from "next";
import { MonoLabel } from "@/components/foothold/mono-label";
import { SheetFrame } from "@/components/foothold/sheet-frame";
import { getSheet, sheetFrameProps } from "@/lib/sheets";

export const metadata: Metadata = { title: "Sim" };

// Placeholder from the shell build; the sim slice replaces this page.
export default function SimPage() {
  return (
    <SheetFrame {...sheetFrameProps("sim")} description={getSheet("sim").description}>
      <MonoLabel as="p">Being built: this sheet is under construction.</MonoLabel>
    </SheetFrame>
  );
}
