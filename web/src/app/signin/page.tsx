import type { Metadata } from "next";
import { Suspense } from "react";
import { MonoLabel } from "@/components/foothold/mono-label";
import { SheetFrame } from "@/components/foothold/sheet-frame";
import { SignInForm } from "./signin-form";

export const metadata: Metadata = { title: "Sign in" };

export default function SignInPage() {
  return (
    <SheetFrame
      sheet="00-A"
      dwg="DWG-000-A"
      code="ACCESS"
      title="Sign in"
      description="One account per browser tab. Signing in here leaves your other tabs as they are."
    >
      <div className="grid gap-10 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <Suspense fallback={<MonoLabel as="p">Loading…</MonoLabel>}>
            <SignInForm />
          </Suspense>
        </div>
        <aside className="hidden border-l border-line pl-8 lg:col-span-4 lg:col-start-8 lg:block" aria-label="What you get">
          <MonoLabel as="p" tone="faint">
            Note 1
          </MonoLabel>
          <p className="mt-2 text-ink-muted">
            Learners try a workday, plan a route with the solver, and decide which employers may see their skills.
          </p>
          <MonoLabel as="p" tone="faint" className="mt-6">
            Note 2
          </MonoLabel>
          <p className="mt-2 text-ink-muted">
            Employers see blind skill cards. Names and contact details stay hidden until the learner says yes.
          </p>
        </aside>
      </div>
    </SheetFrame>
  );
}
