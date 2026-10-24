"use client";

import * as React from "react";
import { Heart, MessageSquare, Phone } from "lucide-react";

export interface CrisisPayload {
  crisis: true;
  message?: string;
  lifeline?: string;
  emergency?: string;
  resources?: { id: string; label: string; href: string }[];
  source?: { label: string; url: string; es_url?: string; retrieved?: string; status?: string };
  note?: string;
}

/** Calm, prominent 988 panel. Statements only; focus moves here so screen readers announce it. */
export function CrisisPanel({ payload }: { payload: CrisisPayload | null }) {
  const ref = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    ref.current?.focus();
  }, []);
  const resources = payload?.resources?.length
    ? payload.resources
    : [
        { id: "call_988", label: "Call 988", href: "tel:988" },
        { id: "text_988", label: "Text 988", href: "sms:988" },
        { id: "call_911", label: "Call 911 if you're in immediate danger", href: "tel:911" },
      ];
  return (
    <div
      ref={ref}
      tabIndex={-1}
      role="alert"
      aria-labelledby="crisis-h"
      className="grid gap-4 border-2 border-info bg-surface p-5 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-info"
    >
      <p id="crisis-h" className="flex items-center gap-2 text-lg font-semibold text-ink">
        <Heart aria-hidden="true" className="size-5 text-info" /> You don&apos;t have to go through this alone.
      </p>
      <p className="text-ink">
        {payload?.lifeline ??
          "Call or text 988 to reach the 988 Suicide & Crisis Lifeline. It's free and available 24/7. You can also reach out to someone you trust."}
      </p>
      <ul className="flex flex-wrap gap-2">
        {resources.map((r) => (
          <li key={r.id}>
            <a
              href={r.href}
              target={r.href.startsWith("http") ? "_blank" : undefined}
              rel={r.href.startsWith("http") ? "noreferrer" : undefined}
              className={
                r.id === "call_988"
                  ? "inline-flex h-11 items-center gap-2 bg-info px-4 font-medium text-bg hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-info"
                  : "inline-flex h-11 items-center gap-2 border border-line-strong px-4 text-ink hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-info"
              }
            >
              {r.id.startsWith("text") || r.id.startsWith("chat") ? <MessageSquare aria-hidden="true" className="size-4" /> : <Phone aria-hidden="true" className="size-4" />}
              {r.label}
            </a>
          </li>
        ))}
      </ul>
      <p className="text-sm text-ink-muted">{payload?.emergency ?? "If you're in immediate danger, call 911."}</p>
      {payload?.note ? <p className="text-sm text-ink-muted">{payload.note}</p> : null}
      {payload?.source ? (
        <p className="text-xs text-ink-faint">
          Source:{" "}
          <a href={payload.source.url} target="_blank" rel="noreferrer" className="underline underline-offset-4 hover:text-ink">
            {payload.source.label}
          </a>
          {payload.source.retrieved ? ` · retrieved ${payload.source.retrieved}` : ""}
        </p>
      ) : null}
    </div>
  );
}
