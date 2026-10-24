"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Clapperboard, Menu, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { isSheetActive, NAV_SHEETS, SHEETS, type SheetMeta } from "@/lib/sheets";
import { Button } from "@/components/ui/button";
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { ApiStatus } from "./api-status";
import { useCommandPalette } from "./command-palette";
import { PersonaSwitcher } from "./persona-switcher";
import { ThemeToggle } from "./theme-toggle";

/* ------------------------------------------------------------------ */

function Wordmark() {
  return (
    <Link href="/" className="group inline-flex items-center gap-2 rounded-sm text-ink" aria-label="Foothold, cover sheet">
      <svg viewBox="0 0 18 18" className="size-[18px] text-accent" fill="none" stroke="currentColor" strokeWidth={1.75} aria-hidden="true">
        <path d="M1.5 16.5h5v-5h5v-5h5" strokeLinecap="square" />
      </svg>
      <span className="font-display text-[1.05rem] leading-none font-bold tracking-[-0.02em]">Foothold</span>
    </Link>
  );
}

function SheetLinks({ pathname, onNavigate }: { pathname: string | null; onNavigate?: boolean }) {
  return (
    <ol className="flex items-center">
      {NAV_SHEETS.map((s) => {
        const active = isSheetActive(s, pathname);
        const link = (
          <Link
            href={s.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "label-mono relative inline-flex h-14 items-center gap-1.5 px-2.5 transition-colors",
              active ? "text-ink" : "text-ink-faint hover:text-ink",
            )}
          >
            <span className={active ? "text-accent" : undefined}>{s.sheet}</span>
            <span>{s.code}</span>
            <span
              aria-hidden="true"
              className={cn("absolute inset-x-2.5 bottom-0 h-0.5 transition-colors", active ? "bg-accent" : "bg-transparent")}
            />
          </Link>
        );
        return <li key={s.id}>{onNavigate ? <SheetClose asChild>{link}</SheetClose> : link}</li>;
      })}
    </ol>
  );
}

function ActiveSheetLinks() {
  const pathname = usePathname();
  return <SheetLinks pathname={pathname} />;
}

/* ------------------------------------------------------------------ */

const subscribeNoop = () => () => undefined;
const isMacPlatform = () => typeof navigator !== "undefined" && /Mac|iPhone|iPad|iPod/i.test(navigator.platform || navigator.userAgent);

function CommandHint() {
  const { setOpen } = useCommandPalette();
  const mac = React.useSyncExternalStore(subscribeNoop, isMacPlatform, () => false);
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={() => setOpen(true)}
      aria-keyshortcuts="Meta+K Control+K"
      aria-label="Open command palette"
      className="hidden gap-2 text-ink-muted hover:text-ink sm:inline-flex"
    >
      <Search aria-hidden="true" />
      <kbd className="label-mono text-ink">{mac ? "⌘K" : "Ctrl K"}</kbd>
    </Button>
  );
}

/* ------------------------------------------------------------------ */

function MobileSheetList({ pathname }: { pathname: string | null }) {
  const cover = SHEETS.find((s) => s.id === "home") as SheetMeta;
  const demo = SHEETS.find((s) => s.id === "demo") as SheetMeta;
  const items = [cover, ...NAV_SHEETS];
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
                <span className={cn("label-mono w-8 shrink-0", active ? "text-accent" : "text-ink-faint")}>{s.sheet}</span>
                <span className="flex min-w-0 flex-col">
                  <span className="font-display text-lg leading-tight font-semibold">{s.title}</span>
                  <span className="text-xs text-ink-muted">{s.description}</span>
                </span>
              </Link>
            </SheetClose>
          </li>
        );
      })}
      <li>
        <SheetClose asChild>
          <Link href={demo.href} className="flex items-center gap-3 px-4 py-3 text-ink-muted transition-colors hover:bg-muted hover:text-ink">
            <Clapperboard aria-hidden="true" className="size-4 text-accent" />
            <span className="label-mono">Start demo mode</span>
          </Link>
        </SheetClose>
      </li>
    </ol>
  );
}

function ActiveMobileSheetList() {
  const pathname = usePathname();
  return <MobileSheetList pathname={pathname} />;
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
          <SheetDescription className="sr-only">Jump to a sheet, switch persona or theme.</SheetDescription>
        </SheetHeader>
        <nav aria-label="Sheets" className="py-4">
          <React.Suspense fallback={<MobileSheetList pathname={null} />}>
            <ActiveMobileSheetList />
          </React.Suspense>
        </nav>
        <div className="mt-auto flex flex-wrap items-center gap-2 border-t border-line px-4 py-4">
          <PersonaSwitcher />
          <ThemeToggle showLabel />
          <ApiStatus showLabel />
        </div>
      </SheetContent>
    </Sheet>
  );
}

/* ------------------------------------------------------------------ */

/** Top bar: wordmark, sheet links 01..07 (xl+), ⌘K hint, API dot, persona, theme; sheet index drawer below xl. */
export function Nav() {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-background/90 backdrop-blur-md supports-backdrop-filter:bg-background/75">
      <div className="mx-auto flex h-14 max-w-[1440px] items-center gap-3 px-3 sm:px-6 lg:px-8">
        <Wordmark />
        <nav aria-label="Sheets" className="ml-4 hidden xl:block">
          <React.Suspense fallback={<SheetLinks pathname={null} />}>
            <ActiveSheetLinks />
          </React.Suspense>
        </nav>
        <div className="ml-auto flex items-center gap-1 sm:gap-1.5">
          <CommandHint />
          <ApiStatus className="hidden sm:inline-flex" />
          <PersonaSwitcher className="hidden sm:inline-flex" />
          <ThemeToggle className="hidden sm:inline-flex" />
          <MobileMenu />
        </div>
      </div>
    </header>
  );
}
