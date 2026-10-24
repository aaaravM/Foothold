import type { Metadata } from "next";
import { SheetFrame } from "@/components/foothold/sheet-frame";
import { EmployerDashboard } from "@/components/employers/employer-dashboard";
import { getSheet, sheetFrameProps } from "@/lib/sheets";

export const metadata: Metadata = { title: "Employers" };

export default function EmployersPage() {
  return (
    <SheetFrame {...sheetFrameProps("employers")} description={getSheet("employers").description}>
      <EmployerDashboard />
    </SheetFrame>
  );
}
