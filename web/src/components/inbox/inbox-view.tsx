"use client";

import * as React from "react";
import { toast } from "sonner";
import { Eye, EyeOff, ShieldCheck } from "lucide-react";
import { MonoLabel } from "@/components/foothold/mono-label";
import { FictionalTag } from "@/components/foothold/fictional-tag";
import { postJSON } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  AccountGate,
  BlindFields,
  EmptyNote,
  ErrorNote,
  errorText,
  fmtTime,
  Panel,
  primaryButtonClass,
  secondaryButtonClass,
  StatusPill,
  usePolling,
} from "@/components/employers/shared";
import type { InboxRequest, InboxResponse } from "@/components/employers/types";

export function InboxView() {
  return (
    <AccountGate kind="learner">
      <Inbox />
    </AccountGate>
  );
}

function Inbox() {
  const inbox = usePolling<InboxResponse>("/api/employer/inbox", 4000);
  const { refresh } = inbox;
  const seen = React.useRef<Set<string> | null>(null);

  React.useEffect(() => {
    const list = inbox.data?.requests;
    if (!list) return;
    const prev = seen.current;
    if (prev) {
      const fresh = list.filter((r) => !prev.has(r.id));
      for (const r of fresh) toast(`New request from ${r.employer.name}`, { description: r.posting_title ?? "They'd like to contact you." });
    }
    seen.current = new Set(list.map((r) => r.id));
  }, [inbox.data]);

  const data = inbox.data;
  if (inbox.error && !data) return <ErrorNote>{inbox.error}</ErrorNote>;
  if (!data) return <MonoLabel as="p">Loading your inbox…</MonoLabel>;

  const pending = data.requests.filter((r) => r.status === "pending");
  const decided = data.requests.filter((r) => r.status !== "pending");

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,24rem)]">
      <div className="grid content-start gap-6">
        <Panel
          label="Consent requests"
          title={pending.length ? `${pending.length} waiting for your answer` : "Nothing waiting"}
          aside={<MonoLabel>checks every few seconds</MonoLabel>}
        >
          {!data.card ? (
            <EmptyNote>Your talent card isn&apos;t in the pool yet, so employers can&apos;t find you. It appears once your sim and pathway results are recorded.</EmptyNote>
          ) : pending.length ? (
            <ul className="grid gap-4">
              {pending.map((r) => (
                <RequestItem key={r.id} request={r} shared={data.shared_on_accept} onDecided={refresh} />
              ))}
            </ul>
          ) : (
            <EmptyNote>No new requests. Employers only see your blind card; when one asks to contact you, it shows up here.</EmptyNote>
          )}
        </Panel>

        {decided.length ? (
          <Panel label="History" title="Answered requests">
            <ul className="grid gap-2">
              {decided.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 border border-line p-3 text-sm">
                  <span className="text-ink">
                    {r.employer.name}
                    {r.posting_title ? <span className="text-ink-muted"> · {r.posting_title}</span> : null}
                  </span>
                  <span className="flex items-center gap-2">
                    <MonoLabel>{fmtTime(r.decided_at)}</MonoLabel>
                    <StatusPill status={r.status} />
                  </span>
                </li>
              ))}
            </ul>
          </Panel>
        ) : null}
      </div>

      <aside className="grid content-start gap-4">
        <div className="grid gap-2 border border-line bg-surface p-4">
          <p className="flex items-center gap-2 font-medium text-ink">
            <ShieldCheck aria-hidden="true" className="size-4 text-success" /> You decide who sees you
          </p>
          <p className="text-sm text-ink-muted">
            Accepting shares your contact details with that one employer only. Other employers keep seeing the blind card. Declining tells them no, and your identity stays hidden.
          </p>
        </div>
        {data.card ? (
          <div className="grid gap-3 border border-line bg-surface p-4">
            <div className="flex items-center justify-between gap-2">
              <MonoLabel>What employers always see</MonoLabel>
              <FictionalTag compact />
            </div>
            <BlindFields card={data.card} />
          </div>
        ) : null}
      </aside>
    </div>
  );
}

function RequestItem({ request, shared, onDecided }: { request: InboxRequest; shared: InboxResponse["shared_on_accept"]; onDecided: () => Promise<void> }) {
  const [busy, setBusy] = React.useState<"accept" | "decline" | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const headingId = `req-${request.id}`;

  async function decide(decision: "accept" | "decline") {
    setBusy(decision);
    setError(null);
    try {
      await postJSON(`/api/employer/consent/${encodeURIComponent(request.id)}`, { decision });
      toast.success(decision === "accept" ? `Shared with ${request.employer.name} only.` : `Declined. ${request.employer.name} won't see who you are.`);
      await onDecided();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <li aria-labelledby={headingId} className="grid gap-3 border border-line bg-bg p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="grid gap-0.5">
          <p id={headingId} className="text-lg font-semibold text-ink">
            {request.employer.name}
          </p>
          <MonoLabel>
            {request.posting_title ?? "General outreach"} · {fmtTime(request.created_at)}
          </MonoLabel>
        </div>
        <FictionalTag label="Fictional employer" />
      </div>
      {request.message ? <p className="border-l-2 border-accent pl-3 text-ink">&ldquo;{request.message}&rdquo;</p> : null}
      <div className="grid gap-2 border border-dashed border-line-strong p-3">
        <p className="flex items-center gap-2 text-sm font-medium text-ink">
          <Eye aria-hidden="true" className="size-4" /> If you accept, {request.employer.name} sees exactly:
        </p>
        <dl className="grid gap-1 text-sm sm:grid-cols-[10rem_1fr]">
          {shared.map((s) => (
            <React.Fragment key={s.field}>
              <dt className="text-ink-muted">{s.label}</dt>
              <dd className="font-mono text-ink">{s.value}</dd>
            </React.Fragment>
          ))}
        </dl>
        <p className="flex items-center gap-2 text-xs text-ink-muted">
          <EyeOff aria-hidden="true" className="size-3.5" /> Only this employer sees these details. Nobody else does.
        </p>
      </div>
      {error ? <ErrorNote>{error}</ErrorNote> : null}
      <div className="flex flex-wrap gap-2">
        <button type="button" className={primaryButtonClass} onClick={() => decide("accept")} disabled={busy !== null}>
          {busy === "accept" ? "Sharing…" : "Accept and share"}
        </button>
        <button type="button" className={cn(secondaryButtonClass)} onClick={() => decide("decline")} disabled={busy !== null}>
          {busy === "decline" ? "Declining…" : "Decline"}
        </button>
      </div>
    </li>
  );
}
