import type { Metadata } from "next";
import { MonoLabel } from "@/components/foothold/mono-label";
import { SheetFrame } from "@/components/foothold/sheet-frame";
import { getSheet, sheetFrameProps } from "@/lib/sheets";

export const metadata: Metadata = { title: "Employers" };

// Placeholder from the shell build; the employers slice replaces this page.
export default function EmployersPage() {
  return (
    <SheetFrame {...sheetFrameProps("employers")} description={getSheet("employers").description}>
      <MonoLabel as="p">Being built: this sheet is under construction.</MonoLabel>
    </SheetFrame>
  );
}
