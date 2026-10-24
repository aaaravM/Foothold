"use client";

import * as React from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Lock, LockOpen, Mail, MapPin, Phone } from "lucide-react";
import { QuietLabel as MonoLabel, ScrambleText } from "@/components/sim/fx";
import { getJSON } from "@/lib/api";
import { BlindFields, EmptyNote, ErrorNote, errorText, fmtTime, StatusPill } from "./shared";
import type { CandidateResponse, EmployerRequest, Revealed } from "./types";

const EASE = [0.16, 1, 0.3, 1] as const;

export function Requests({ requests, error }: { requests: EmployerRequest[] | null; error: string | null }) {
  if (error && !requests) return <ErrorNote>{error}</ErrorNote>;
  if (!requests) return <MonoLabel as="p">Loading requests…</MonoLabel>;
  if (!requests.length) return <EmptyNote>No requests yet.</EmptyNote>;
  return (
    <div className="grid gap-3">
      <ul className="grid gap-3 md:grid-cols-2">
        {requests.map((r) => (
          <RequestCard key={r.id} request={r} />
        ))}
      </ul>
    </div>
  );
}

function RequestCard({ request }: { request: EmployerRequest }) {
  const reduce = useReducedMotion();
  const accepted = request.status === "accepted";
  const [contact, setContact] = React.useState<Revealed | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  const [firstStatus] = React.useState(request.status);
  const justUnlocked = accepted && firstStatus !== "accepted";

  React.useEffect(() => {
    if (!accepted) return;
    let live = true;
    getJSON<CandidateResponse>(`/api/employer/candidates/${encodeURIComponent(request.candidate_id)}`)
      .then((res) => {
        if (live) setContact(res.revealed);
      })
      .catch((e: unknown) => {
        if (live) setErr(errorText(e));
      });
    return () => {
      live = false;
    };
  }, [accepted, request.candidate_id]);

  const revealed = contact ?? (accepted ? request.revealed : null);

  return (
    <li className="grid content-start gap-3 rounded-2xl border border-line bg-bg p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="grid gap-0.5">
          <p className="text-sm font-medium text-ink">{request.posting_title ?? "General outreach"}</p>
          <MonoLabel>sent {fmtTime(request.created_at)}{request.decided_at ? ` · decided ${fmtTime(request.decided_at)}` : ""}</MonoLabel>
        </div>
        <StatusPill status={request.status} />
      </div>
      {request.message ? <p className="border-l border-line-strong pl-3 text-sm text-ink-muted">&ldquo;{request.message}&rdquo;</p> : null}

      <AnimatePresence initial={false} mode="wait">
        {revealed ? (
          <motion.div
            key="open"
            className="relative grid gap-2 overflow-hidden rounded-2xl border border-accent/50 bg-accent-wash p-4"
            initial={reduce || !justUnlocked ? false : { opacity: 0, scale: 0.96, clipPath: "inset(0 100% 0 0 round 16px)" }}
            animate={{ opacity: 1, scale: 1, clipPath: "inset(0 0% 0 0 round 16px)" }}
            transition={{ duration: 0.9, ease: EASE }}
          >
            {justUnlocked && !reduce ? (
              <>
                <motion.span
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-0 rounded-2xl"
                  initial={{ boxShadow: "0 0 0 0 color-mix(in oklab, var(--accent) 55%, transparent)" }}
                  animate={{ boxShadow: "0 0 0 18px color-mix(in oklab, var(--accent) 0%, transparent)" }}
                  transition={{ duration: 1.4, ease: "easeOut", repeat: 2 }}
                />
                <motion.span
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-y-0 -left-1/3 w-1/3 -skew-x-12 bg-gradient-to-r from-transparent via-accent/25 to-transparent"
                  initial={{ x: "0%" }}
                  animate={{ x: "450%" }}
                  transition={{ duration: 1.3, ease: EASE, delay: 0.3 }}
                />
              </>
            ) : null}
            <div className="flex items-center justify-between gap-2">
              <p className="flex items-center gap-2 text-sm font-medium text-accent">
                <motion.span
                  className="inline-flex"
                  initial={justUnlocked && !reduce ? { rotate: -25, scale: 0.6 } : false}
                  animate={{ rotate: 0, scale: 1 }}
                  transition={{ type: "spring", stiffness: 260, damping: 12, delay: 0.2 }}
                >
                  <LockOpen aria-hidden="true" className="size-4" />
                </motion.span>
                Unlocked with consent
              </p>
            </div>
            <p className="font-display text-2xl text-ink">
              {justUnlocked ? <ScrambleText text={revealed.name ?? "Name not provided"} duration={1100} /> : revealed.name ?? "Name not provided"}
            </p>
            <ul className="grid gap-1 text-sm text-ink">
              {revealed.contact.email ? (
                <li className="flex items-center gap-2">
                  <Mail aria-hidden="true" className="size-4 text-ink-faint" />
                  <a className="underline underline-offset-4 hover:text-accent" href={`mailto:${revealed.contact.email}`}>
                    {revealed.contact.email}
                  </a>
                </li>
              ) : null}
              {revealed.contact.phone ? (
                <li className="flex items-center gap-2">
                  <Phone aria-hidden="true" className="size-4 text-ink-faint" /> {revealed.contact.phone}
                </li>
              ) : null}
              {revealed.exact_location ? (
                <li className="flex items-center gap-2">
                  <MapPin aria-hidden="true" className="size-4 text-ink-faint" /> {revealed.exact_location}
                </li>
              ) : null}
            </ul>
          </motion.div>
        ) : (
          <motion.p key="locked" exit={reduce ? undefined : { opacity: 0 }} className="flex items-center gap-2 text-sm text-ink-muted">
            <Lock aria-hidden="true" className="size-4" />
            {request.status === "declined" ? "The learner declined. Their identity stays hidden." : "Name and contact stay hidden until the learner accepts."}
          </motion.p>
        )}
      </AnimatePresence>
      {err ? <ErrorNote>{err}</ErrorNote> : null}
      {request.card ? (
        <details className="border-t border-line pt-2">
          <summary className="cursor-pointer text-sm text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent">Blind card</summary>
          <div className="mt-2">
            <BlindFields card={request.card} showLocked={!revealed} />
          </div>
        </details>
      ) : null}
    </li>
  );
}
