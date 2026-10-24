import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthShell } from "@/components/auth/auth-shell";
import { SignUpForm } from "./signup-form";

export const metadata: Metadata = { title: "Create your account" };

export default function SignUpPage() {
  return (
    <AuthShell
      title="Start with one shift."
      accent={[2, 3]}
      lead="Free. Takes a minute."
      aside={
        <ul className="space-y-4 text-[15px] text-ink-muted">
          <li className="flex gap-3">
            <span aria-hidden="true" className="mt-2 size-1.5 shrink-0 rounded-full bg-accent" />
            Try eight Valley careers.
          </li>
          <li className="flex gap-3">
            <span aria-hidden="true" className="mt-2 size-1.5 shrink-0 rounded-full bg-accent" />
            Plans that fit your week.
          </li>
          <li className="flex gap-3">
            <span aria-hidden="true" className="mt-2 size-1.5 shrink-0 rounded-full bg-accent" />
            You control who sees you.
          </li>
        </ul>
      }
    >
      <Suspense fallback={<p className="text-sm text-ink-muted">Loading…</p>}>
        <SignUpForm />
      </Suspense>
    </AuthShell>
  );
}
