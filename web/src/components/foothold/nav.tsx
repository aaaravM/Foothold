"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion, useMotionValueEvent, useReducedMotion, useScroll } from "motion/react";
import { cn } from "@/lib/utils";
import { isSheetActive, navSheetsFor, type NavAccountKind } from "@/lib/sheets";
import { AccountSlot } from "@/components/auth/account-slot";
import { useAccount } from "@/components/auth/auth-provider";
import { PlaceSwitcher } from "@/components/auth/place-switcher";
import { EASE, EASE_WIPE, TextRoll } from "@/components/motion/kit";
import { ThemeToggle } from "./theme-toggle";

function Wordmark() {
  return (
    <Link href="/" className="group inline-flex h-9 items-center gap-2 rounded-full pr-2 text-ink" aria-label="Foothold home">
      <svg viewBox="0 0 18 18" className="size-[18px] text-accent" fill="none" stroke="currentColor" strokeWidth={1.9} aria-hidden="true">
        <path
          d="M1.5 16.5h5v-5h5v-5h5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="[stroke-dasharray:40] [stroke-dashoffset:0] transition-[stroke-dashoffset] duration-700 group-hover:[stroke-dashoffset:80]"
        />
      </svg>
      <span className="font-display text-[1.08rem] leading-none font-bold tracking-[-0.03em]">Foothold</span>
    </Link>
  );
}

function useNavKind(): NavAccountKind {
  const { account, status } = useAccount();
  if (status !== "signed_in" || !account) return null;
  return account.kind;
}

function DesktopLinks() {
  const pathname = usePathname();
  const kind = useNavKind();
  const items = navSheetsFor(kind);
  const [hover, setHover] = React.useState<string | null>(null);
  return (
    <ul className="flex items-center gap-0.5" onMouseLeave={() => setHover(null)}>
      {items.map((s) => {
        const active = isSheetActive(s, pathname);
        return (
          <li key={s.id} className="relative">
            <Link
              href={s.href}
              aria-current={active ? "page" : undefined}
              onMouseEnter={() => setHover(s.id)}
              className={cn(
                "group relative inline-flex h-9 items-center rounded-full px-3.5 text-[0.9rem] font-medium transition-colors duration-300",
                active ? "text-ink" : "text-ink-muted hover:text-ink",
              )}
            >
              {hover === s.id ? (
                <motion.span layoutId="nav-hover" className="absolute inset-0 rounded-full bg-ink/[0.06]" transition={{ duration: 0.45, ease: EASE }} />
              ) : null}
              {active ? (
                <motion.span
                  layoutId="nav-active"
                  className="absolute bottom-1 left-1/2 h-[3px] w-4 -translate-x-1/2 rounded-full bg-accent"
                  transition={{ duration: 0.6, ease: EASE }}
                />
              ) : null}
              <span className="relative">
                <TextRoll text={s.navLabel ?? s.title} />
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function MobileMenu({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const kind = useNavKind();
  const items = [{ id: "home", href: "/", label: "Home" }, ...navSheetsFor(kind).map((s) => ({ id: s.id, href: s.href, label: s.navLabel ?? s.title }))];
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const main = document.getElementById("main");
    main?.setAttribute("inert", "");
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      main?.removeAttribute("inert");
      document.body.style.overflow = "";
    };
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          key="menu"
          id="mobile-menu"
          initial={{ clipPath: "inset(0 0 100% 0)" }}
          animate={{ clipPath: "inset(0 0 0% 0)" }}
          exit={{ clipPath: "inset(0 0 100% 0)" }}
          transition={{ duration: 0.7, ease: EASE_WIPE }}
          className="fixed inset-x-0 top-[var(--nav-h)] bottom-0 z-40 flex flex-col bg-bg px-[var(--page-pad)] pt-8 pb-10 lg:hidden"
        >
          <nav aria-label="Main">
            <ul className="space-y-1">
              {items.map((it, i) => {
                const active = it.href === "/" ? pathname === "/" : pathname?.startsWith(it.href);
                return (
                  <li key={it.id} className="overflow-hidden">
                    <motion.div initial={{ y: "110%" }} animate={{ y: 0 }} transition={{ duration: 0.8, ease: EASE, delay: 0.18 + i * 0.06 }}>
                      <Link
                        href={it.href}
                        onClick={onClose}
                        aria-current={active ? "page" : undefined}
                        className={cn("flex items-center gap-3 py-2 font-display text-[2.6rem] leading-none font-semibold tracking-[-0.04em]", active ? "text-ink" : "text-ink-muted")}
                      >
                        {active ? <span className="size-2 rounded-full bg-accent" aria-hidden="true" /> : null}
                        {it.label}
                      </Link>
                    </motion.div>
                  </li>
                );
              })}
            </ul>
          </nav>
          <div className="mt-auto flex items-center justify-between">
            <ThemeToggle showLabel />
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

/** App-first top bar: hides on scroll down, returns on scroll up; animated active tab. */
export function Nav() {
  const reduce = useReducedMotion();
  const { scrollY } = useScroll();
  const [hidden, setHidden] = React.useState(false);
  const [scrolled, setScrolled] = React.useState(false);
  const [open, setOpen] = React.useState(false);
  const pathname = usePathname();
  const lastPath = React.useRef(pathname);

  useMotionValueEvent(scrollY, "change", (y) => {
    const prev = scrollY.getPrevious() ?? 0;
    const d = y - prev;
    setScrolled(y > 8);
    if (open) return;
    if (y > 240 && d > 2) setHidden(true);
    else if (d < -4 || y < 120) setHidden(false);
  });

  React.useEffect(() => {
    if (lastPath.current !== pathname) {
      lastPath.current = pathname;
      const t = window.setTimeout(() => {
        setOpen(false);
        setHidden(false);
      }, 0);
      return () => window.clearTimeout(t);
    }
  }, [pathname]);

  const close = React.useCallback(() => setOpen(false), []);

  return (
    <>
      <motion.header
        initial={false}
        animate={{ y: hidden && !reduce ? -90 : 0 }}
        transition={{ duration: 0.8, ease: EASE }}
        className={cn("sticky top-0 z-50 transition-[background-color,border-color] duration-500", scrolled || open ? "nav-blur border-b border-line/60" : "border-b border-transparent")}
      >
        <div className="page-container flex h-[var(--nav-h)] items-center gap-3">
          <Wordmark />
          <nav aria-label="Main" className="ml-4 hidden lg:block">
            <DesktopLinks />
          </nav>
          <div className="ml-auto flex items-center gap-1 sm:gap-1.5">
            <PlaceSwitcher />
            <AccountSlot />
            <span className="hidden lg:inline-flex">
              <ThemeToggle />
            </span>
            <button
              type="button"
              aria-expanded={open}
              aria-controls="mobile-menu"
              aria-label={open ? "Close menu" : "Open menu"}
              onClick={() => setOpen((o) => !o)}
              className="relative grid size-10 place-items-center rounded-full text-ink hover:bg-ink/5 lg:hidden"
            >
              <span aria-hidden="true" className={cn("absolute h-[1.5px] w-5 rounded-full bg-current transition-transform duration-500 [transition-timing-function:var(--ease-expo)]", open ? "rotate-45" : "-translate-y-[4px]")} />
              <span aria-hidden="true" className={cn("absolute h-[1.5px] w-5 rounded-full bg-current transition-transform duration-500 [transition-timing-function:var(--ease-expo)]", open ? "-rotate-45" : "translate-y-[4px]")} />
            </button>
          </div>
        </div>
      </motion.header>
      <MobileMenu open={open} onClose={close} />
    </>
  );
}
