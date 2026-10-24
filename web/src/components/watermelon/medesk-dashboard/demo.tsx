"use client";

/*
 * Watermelon UI "medesk-dashboard" (MIT, Watermelon Contributors), adapted for Foothold.
 *
 * Changes from the original demo:
 * - The bundled ThemeProvider is gone. It read localStorage/matchMedia during render
 *   (SSR crash) and wrote .dark/.light classes on <html>, fighting Foothold's
 *   data-theme. The portal now inherits Foothold's tokens.
 * - Mount it client-only: import `LazyMedeskDashboard` from "@/components/lazy"
 *   (next/dynamic with ssr:false), not this file directly from a server component.
 * - Routes without data render NotWiredPanel instead of an empty page.
 */
import type { ReactNode } from "react";
import DashboardLayout from "./dashboard-layout";
import { DashboardPage, NotWiredPanel } from "./components/medesk/dashboard-content";
import {
  DashboardNavigationProvider,
  useDashboardNavigation,
} from "./components/medesk/navigation";
import {
  defaultOrg,
  gapReportData,
  navigationGroups,
  type DashboardOrg,
  type EmployerDashboardData,
  type NavigationGroup,
} from "./data";

export interface MedeskDashboardProps {
  /** dashboard content for the "/" route (default: the sourced regional gap report) */
  data?: EmployerDashboardData;
  groups?: NavigationGroup[];
  org?: DashboardOrg;
  /** custom views by in-portal path; anything missing falls back to NotWiredPanel */
  views?: Record<string, ReactNode>;
  initialPath?: string;
  brand?: ReactNode;
  accountSlot?: ReactNode;
  sheetLabel?: string;
  topbarActions?: ReactNode;
  pageActions?: ReactNode;
  className?: string;
}

function DashboardRoute({
  data,
  groups,
  views,
  pageActions,
}: Required<Pick<MedeskDashboardProps, "data" | "groups">> &
  Pick<MedeskDashboardProps, "views" | "pageActions">) {
  const { pathname } = useDashboardNavigation();
  const custom = views?.[pathname];
  if (custom) return <>{custom}</>;
  if (pathname === "/") return <DashboardPage data={data} actions={pageActions} />;
  const item = groups.flatMap((g) => g.items).find((i) => i.href === pathname);
  return item ? <NotWiredPanel item={item} /> : <DashboardPage data={data} actions={pageActions} />;
}

export default function MedeskDashboardDemo({
  data = gapReportData,
  groups = navigationGroups,
  org = defaultOrg,
  views,
  initialPath = "/",
  brand,
  accountSlot,
  sheetLabel = "SHEET 04 / EMPLOYERS",
  topbarActions,
  pageActions,
  className,
}: MedeskDashboardProps) {
  return (
    <DashboardNavigationProvider initialPath={initialPath}>
      <DashboardLayout
        groups={groups}
        org={org}
        brand={brand}
        accountSlot={accountSlot}
        sheetLabel={sheetLabel}
        topbarActions={topbarActions}
        className={className}
      >
        <DashboardRoute data={data} groups={groups} views={views} pageActions={pageActions} />
      </DashboardLayout>
    </DashboardNavigationProvider>
  );
}
