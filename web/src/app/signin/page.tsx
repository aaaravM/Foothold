import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthShell } from "@/components/auth/auth-shell";
import { SignInForm } from "./signin-form";

export const metadata: Metadata = { title: "Sign in" };

export default function SignInPage() {
  return (
    <AuthShell title="Welcome back." accent={[1]} lead="Pick up your workday, your path and your circle right where you left them.">
      <Suspense fallback={<p className="text-sm text-ink-muted">Loading…</p>}>
        <SignInForm />
      </Suspense>
    </AuthShell>
  );
}
