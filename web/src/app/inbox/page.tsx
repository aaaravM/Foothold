import type { Metadata } from "next";
import { SheetFrame } from "@/components/foothold/sheet-frame";
import { InboxView } from "@/components/inbox/inbox-view";
import { getSheet, sheetFrameProps } from "@/lib/sheets";

export const metadata: Metadata = { title: "Inbox" };

export default function InboxPage() {
  return (
    <SheetFrame {...sheetFrameProps("inbox")} description={getSheet("inbox").description}>
      <InboxView />
    </SheetFrame>
  );
}
