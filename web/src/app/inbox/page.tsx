import type { Metadata } from "next";
import { MonoLabel } from "@/components/foothold/mono-label";
import { SheetFrame } from "@/components/foothold/sheet-frame";
import { getSheet, sheetFrameProps } from "@/lib/sheets";

export const metadata: Metadata = { title: "Inbox" };

// Placeholder from the shell build; the inbox slice replaces this page.
export default function InboxPage() {
  return (
    <SheetFrame {...sheetFrameProps("inbox")} description={getSheet("inbox").description}>
      <MonoLabel as="p">Being built: this sheet is under construction.</MonoLabel>
    </SheetFrame>
  );
}
