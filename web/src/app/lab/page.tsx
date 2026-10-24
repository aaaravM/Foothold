import type { Metadata } from "next";
import { SheetFrame } from "@/components/foothold/sheet-frame";
import { LabSheet } from "@/components/lab/lab-sheet";
import { getSheet, sheetFrameProps } from "@/lib/sheets";

export const metadata: Metadata = { title: "Lab" };

export default function LabPage() {
  return (
    <SheetFrame {...sheetFrameProps("lab")} description={getSheet("lab").description}>
      <LabSheet />
    </SheetFrame>
  );
}
