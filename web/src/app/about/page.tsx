import type { Metadata } from "next";
import { MonoLabel } from "@/components/foothold/mono-label";
import { SheetFrame } from "@/components/foothold/sheet-frame";
import { getSheet, sheetFrameProps } from "@/lib/sheets";

export const metadata: Metadata = { title: "About" };

// Placeholder from the shell build; the about slice replaces this page.
export default function AboutPage() {
  return (
    <SheetFrame {...sheetFrameProps("about")} description={getSheet("about").description}>
      <MonoLabel as="p">Being built: this sheet is under construction.</MonoLabel>
    </SheetFrame>
  );
}
