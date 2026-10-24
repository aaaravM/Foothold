"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";
import { cn } from "@/lib/utils";
import { isSheetActive, navSheetsFor, SHEETS, type NavAccountKind, type SheetMeta } from "@/lib/sheets";
import { AccountSlot } from "@/components/auth/account-slot";
import { useAccount } from "@/components/auth/auth-provider";
import { Button } from "@/components/ui/button";
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { ThemeToggle } from "./theme-toggle";

/* ------------------------------------------------------------------ */

/** Corner brackets that snap in on hover / keyboard focus of the nearest .bk-host. */
function Corners() {
  return (
    <>
      <span aria-hidden="true" className="bk" data-corner="tl" />
      <span aria-hidden="true" className="bk" data-corner="tr" />
      <span aria-hidden="true" className="bk" data-corner="bl" />
      <span aria-hidden="true" className="bk" data-corner="br" />
    </>
  );
}

function Wordmark() {
  return (
    <Link
      href="/"
      className="bk-host group inline-flex h-9 items-center gap-2 rounded-[1px] px-1.5 text-ink [--bk-inset:-2px]"
      aria-label="Foothold, cover sheet"
    >
      <svg viewBox="0 0 18 18" className="size-[18px] text-accent" fill="none" stroke="currentColor" strokeWidth={1.75} aria-hidden="true">
        <path d="M1.5 16.5h5v-5h5v-5h5" strokeLinecap="square" />
      </svg>
      <span className="font-display text-[1.05rem] leading-none font-bold tracking-[-0.02em] [font-variation-settings:'wdth'_112]">
        Foothold
      </span>
      <Corners />
    </Link>
  );
}

/** Account kind for the nav. While the session loads, only public sheets show (no flash of learner links). */
function useNavKind(): NavAccountKind {
  const { account, status } = useAccount();
  if (status !== "signed_in" || !account) return null;
  return account.kind;
}

function SheetLinks({ pathname, kind }: { pathname: string | null; kind: NavAccountKind }) {
  const items = navSheetsFor(kind);
  return (
    <ol className="flex items-center gap-0.5">
      {items.map((s) => {
        const active = isSheetActive(s, pathname);
        return (
          <li key={s.id}>
            <Link
              href={s.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "bk-host label-mono group relative inline-flex h-9 items-center gap-1.5 px-2.5 transition-colors duration-150 [--bk-inset:0px]",
                active ? "text-ink" : "text-ink-faint hover:text-ink",
              )}
            >
              <span className="link-draw [--ul-offset:-5px]" data-drawn={active ? "true" : undefined}>
                {s.navLabel ?? s.title}
              </span>
              <Corners />
            </Link>
          </li>
        );
      })}
    </ol>
  );
}

function ActiveSheetLinks() {
  const pathname = usePathname();
  const kind = useNavKind();
  return <SheetLinks pathname={pathname} kind={kind} />;
}

function StaticSheetLinks() {
  const kind = useNavKind();
  return <SheetLinks pathname={null} kind={kind} />;
}

/* ------------------------------------------------------------------ */

function MobileSheetList({ pathname, kind }: { pathname: string | null; kind: NavAccountKind }) {
  const cover = SHEETS.find((s) => s.id === "home") as SheetMeta;
  const items = [cover, ...navSheetsFor(kind)];
  return (
    <ol className="divide-y divide-line border-y border-line">
      {items.map((s) => {
        const active = s.id === "home" ? pathname === "/" : isSheetActive(s, pathname);
        return (
          <li key={s.id}>
            <SheetClose asChild>
              <Link
                href={s.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-baseline gap-3 px-4 py-3 transition-colors hover:bg-muted",
                  active ? "text-ink" : "text-ink-muted",
                )}
              >
                <span className="flex min-w-0 flex-col">
                  <span className="font-display text-lg leading-tight font-semibold">{s.navLabel ?? s.title}</span>
                  <span className="text-xs text-ink-muted">{s.description}</span>
                </span>
              </Link>
            </SheetClose>
          </li>
        );
      })}
    </ol>
  );
}

function ActiveMobileSheetList() {
  const pathname = usePathname();
  const kind = useNavKind();
  return <MobileSheetList pathname={pathname} kind={kind} />;
}

function StaticMobileSheetList() {
  const kind = useNavKind();
  return <MobileSheetList pathname={null} kind={kind} />;
}

function MobileMenu() {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button type="button" variant="ghost" size="icon" aria-label="Open sheet index" className="text-ink-muted hover:text-ink xl:hidden">
          <Menu aria-hidden="true" />
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-[88vw] gap-0 overflow-y-auto p-0 sm:max-w-sm">
        <SheetHeader className="border-b border-line px-4 py-4">
          <SheetTitle className="label-mono text-ink-muted">Sheet index</SheetTitle>
          <SheetDescription className="sr-only">Jump to a sheet or switch the theme.</SheetDescription>
        </SheetHeader>
        <nav aria-label="Sheets" className="py-4">
          <React.Suspense fallback={<StaticMobileSheetList />}>
            <ActiveMobileSheetList />
          </React.Suspense>
        </nav>
        <div className="mt-auto flex flex-wrap items-center gap-3 border-t border-line px-4 py-4">
          <ThemeToggle showLabel />
        </div>
      </SheetContent>
    </Sheet>
  );
}

/* ------------------------------------------------------------------ */

/**
 * Top bar: wordmark, the sheets issued to this account (xl+), then only the account menu and
 * the theme toggle on the right (CONTRACTS section 13). Below xl the sheets move into a drawer.
 */
export function Nav() {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-background">
      <div className="page-container flex h-[var(--nav-h)] items-center gap-3">
        <Wordmark />
        <nav aria-label="Sheets" className="ml-3 hidden xl:block">
          <React.Suspense fallback={<StaticSheetLinks />}>
            <ActiveSheetLinks />
          </React.Suspense>
        </nav>
        <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
          <AccountSlot />
          <ThemeToggle />
          <MobileMenu />
        </div>
      </div>
    </header>
  );
}
