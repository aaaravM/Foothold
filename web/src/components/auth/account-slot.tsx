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
import { FictionalTag } from "@/components/foothold/fictional-tag";
import { useAccount } from "./auth-provider";
import { Brackets, Initials, PLOT_EASE } from "./parts";

/* ------------------------------------------------------------------ */
/* Signed out: "Sign in" (returns here afterwards)                     */
/* ------------------------------------------------------------------ */

function SignInLink({ href, className }: { href: string; className?: string }) {
  return (
    <Link
      href={href}
      className={cn(
        "group/bracket label-mono relative inline-flex h-8 items-center gap-2 border border-line px-3 text-ink transition-colors hover:border-line-strong",
        className,
      )}
    >
      <Brackets />
      <span>Sign in</span>
      <span aria-hidden="true" className="text-ink-faint transition-transform duration-150 group-hover/bracket:translate-x-0.5">
        →
      </span>
    </Link>
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

function formatClock(ms: number): string {
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(ms);
}

function AccountMenu({ account, className }: { account: Account; className?: string }) {
  const { signOut, expiresAt } = useAccount();
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
            "group/bracket relative inline-flex h-9 items-center gap-2.5 pr-2 pl-1 text-ink transition-colors outline-none",
            "hover:bg-surface-2 data-[state=open]:bg-surface-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
            className,
          )}
        >
          <Brackets active={open} />
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
          className="z-50 w-[20rem] max-w-[calc(100vw-1.5rem)] border border-line bg-surface text-ink outline-none"
        >
          <motion.div
            initial={reduce ? false : { clipPath: "inset(0 0 100% 0)" }}
            animate={{ clipPath: "inset(0 0 0% 0)" }}
            transition={{ duration: 0.26, ease: PLOT_EASE }}
          >
            <div className="flex items-center justify-between border-b border-line px-4 py-2">
              <span className="label-mono text-ink-faint">Account</span>
              <span className="label-mono text-ink-faint">This tab</span>
            </div>

            <div className="flex items-start gap-3 px-4 pt-4 pb-3">
              <Initials account={account} size="md" />
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="truncate font-display text-base leading-tight font-semibold">{account.display_name}</span>
                  <FictionalTag compact />
                </div>
                <p className="truncate font-mono text-[0.7rem] text-ink-muted">{account.email}</p>
              </div>
            </div>

            <dl className="mx-4 mb-3 divide-y divide-line border-y border-line text-sm">
              <div className="flex items-baseline justify-between gap-4 py-2">
                <dt className="label-mono text-ink-faint">Role</dt>
                <dd className="truncate text-right text-ink">{role}</dd>
              </div>
              <div className="flex items-baseline justify-between gap-4 py-2">
                <dt className="label-mono text-ink-faint">Session</dt>
                <dd className="text-right text-ink-muted tabular-nums">
                  {expiresAt ? `Until ${formatClock(expiresAt)}` : "Active"}
                </dd>
              </div>
            </dl>

            <div className="border-t border-line py-1">
              <Menu.Item asChild>
                <Link href={home.href} className={itemClass}>
                  <ArrowUpRight aria-hidden="true" className="size-4 text-ink-faint" />
                  <span className="flex-1">Open your home sheet</span>
                  <span className="label-mono text-ink-faint">
                    {home.sheet} / {home.code}
                  </span>
                </Link>
              </Menu.Item>
              <Menu.Item className={itemClass} onSelect={onSignOut}>
                <LogOut aria-hidden="true" className="size-4 text-ink-faint" />
                <span className="flex-1">Sign out</span>
                <span className="label-mono text-ink-faint">This tab</span>
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
