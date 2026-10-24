"use client";

import { RequireAccount } from "@/components/auth/require-account";
import { SheetFrame } from "@/components/foothold/sheet-frame";
import { SimWorkday } from "@/components/sim/sim-workday";
import { getSheet, sheetFrameProps } from "@/lib/sheets";

export function SimPage() {
  return (
    <SheetFrame {...sheetFrameProps("sim")} description={getSheet("sim").description}>
      <RequireAccount kind="learner">{(account) => <SimWorkday account={account} />}</RequireAccount>
    </SheetFrame>
  );
}
