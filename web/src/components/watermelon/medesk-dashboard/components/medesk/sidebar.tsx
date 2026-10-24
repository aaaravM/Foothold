"use client";

/*
 * Watermelon UI "medesk-dashboard" (MIT), rethemed for Foothold.
 * Kept: collapsible icon sidebar, grouped nav with collapsible groups, tooltips when
 * collapsed, mobile sheet. Removed: the bundled ThemeProvider toggle (Foothold's theme
 * lives on <html data-theme>), the Medesk logo, the user dropdown with outside links and
 * the remote avatar. The footer shows the signed-in organization and an optional
 * `accountSlot` (e.g. the AuthProvider's account menu).
 */
import type { ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import { SidebarCollapseIcon } from "./icons";
import { DashboardLink, useDashboardNavigation } from "./navigation";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import { type DashboardOrg, type NavigationGroup, type NavigationItem } from "../../data";
import { cn } from "@/lib/utils";

const menuButtonClassName = cn(
  "relative h-10 gap-2.5 rounded-none bg-transparent py-2 pl-3 pr-2 text-sm font-normal text-ink-muted transition-colors",
  "hover:!bg-transparent hover:text-ink active:!bg-transparent",
  "aria-[current=page]:!bg-surface-2 aria-[current=page]:text-ink",
  "aria-[current=page]:before:absolute aria-[current=page]:before:inset-y-1.5 aria-[current=page]:before:left-0 aria-[current=page]:before:w-0.5 aria-[current=page]:before:bg-accent",
  "data-open:!bg-transparent data-open:hover:!bg-transparent data-open:text-ink data-active:!bg-transparent",
  "[&_svg]:size-4! [&_svg]:shrink-0",
  "group-data-[collapsible=icon]:size-10! group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:p-0! group-data-[collapsible=icon]:[&>span]:hidden",
);

const sidebarGroupLabelClassName =
  "label-mono h-auto px-0 py-1 text-ink-faint transition-colors";

function NavItem({ item }: { item: NavigationItem }) {
  const { pathname } = useDashboardNavigation();
  const { isMobile, setOpenMobile } = useSidebar();
  const isActive =
    item.href === "/"
      ? pathname === "/"
      : pathname === item.href || pathname.startsWith(`${item.href}/`);

  return (
    <SidebarMenuButton
      asChild
      tooltip={item.name}
      className={menuButtonClassName}
    >
      <DashboardLink
        href={item.href}
        aria-current={isActive ? "page" : undefined}
        onClick={() => {
          if (isMobile) setOpenMobile(false);
        }}
      >
        <item.icon aria-hidden="true" />
        <span>{item.name}</span>
        {item.badge ? <SidebarMenuBadge className="font-mono">{item.badge}</SidebarMenuBadge> : null}
      </DashboardLink>
    </SidebarMenuButton>
  );
}

export interface DashboardSidebarProps {
  groups: NavigationGroup[];
  org: DashboardOrg;
  /** brand block in the header; defaults to the Foothold employer mark */
  brand?: ReactNode;
  /** rendered under the org block (e.g. an account menu) */
  accountSlot?: ReactNode;
}

function DefaultBrand() {
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <span
        className="font-display text-lg leading-none font-bold tracking-tight text-ink"
        style={{ fontVariationSettings: '"wdth" 112' }}
      >
        Foothold
      </span>
      <span className="label-mono text-ink-faint">Employer · DWG-004</span>
    </div>
  );
}

export function DashboardSidebar({ groups, org, brand, accountSlot }: DashboardSidebarProps) {
  const { state, toggleSidebar } = useSidebar();

  return (
    <Sidebar collapsible="icon" className="border-r border-line!">
      <SidebarHeader className="relative h-16 flex-row items-center justify-between gap-3 border-b border-line px-4 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0">
        <div className="flex min-w-0 items-center gap-3 transition-opacity group-data-[collapsible=icon]:hidden">
          {brand ?? <DefaultBrand />}
        </div>
        <Button
          variant="ghost"
          onClick={toggleSidebar}
          aria-label={
            state === "expanded" ? "Collapse sidebar" : "Expand sidebar"
          }
          className="size-9 rounded-none text-ink-muted hover:text-ink"
        >
          <SidebarCollapseIcon className="size-4.5 transition-transform group-data-[collapsible=icon]:rotate-180" />
        </Button>
      </SidebarHeader>

      <SidebarContent className="gap-5 px-3 py-4 group-data-[collapsible=icon]:overflow-auto!">
        {groups.map((group) => {
          const isCollapsible = group.collapsible ?? false;

          if (isCollapsible) {
            return (
              <Collapsible
                key={group.label}
                defaultOpen
                className="group/collapsible"
              >
                <SidebarGroup className="gap-1 p-0">
                  <SidebarGroupLabel
                    asChild
                    className={sidebarGroupLabelClassName}
                  >
                    <CollapsibleTrigger className="flex w-full items-center justify-between transition-colors hover:text-ink">
                      <span>{group.label}</span>
                      <ChevronRight className="ml-auto size-3.5 transition-transform group-data-[state=open]/collapsible:rotate-90" />
                    </CollapsibleTrigger>
                  </SidebarGroupLabel>
                  <CollapsibleContent>
                    <SidebarGroupContent>
                      <SidebarMenu className="gap-0.5">
                        {group.items.map((item) => (
                          <SidebarMenuItem key={item.name}>
                            <NavItem item={item} />
                          </SidebarMenuItem>
                        ))}
                      </SidebarMenu>
                    </SidebarGroupContent>
                  </CollapsibleContent>
                </SidebarGroup>
              </Collapsible>
            );
          }

          return (
            <SidebarGroup key={group.label} className="gap-1 p-0">
              <SidebarGroupLabel className={sidebarGroupLabelClassName}>
                {group.label}
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu className="gap-0.5">
                  {group.items.map((item) => (
                    <SidebarMenuItem key={item.name}>
                      <NavItem item={item} />
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          );
        })}
      </SidebarContent>

      <SidebarFooter className="gap-3 border-t border-line px-3 py-3">
        <div className="flex min-w-0 items-center gap-2.5 group-data-[collapsible=icon]:justify-center">
          <span
            aria-hidden="true"
            className="flex size-8 shrink-0 items-center justify-center border border-line-strong font-mono text-[11px] tracking-[0.08em] text-ink"
          >
            {org.initials}
          </span>
          <div className="flex min-w-0 flex-col gap-1 group-data-[collapsible=icon]:hidden">
            <span className="truncate text-sm leading-none text-ink">{org.name}</span>
            <span className="flex items-center gap-2">
              {org.role ? <span className="label-mono text-ink-faint">{org.role}</span> : null}
              
            </span>
          </div>
        </div>
        {accountSlot ? <div className="group-data-[collapsible=icon]:hidden">{accountSlot}</div> : null}
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
