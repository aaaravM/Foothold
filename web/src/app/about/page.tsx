import type { Metadata } from "next";
import { SheetFrame } from "@/components/foothold/sheet-frame";
import { AboutSheet } from "@/components/lab/about-sheet";
import { getSheet, sheetFrameProps } from "@/lib/sheets";

export const metadata: Metadata = { title: "About" };

export default function AboutPage() {
  return (
    <SheetFrame {...sheetFrameProps("about")} description={getSheet("about").description}>
      <AboutSheet />
    </SheetFrame>
  );
}
