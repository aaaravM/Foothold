"use client";

import * as React from "react";
import { toast } from "sonner";
import { motion } from "motion/react";
import { EASE, QuietLabel as MonoLabel, staggerChild, staggerParent } from "@/components/sim/fx";
import { postJSON } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  BlindFields,
  EmptyNote,
  ErrorNote,
  errorText,
  inputClass,
  pct,
  primaryButtonClass,
  secondaryButtonClass,
  StatusPill,
} from "./shared";
import type { EmployerRequest, PostingSummary, TalentCard, TalentResponse } from "./types";

const DEFAULT_MESSAGE = "Hi! We're hiring and your Foothold card matches what we need. Would you be open to a short call about it?";

export function Talent({
  postings,
  postingId,
  onPostingChange,
  talent,
  error,
  loading,
  onRequested,
  maxKm = null,
  onMaxKm,
}: {
  postings: PostingSummary[];
  postingId: string;
  onPostingChange: (id: string) => void;
  talent: TalentResponse | null;
  error: string | null;
  loading: boolean;
  onRequested: () => void;
  maxKm?: number | null;
  onMaxKm?: (km: number | null) => void;
}) {
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="grid gap-1.5">
          <label htmlFor="talent-posting" className="text-sm font-medium text-ink">
            Rank for posting
          </label>
          <select id="talent-posting" className={cn(inputClass, "h-10 w-72 max-w-full py-0")} value={postingId} onChange={(e) => onPostingChange(e.target.value)}>
            <option value="">All candidates (unranked)</option>
            {postings.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
        </div>
        {onMaxKm ? (
          <div className="grid gap-1.5">
            <span className="text-sm font-medium text-ink">
              Distance{talent?.origin?.name ? ` from ${talent.origin.name}` : ""}
            </span>
            <div role="radiogroup" aria-label="Maximum distance" className="flex gap-1 rounded-full border border-line p-1">
              {[null, 25, 50, 100].map((km) => {
                const on = maxKm === km;
                return (
                  <button
                    key={String(km)}
                    type="button"
                    role="radio"
                    aria-checked={on}
                    onClick={() => onMaxKm(km)}
                    className={cn("relative h-8 rounded-full px-3 text-sm transition-colors", on ? "text-accent-ink" : "text-ink-muted hover:text-ink")}
                  >
                    {on ? <motion.span layoutId="talent-km" className="absolute inset-0 rounded-full bg-accent" transition={{ duration: 0.5, ease: EASE }} /> : null}
                    <span className="relative">{km ? `${km} km` : "Any"}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>
      {talent ? (
        <MonoLabel as="p">
          {talent.eligible} eligible of {talent.pool_size} in pool
          {talent.filtered_out ? ` · ${talent.filtered_out} filtered by hours or region` : ""}
          {talent.posting_id ? ` · ranking: skill match ${pct(talent.weights.skill_match)}${talent.recommender.used ? `, recommender ${pct(talent.weights.recommender)}` : ""}` : ""}
        </MonoLabel>
      ) : null}
      {error ? <ErrorNote>{error}</ErrorNote> : null}
      {loading && !talent ? <MonoLabel as="p">Loading blind cards…</MonoLabel> : null}
      {talent && !talent.cards.length ? (
        <EmptyNote>
          {talent.pool_size ? "No candidates pass this posting's filters." : "The talent pool hasn't been generated yet, so there are no cards to show."}
        </EmptyNote>
      ) : null}
      {talent?.cards.length ? (
        <motion.ul key={`${talent.posting_id ?? "all"}-${maxKm ?? "any"}`} className="grid gap-3 md:grid-cols-2" variants={staggerParent(0.05)} initial="hidden" animate="show">
          {talent.cards.map((c, i) => (
            <TalentCardView key={c.candidate_id} card={c} index={i} postingId={talent.posting_id} onRequested={onRequested} />
          ))}
        </motion.ul>
      ) : null}
    </div>
  );
}

function TalentCardView({ card, index, postingId, onRequested }: { card: TalentCard; index: number; postingId: string | null; onRequested: () => void }) {
  const [open, setOpen] = React.useState(false);
  const [message, setMessage] = React.useState(DEFAULT_MESSAGE);
  const [sending, setSending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [localStatus, setLocalStatus] = React.useState<EmployerRequest["status"] | null>(null);
  const status = card.request?.status ?? localStatus;
  const msgId = `msg-${card.candidate_id}`;

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (sending) return;
    setSending(true);
    setError(null);
    try {
      const res = await postJSON<EmployerRequest>("/api/employer/consent-requests", {
        candidate_id: card.candidate_id,
        posting_id: postingId || undefined,
        message: message.trim(),
      });
      setLocalStatus(res.status);
      setOpen(false);
      toast.success(res.duplicate ? "You already have an open request with this candidate." : "Consent request sent. Their name stays hidden until they accept.");
      onRequested();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSending(false);
    }
  }

  return (
    <motion.li variants={staggerChild} className="grid content-start gap-3 rounded-2xl border border-line bg-bg p-5 transition-colors duration-300 hover:border-line-strong">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-sm text-ink">
          Candidate {String(index + 1).padStart(2, "0")} <span className="text-ink-faint">· {card.candidate_id.replace(/^cand_/, "").slice(0, 6)}</span>
        </p>
        <div className="flex items-center gap-2">
          {typeof card.distance_km === "number" ? <MonoLabel>{Math.round(card.distance_km)} km away</MonoLabel> : null}
          {card.match && postingId ? <MonoLabel tone="accent">match {pct(card.match.score)}</MonoLabel> : null}
          {status ? <StatusPill status={status} /> : null}
        </div>
      </div>
      <BlindFields card={card} matched={card.match?.matched} />
      {status ? null : open ? (
        <form onSubmit={send} className="grid gap-2 border-t border-line pt-3">
          <label htmlFor={msgId} className="text-sm font-medium text-ink">
            Message to the candidate
          </label>
          <textarea id={msgId} className={cn(inputClass, "min-h-20")} value={message} maxLength={600} onChange={(e) => setMessage(e.target.value)} required />
          <p className="text-xs text-ink-muted">They see your company, this message and the posting. You see their name and contact only if they accept.</p>
          {error ? <ErrorNote>{error}</ErrorNote> : null}
          <div className="flex flex-wrap gap-2">
            <button type="submit" className={primaryButtonClass} disabled={sending || !message.trim()}>
              {sending ? "Sending…" : "Send request"}
            </button>
            <button type="button" className={secondaryButtonClass} onClick={() => setOpen(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button type="button" className={cn(secondaryButtonClass, "w-fit")} onClick={() => setOpen(true)}>
          Request contact
        </button>
      )}
    </motion.li>
  );
}
