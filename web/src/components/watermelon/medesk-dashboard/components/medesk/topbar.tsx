"use client";

/*
 * Watermelon UI "medesk-dashboard" (MIT), rethemed for Foothold.
 * Removed per the product decision: the ⌘K / Ctrl+K search shortcut and its key hint
 * (Foothold is an app without a command palette), and the invented "Last synced" line.
 * Kept: mobile sidebar trigger and the current-page title. `actions` fills the right side.
 */
import type { ReactNode } from "react";
import { useDashboardNavigation } from "./navigation";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { type NavigationGroup } from "../../data";

export function DashboardTopbar({
  groups,
  sheetLabel,
  actions,
}: {
  groups: NavigationGroup[];
  /** mono drawing label next to the page title, e.g. "SHEET 04 / EMPLOYERS" */
  sheetLabel?: string;
  actions?: ReactNode;
}) {
  const { pathname } = useDashboardNavigation();
  const items = groups.flatMap((group) => group.items);
  const currentPage = items.find((item) => item.href === pathname) ?? items[0];
  const CurrentPageIcon = currentPage.icon;

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-line px-4 md:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <SidebarTrigger
          size="icon"
          className="shrink-0 rounded-none md:hidden [&_svg]:size-4.5!"
        />
        <div className="flex min-w-0 items-center gap-2.5">
          <CurrentPageIcon aria-hidden="true" className="size-4 shrink-0 text-ink-muted" />
          <span className="truncate text-[15px] leading-6 font-medium text-ink">{currentPage.name}</span>
        </div>
        {sheetLabel ? (
          <span className="label-mono hidden truncate text-ink-faint lg:inline">· {sheetLabel}</span>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </header>
  );
}
