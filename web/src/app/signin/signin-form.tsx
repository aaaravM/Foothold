"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAccount } from "@/components/auth/auth-provider";
import { Initials } from "@/components/auth/parts";
import { FieldLabel } from "@/components/auth/auth-shell";
import { SwapArrow, TextRoll } from "@/components/motion/kit";
import { isApiError, isOfflineError } from "@/lib/api";
import { DEMO_ACCOUNTS, destinationFor } from "@/lib/auth";
import { cn } from "@/lib/utils";

export function SignInForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next");
  const { status, account, signIn, signOut } = useAccount();
  // ?as=<persona_id> pre-fills a demo account (presenter links on /demo)
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
        <div className="flex items-center gap-4">
          <Initials account={account} size="lg" />
          <div className="min-w-0">
            <p className="truncate text-lg font-medium text-ink">{account.display_name}</p>
            <p className="text-sm text-ink-muted">You&rsquo;re signed in.</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <Link href={destinationFor(account, next)} className="btn-primary group">
            <TextRoll text="Continue" />
            <SwapArrow />
          </Link>
          <button type="button" className="text-sm text-ink-muted underline-offset-4 hover:text-ink hover:underline" onClick={() => void signOut()}>
            Sign out
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <form onSubmit={onSubmit} noValidate className="space-y-5" aria-describedby={error ? "signin-error" : undefined}>
        <div>
          <FieldLabel htmlFor="signin-email">Email</FieldLabel>
          <input
            ref={emailRef}
            id="signin-email"
            type="email"
            autoComplete="username"
            inputMode="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="field"
            placeholder="you@example.com"
            aria-invalid={error ? true : undefined}
          />
        </div>
        <div>
          <FieldLabel htmlFor="signin-password">Password</FieldLabel>
          <input
            id="signin-password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="field"
            aria-invalid={error ? true : undefined}
          />
        </div>
        <p id="signin-error" role="alert" className={cn("min-h-5 text-sm text-danger", !error && "sr-only")}>
          {error ?? ""}
        </p>
        <button type="submit" disabled={busy || status === "loading"} className="btn-primary group w-full">
          <TextRoll text={busy ? "Signing in…" : "Sign in"} />
          <SwapArrow />
        </button>
      </form>
      <p className="text-center text-sm text-ink-muted">
        New to Foothold?{" "}
        <Link href={next ? `/signup?next=${encodeURIComponent(next)}` : "/signup"} className="font-medium text-ink underline decoration-accent decoration-2 underline-offset-4 hover:text-accent">
          Create an account
        </Link>
      </p>
    </div>
  );
}
