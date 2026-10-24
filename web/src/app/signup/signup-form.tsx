"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { Eye, EyeOff } from "lucide-react";
import { useAccount } from "@/components/auth/auth-provider";
import { FieldLabel } from "@/components/auth/auth-shell";
import { EASE, SwapArrow, TextRoll } from "@/components/motion/kit";
import { apiDetail, isApiError, isOfflineError } from "@/lib/api";
import { destinationFor, safeNextPath } from "@/lib/auth";
import { cn } from "@/lib/utils";

type Kind = "learner" | "employer";

function strength(pw: string): number {
  let s = 0;
  if (pw.length >= 8) s += 1;
  if (pw.length >= 12) s += 1;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) s += 1;
  if (/\d/.test(pw) || /[^A-Za-z0-9]/.test(pw)) s += 1;
  return s;
}

export function SignUpForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNextPath(params.get("next"));
  const { status, account, signUp } = useAccount();
  const [kind, setKind] = React.useState<Kind>(params.get("role") === "employer" ? "employer" : "learner");
  const [name, setName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [org, setOrg] = React.useState("");
  const [show, setShow] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const pw = strength(password);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setError("Tell us your name.");
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setError("Enter a valid email.");
    if (password.length < 8) return setError("Use at least 8 characters for your password.");
    setBusy(true);
    setError(null);
    try {
      await signUp({
        display_name: name.trim(),
        email: email.trim(),
        password,
        kind,
        ...(kind === "employer" && org.trim() ? { org_name: org.trim() } : {}),
      });
      router.push(next ? `/onboarding?next=${encodeURIComponent(next)}` : "/onboarding");
    } catch (err) {
      if (isApiError(err) && err.status === 409) setError("That email already has an account. Sign in instead.");
      else if (isApiError(err) && err.status === 422) setError(apiDetail(err) ?? "Check your details and try again.");
      else if (isApiError(err) && err.status === 429) setError("Too many attempts. Wait a minute and try again.");
      else if (isOfflineError(err)) setError("Can't reach Foothold right now. Try again in a moment.");
      else setError("Sign-up failed. Try again.");
      setBusy(false);
    }
  }

  if (status === "signed_in" && account && !busy) {
    return (
      <div className="space-y-5">
        <p className="text-ink">You&rsquo;re signed in as {account.display_name}.</p>
        <Link href={destinationFor(account, next)} className="btn-primary group">
          <TextRoll text="Continue" />
          <SwapArrow />
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <form onSubmit={onSubmit} noValidate className="space-y-5" aria-describedby={error ? "signup-error" : undefined}>
        <div role="radiogroup" aria-label="I am" className="grid grid-cols-2 gap-1 rounded-full bg-ink/[0.06] p-1">
          {(["learner", "employer"] as const).map((k) => (
            <button
              key={k}
              type="button"
              role="radio"
              aria-checked={kind === k}
              onClick={() => setKind(k)}
              className={cn("relative h-10 rounded-full text-sm font-medium transition-colors duration-300", kind === k ? "text-bg" : "text-ink-muted hover:text-ink")}
            >
              {kind === k ? <motion.span layoutId="signup-kind" className="absolute inset-0 rounded-full bg-ink" transition={{ duration: 0.55, ease: EASE }} /> : null}
              <span className="relative">{k === "learner" ? "I'm exploring careers" : "I'm hiring"}</span>
            </button>
          ))}
        </div>

        <div>
          <FieldLabel htmlFor="su-name">Your name</FieldLabel>
          <input id="su-name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} className="field" placeholder="First and last name" />
        </div>

        <AnimatePresence initial={false}>
          {kind === "employer" ? (
            <motion.div
              key="org"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.5, ease: EASE }}
              className="overflow-hidden"
            >
              <FieldLabel htmlFor="su-org">Company</FieldLabel>
              <input id="su-org" autoComplete="organization" value={org} onChange={(e) => setOrg(e.target.value)} className="field" placeholder="Where you hire for" />
            </motion.div>
          ) : null}
        </AnimatePresence>

        <div>
          <FieldLabel htmlFor="su-email">Email</FieldLabel>
          <input
            id="su-email"
            type="email"
            inputMode="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="field"
            placeholder="you@example.com"
          />
        </div>

        <div>
          <FieldLabel htmlFor="su-password" hint="8+ characters">
            Password
          </FieldLabel>
          <div className="relative">
            <input
              id="su-password"
              type={show ? "text" : "password"}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="field pr-12"
            />
            <button
              type="button"
              onClick={() => setShow((s) => !s)}
              aria-label={show ? "Hide password" : "Show password"}
              className="absolute top-1/2 right-2 grid size-9 -translate-y-1/2 place-items-center rounded-full text-ink-faint hover:text-ink"
            >
              {show ? <EyeOff className="size-4" aria-hidden="true" /> : <Eye className="size-4" aria-hidden="true" />}
            </button>
          </div>
          <div className="mt-2 grid grid-cols-4 gap-1" aria-hidden="true">
            {[0, 1, 2, 3].map((i) => (
              <span key={i} className="h-1 overflow-hidden rounded-full bg-ink/10">
                <motion.span
                  className={cn("block h-full rounded-full", pw >= 3 ? "bg-success" : "bg-accent")}
                  initial={false}
                  animate={{ scaleX: pw > i ? 1 : 0 }}
                  style={{ originX: 0 }}
                  transition={{ duration: 0.4, ease: EASE }}
                />
              </span>
            ))}
          </div>
        </div>

        <p id="signup-error" role="alert" className={cn("min-h-5 text-sm text-danger", !error && "sr-only")}>
          {error ?? ""}
        </p>

        <button type="submit" disabled={busy} className="btn-primary group w-full">
          <TextRoll text={busy ? "Creating your account…" : "Create account"} />
          <SwapArrow />
        </button>
      </form>
      <p className="text-center text-sm text-ink-muted">
        Already have an account?{" "}
        <Link href={next ? `/signin?next=${encodeURIComponent(next)}` : "/signin"} className="font-medium text-ink underline decoration-accent decoration-2 underline-offset-4 hover:text-accent">
          Sign in
        </Link>
      </p>
    </div>
  );
}
