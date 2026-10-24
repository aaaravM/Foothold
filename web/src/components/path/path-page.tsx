"use client";

import { Suspense } from "react";
import { RequireAccount } from "@/components/auth/require-account";
import { MonoLabel } from "@/components/foothold/mono-label";
import { SheetFrame } from "@/components/foothold/sheet-frame";
import { PathPlanner } from "@/components/path/path-planner";
import { getSheet, sheetFrameProps } from "@/lib/sheets";

export function PathPage() {
  return (
    <SheetFrame {...sheetFrameProps("path")} description={getSheet("path").description}>
      <Suspense fallback={<MonoLabel as="p">Loading…</MonoLabel>}>
        <RequireAccount kind="learner">{(account) => <PathPlanner account={account} />}</RequireAccount>
      </Suspense>
    </SheetFrame>
  );
}
