"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAccount } from "@/components/auth/auth-provider";
import { Brackets, Initials, drawLinkClass, techButtonClass } from "@/components/auth/parts";
import { FictionalTag } from "@/components/foothold/fictional-tag";
import { MonoLabel } from "@/components/foothold/mono-label";
import { isApiError, isOfflineError } from "@/lib/api";
import { DEMO_ACCOUNTS, destinationFor, roleLabel } from "@/lib/auth";
import { cn } from "@/lib/utils";

const fieldClass =
  "h-12 w-full border border-line-strong bg-bg px-3 text-base text-ink placeholder:text-ink-faint " +
  "focus-visible:border-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

export function SignInForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next");
  const { status, account, signIn, signOut } = useAccount();
  // ?as=<persona_id> pre-fills a fictional demo account (presenter links on /demo)
  const preset = DEMO_ACCOUNTS.find((d) => d.persona_id === params.get("as"));
  const [email, setEmail] = React.useState(preset?.email ?? "");
  const [password, setPassword] = React.useState(preset?.password ?? "");
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const emailRef = React.useRef<HTMLInputElement>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError("Enter your email and password.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const acc = await signIn(email.trim(), password);
      router.push(destinationFor(acc, next));
    } catch (err) {
      if (isApiError(err) && err.kind === "http" && (err.status === 401 || err.status === 400)) {
        setError("That email and password don't match an account.");
      } else if (isApiError(err) && err.kind === "http" && err.status === 429) {
        setError("Too many attempts. Wait a minute and try again.");
      } else if (isOfflineError(err)) {
        setError("Can't reach the Foothold server. Check that the API is running, then try again.");
      } else {
        setError("Sign-in failed. Try again.");
      }
      setBusy(false);
    }
  }

  if (status === "signed_in" && account) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4 border border-line p-4">
          <Initials account={account} size="lg" />
          <div className="min-w-0">
            <p className="truncate text-lg text-ink">{account.display_name}</p>
            <MonoLabel as="p">{roleLabel(account)} · signed in on this tab</MonoLabel>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-5">
          <Link href={destinationFor(account, next)} className={techButtonClass}>
            <span>Continue</span>
            <span aria-hidden="true" className="font-mono text-xs">
              ↵
            </span>
            <Brackets offset={5} />
          </Link>
          <button type="button" className={drawLinkClass} onClick={() => void signOut()}>
            Sign out of this tab
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <form onSubmit={onSubmit} noValidate className="space-y-5" aria-describedby={error ? "signin-error" : undefined}>
        <div className="space-y-2">
          <MonoLabel as="label" htmlFor="signin-email" tone="ink">
            Email
          </MonoLabel>
          <input
            ref={emailRef}
            id="signin-email"
            type="email"
            autoComplete="username"
            inputMode="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={fieldClass}
            aria-invalid={error ? true : undefined}
          />
        </div>
        <div className="space-y-2">
          <MonoLabel as="label" htmlFor="signin-password" tone="ink">
            Password
          </MonoLabel>
          <input
            id="signin-password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={fieldClass}
            aria-invalid={error ? true : undefined}
          />
        </div>
        <p id="signin-error" role="alert" className={cn("min-h-6 text-sm text-danger", !error && "sr-only")}>
          {error ?? ""}
        </p>
        <button type="submit" disabled={busy || status === "loading"} className={cn(techButtonClass, "w-full")}>
          <span>{busy ? "Signing in…" : "Sign in"}</span>
          <span aria-hidden="true" className="font-mono text-xs">
            {busy ? "···" : "↵"}
          </span>
          <Brackets offset={5} />
        </button>
        <MonoLabel as="p" tone="faint">
          This tab only · session lasts 12 h
        </MonoLabel>
      </form>

      <details className="group border-t border-line pt-4">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
          <span>Demo accounts (fictional)</span>
          <span aria-hidden="true" className="font-mono text-xs transition-transform group-open:rotate-45">
            +
          </span>
        </summary>
        <ul className="mt-3 divide-y divide-line border border-line">
          {DEMO_ACCOUNTS.map((d) => (
            <li key={d.persona_id}>
              <button
                type="button"
                onClick={() => {
                  setEmail(d.email);
                  setPassword(d.password);
                  setError(null);
                  emailRef.current?.focus();
                }}
                className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-surface-2 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent"
              >
                <Initials account={d} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm text-ink">{d.display_name}</span>
                  <span className="block truncate text-xs text-ink-muted">{d.note}</span>
                </span>
                <MonoLabel tone="faint" className="hidden sm:inline">
                  {d.kind === "employer" ? "Employer" : "Learner"}
                </MonoLabel>
              </button>
            </li>
          ))}
        </ul>
        <div className="mt-2 flex items-center justify-between gap-3">
          <FictionalTag />
          <MonoLabel tone="faint">Click to fill</MonoLabel>
        </div>
      </details>
    </div>
  );
}
