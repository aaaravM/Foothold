"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { DropdownMenu as Menu } from "radix-ui";
import { motion, useReducedMotion } from "motion/react";
import { ArrowUpRight, ChevronDown, LogOut } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { homeFor, roleLabel, signInHref, type Account } from "@/lib/auth";
import { sheetForPath } from "@/lib/sheets";
import { useAccount } from "./auth-provider";
import { Initials } from "./parts";
import { EASE, SwapArrow, TextRoll } from "@/components/motion/kit";

/* ------------------------------------------------------------------ */
/* Signed out: "Sign in" (returns here afterwards)                     */
/* ------------------------------------------------------------------ */

function SignInLink({ href, className }: { href: string; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1", className)}>
      <Link href={href} className="group inline-flex h-9 items-center rounded-full px-3 text-[0.9rem] font-medium text-ink-muted transition-colors hover:text-ink">
        <TextRoll text="Sign in" />
      </Link>
      <Link
        href="/signup"
        className="group relative isolate inline-flex h-9 items-center gap-1.5 overflow-hidden rounded-full bg-ink pr-3 pl-3.5 text-[0.9rem] font-semibold text-bg transition-colors duration-500 hover:text-accent-ink"
      >
        <span aria-hidden="true" className="absolute inset-0 -z-10 translate-y-full rounded-full bg-accent transition-transform duration-500 [transition-timing-function:var(--ease-expo)] group-hover:translate-y-0" />
        <TextRoll text="Sign up" />
        <SwapArrow className="size-3" />
      </Link>
    </span>
  );
}

function SignInLinkHere({ className }: { className?: string }) {
  const pathname = usePathname();
  return <SignInLink href={signInHref(pathname)} className={className} />;
}

/* ------------------------------------------------------------------ */
/* Signed in: account menu                                             */
/* ------------------------------------------------------------------ */

const itemClass =
  "group/item relative flex w-full cursor-default items-center gap-3 px-4 py-2.5 text-left text-sm text-ink outline-none select-none " +
  "transition-colors data-[highlighted]:bg-surface-2 " +
  "before:absolute before:top-1/2 before:left-0 before:h-4 before:w-0.5 before:-translate-y-1/2 before:bg-accent before:opacity-0 " +
  "before:transition-opacity data-[highlighted]:before:opacity-100";

function AccountMenu({ account, className }: { account: Account; className?: string }) {
  const { signOut } = useAccount();
  const router = useRouter();
  const reduce = useReducedMotion();
  const [open, setOpen] = React.useState(false);
  const home = sheetForPath(homeFor(account));
  const role = roleLabel(account);

  const onSignOut = () => {
    void signOut();
    toast("Signed out of this tab", { description: "Other tabs keep their own sign-in." });
    router.push("/signin");
  };

  return (
    <Menu.Root open={open} onOpenChange={setOpen} modal={false}>
      <Menu.Trigger asChild>
        <button
          type="button"
          aria-label={`Account: ${account.display_name}, ${role}. Open account menu`}
          className={cn(
            "group/bracket relative inline-flex h-9 items-center gap-2 rounded-full pr-2.5 pl-1 text-ink transition-colors outline-none",
            "hover:bg-surface-2 data-[state=open]:bg-surface-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
            className,
          )}
        >
          <Initials account={account} />
          <span className="hidden max-w-[18ch] truncate text-sm font-medium sm:inline">{account.display_name}</span>
          <ChevronDown
            aria-hidden="true"
            className="size-3.5 text-ink-faint transition-transform duration-200 group-data-[state=open]/bracket:rotate-180"
          />
        </button>
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Content
          align="end"
          sideOffset={8}
          collisionPadding={12}
          className="z-50 w-[19rem] max-w-[calc(100vw-1.5rem)] overflow-hidden rounded-2xl border border-line bg-surface text-ink shadow-2xl shadow-black/40 outline-none"
        >
          <motion.div
            initial={reduce ? false : { opacity: 0, y: -6, filter: "blur(6px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            transition={{ duration: 0.45, ease: EASE }}
          >

            <div className="flex items-start gap-3 px-4 pt-4 pb-3">
              <Initials account={account} size="md" />
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="truncate font-display text-base leading-tight font-semibold">{account.display_name}</span>
                </div>
                <p className="truncate font-mono text-[0.7rem] text-ink-muted">{account.email}</p>
              </div>
            </div>

            <p className="mx-4 mb-3 text-sm text-ink-muted">{role}</p>

            <div className="border-t border-line py-1">
              <Menu.Item asChild>
                <Link href={home.href} className={itemClass}>
                  <ArrowUpRight aria-hidden="true" className="size-4 text-ink-faint" />
                  <span className="flex-1">Go to {home.navLabel ?? home.title}</span>
                </Link>
              </Menu.Item>
              <Menu.Item className={itemClass} onSelect={onSignOut}>
                <LogOut aria-hidden="true" className="size-4 text-ink-faint" />
                <span className="flex-1">Sign out</span>
              </Menu.Item>
            </div>
          </motion.div>
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
  );
}

/* ------------------------------------------------------------------ */

/**
 * Right side of the nav: "Sign in" when this tab is signed out, otherwise the account
 * menu (initials, name, role, session, sign out). Keyboard accessible (Radix menu).
 */
export function AccountSlot({ className }: { className?: string }) {
  const { status, account } = useAccount();
  if (status === "loading") {
    return <span aria-hidden="true" className={cn("inline-block h-9 w-9 sm:w-28", className)} />;
  }
  if (!account) {
    return (
      <React.Suspense fallback={<SignInLink href="/signin" className={className} />}>
        <SignInLinkHere className={className} />
      </React.Suspense>
    );
  }
  return <AccountMenu account={account} className={className} />;
}
