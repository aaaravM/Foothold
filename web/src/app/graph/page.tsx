import type { Metadata } from "next";
import { SheetFrame } from "@/components/foothold/sheet-frame";
import { GraphExplorer } from "@/components/graph/graph-explorer";
import { getSheet, sheetFrameProps } from "@/lib/sheets";

export const metadata: Metadata = { title: "Graph" };

export default function GraphPage() {
  return (
    <SheetFrame {...sheetFrameProps("graph")} description={getSheet("graph").description}>
      <GraphExplorer />
    </SheetFrame>
  );
}
