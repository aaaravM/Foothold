"use client";

import * as React from "react";
import { toast } from "sonner";
import { MonoLabel } from "@/components/foothold/mono-label";
import { ProvenanceBadge } from "@/components/foothold/provenance-badge";
import { FictionalTag } from "@/components/foothold/fictional-tag";
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
}: {
  postings: PostingSummary[];
  postingId: string;
  onPostingChange: (id: string) => void;
  talent: TalentResponse | null;
  error: string | null;
  loading: boolean;
  onRequested: () => void;
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
        <div className="flex flex-wrap items-center gap-2">
          <ProvenanceBadge status="SYNTHETIC" note="Synthetic talent pool" />
          <FictionalTag />
        </div>
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
          {talent.pool_size ? "No candidates pass this posting's filters." : "The synthetic talent pool hasn't been generated yet, so there are no cards to show."}
        </EmptyNote>
      ) : null}
      {talent?.cards.length ? (
        <ul className="grid gap-3 md:grid-cols-2">
          {talent.cards.map((c, i) => (
            <TalentCardView key={c.candidate_id} card={c} index={i} postingId={talent.posting_id} onRequested={onRequested} />
          ))}
        </ul>
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
    <li className="grid content-start gap-3 border border-line bg-bg p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-sm text-ink">
          Candidate {String(index + 1).padStart(2, "0")} <span className="text-ink-faint">· {card.candidate_id.replace(/^cand_/, "").slice(0, 6)}</span>
        </p>
        <div className="flex items-center gap-2">
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
    </li>
  );
}
