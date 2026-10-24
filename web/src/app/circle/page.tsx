import type { Metadata } from "next";
import { SheetFrame } from "@/components/foothold/sheet-frame";
import { CircleView } from "@/components/circle/circle-view";
import { getSheet, sheetFrameProps } from "@/lib/sheets";

export const metadata: Metadata = { title: "Circle" };

export default function CirclePage() {
  return (
    <SheetFrame {...sheetFrameProps("circle")} description={getSheet("circle").description}>
      <CircleView />
    </SheetFrame>
  );
}
