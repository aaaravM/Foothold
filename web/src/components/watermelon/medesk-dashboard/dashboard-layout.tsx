"use client";

/*
 * Watermelon UI "medesk-dashboard" (MIT), rethemed for Foothold: the portal frame.
 * Fixed-height by default so it can sit inside a page (the original filled the viewport
 * with h-svh). Pass className to change the height.
 */
import type { CSSProperties, ReactNode } from "react";
import { DashboardSidebar } from "./components/medesk/sidebar";
import { DashboardTopbar } from "./components/medesk/topbar";
import { SidebarProvider } from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";
import type { DashboardOrg, NavigationGroup } from "./data";
import "./dashboard.css";

type DashboardLayoutProps = {
  children: ReactNode;
  groups: NavigationGroup[];
  org: DashboardOrg;
  brand?: ReactNode;
  accountSlot?: ReactNode;
  sheetLabel?: string;
  topbarActions?: ReactNode;
  className?: string;
};

export default function DashboardLayout({
  children,
  groups,
  org,
  brand,
  accountSlot,
  sheetLabel,
  topbarActions,
  className,
}: DashboardLayoutProps) {
  return (
    <SidebarProvider
      defaultOpen
      data-lib="watermelon"
      className={cn(
        "medesk-dashboard relative h-[min(56rem,100svh)] min-h-0! overflow-hidden border border-line bg-surface no-scrollbar",
        className,
      )}
      style={
        {
          "--sidebar-width": "15rem",
          "--sidebar-width-icon": "3.5rem",
        } as CSSProperties
      }
    >
      <DashboardSidebar groups={groups} org={org} brand={brand} accountSlot={accountSlot} />

      <main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-background">
        <DashboardTopbar groups={groups} sheetLabel={sheetLabel} actions={topbarActions} />
        <div className="flex-1 overflow-y-auto">{children}</div>
      </main>
    </SidebarProvider>
  );
}
