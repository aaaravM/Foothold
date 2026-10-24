"use client";

import * as React from "react";
import { toast } from "sonner";
import { Eye, EyeOff, ShieldCheck } from "lucide-react";
import { EASE, QuietLabel as MonoLabel } from "@/components/sim/fx";
import { AnimatePresence, motion } from "motion/react";
import { patchJSON, postJSON } from "@/lib/api";
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
          title={pending.length ? `${pending.length} waiting` : "Nothing waiting"}
        >
          {!data.card ? (
            <OptIn onDone={refresh} />
          ) : pending.length ? (
            <ul className="grid gap-4">
              <AnimatePresence initial={false}>
                {pending.map((r) => (
                  <RequestItem key={r.id} request={r} shared={data.shared_on_accept} onDecided={refresh} />
                ))}
              </AnimatePresence>
            </ul>
          ) : (
            <EmptyNote>No new requests.</EmptyNote>
          )}
        </Panel>

        {decided.length ? (
          <details className="rounded-2xl border border-line p-5">
            <summary className="cursor-pointer text-sm text-ink-muted hover:text-ink">Answered ({decided.length})</summary>
            <ul className="mt-3 grid gap-2">
              {decided.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line p-3 text-sm">
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
          </details>
        ) : null}
      </div>

      <aside className="grid content-start gap-4">
        <div className="grid gap-2 rounded-2xl border border-line p-5">
          <p className="flex items-center gap-2 font-medium text-ink">
            <ShieldCheck aria-hidden="true" className="size-4 text-success" /> You decide who sees you
          </p>
        </div>
        {data.card ? (
          <details className="rounded-2xl border border-line p-5">
            <summary className="cursor-pointer text-sm text-ink-muted hover:text-ink">What employers see</summary>
            <div className="mt-3">
              <BlindFields card={data.card} />
            </div>
          </details>
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
    <motion.li
      layout
      aria-labelledby={headingId}
      initial={{ opacity: 0, y: 16, filter: "blur(6px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      exit={{ opacity: 0, x: 40, transition: { duration: 0.4, ease: EASE } }}
      transition={{ duration: 0.8, ease: EASE }}
      className="grid gap-4 rounded-2xl border border-line bg-bg p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="grid gap-0.5">
          <p id={headingId} className="text-lg font-semibold text-ink">
            {request.employer.name}
          </p>
          <MonoLabel>
            {request.posting_title ?? "General outreach"} · {fmtTime(request.created_at)}
          </MonoLabel>
        </div>
      </div>
      {request.message ? <p className="border-l border-accent pl-3 text-lg text-ink">&ldquo;{request.message}&rdquo;</p> : null}
      <div className="grid gap-2 rounded-xl bg-surface/50 p-4">
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
          <EyeOff aria-hidden="true" className="size-3.5" /> Nobody else sees these.
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
    </motion.li>
  );
}

/** New accounts: one tap puts a blind card in the pool (PATCH profile talent_opt_in). */
function OptIn({ onDone }: { onDone: () => Promise<void> }) {
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);
  return (
    <div className="grid gap-3">
      <p className="text-ink-muted">Turn on your blind card. Your name stays hidden until you say yes.</p>
      {err ? <ErrorNote>{err}</ErrorNote> : null}
      <button
        type="button"
        className={cn(primaryButtonClass, "w-fit")}
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setErr(null);
          try {
            await patchJSON("/api/auth/me/profile", { talent_opt_in: true });
            toast.success("Your blind card is live.");
            await onDone();
          } catch (e) {
            setErr(errorText(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Turning on…" : "Let employers find me"}
      </button>
    </div>
  );
}
