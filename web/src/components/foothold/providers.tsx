"use client";

import * as React from "react";
import { MotionConfig } from "motion/react";
import { AuthProvider } from "@/components/auth/auth-provider";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeSync, useTheme } from "./theme-toggle";

function ThemedToaster() {
  const { theme } = useTheme();
  return <Toaster theme={theme} position="bottom-right" closeButton />;
}

/**
 * App-wide client providers (rendered once by app/layout.tsx):
 * reduced-motion-aware Motion, tooltips, theme sync, the per-tab account session, toasts.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <MotionConfig reducedMotion="user">
      <TooltipProvider delayDuration={150}>
        <ThemeSync />
        <AuthProvider>
          {children}
          <ThemedToaster />
        </AuthProvider>
      </TooltipProvider>
    </MotionConfig>
  );
}
