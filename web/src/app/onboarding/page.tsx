import type { Metadata } from "next";
import { Suspense } from "react";
import { Onboarding } from "./onboarding";

export const metadata: Metadata = { title: "Welcome" };

export default function OnboardingPage() {
  return (
    <Suspense fallback={<div className="page-container py-24 text-sm text-ink-muted">Loading…</div>}>
      <Onboarding />
    </Suspense>
  );
}
