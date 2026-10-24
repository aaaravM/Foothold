"use client";

import * as React from "react";
import { ShieldAlert } from "lucide-react";
import { TracePanel } from "@/components/foothold/trace-panel";
import { useTrace } from "@/components/foothold/use-trace";
import { QuietLabel as MonoLabel } from "@/components/sim/fx";
import { cn } from "@/lib/utils";
import {
  BlindFields,
  Chip,
  EmptyNote,
  ErrorNote,
  inputClass,
  pct,
  primaryButtonClass,
  secondaryButtonClass,
} from "./shared";
import type { InjectionInfo, PickInterrupt, PostingProfile, SimVariant, TalentCard } from "./types";

const SAMPLE_TITLE = "Diesel Technician Apprentice";
const SAMPLE_TEXT =
  "Tri-Valley Freight is hiring a diesel technician apprentice for our Stockton truck yard. You will help our lead mechanic " +
  "diagnose diesel engines, service hydraulic lift gates, do preventive maintenance on our fleet, and troubleshoot electrical faults. " +
  "Basic MIG welding for bracket repairs is a plus. Part-time after school or full-time in summer; we pay for your ASE certification.";

export function PostJob({ onChanged }: { onChanged: (postingId?: string) => void }) {
  const trace = useTrace();
  const { state } = trace;
  const [title, setTitle] = React.useState("");
  const [text, setText] = React.useState("");
  const [minHours, setMinHours] = React.useState("");
  const [picked, setPicked] = React.useState<string[]>([]);
  const [message, setMessage] = React.useState("");
  const abortRef = React.useRef<AbortController | null>(null);

  React.useEffect(() => () => abortRef.current?.abort(), []);

  const data = state.data as {
    posting_id?: string;
    profile?: PostingProfile | null;
    injection?: InjectionInfo | null;
    sim_variant?: SimVariant | null;
    shortlist?: TalentCard[] | null;
    pool?: { pool_size: number; eligible: number; shortlisted: number } | null;
    requests?: { id: string; candidate_id: string; status: string }[] | null;
  };
  const busy = state.status === "connecting" || state.status === "running";
  const pick = state.status === "interrupted" && state.interrupt ? (state.interrupt.payload as PickInterrupt) : null;

  const newPostingId = data.posting_id;
  const lastStatus = React.useRef(state.status);
  React.useEffect(() => {
    const prev = lastStatus.current;
    lastStatus.current = state.status;
    if (prev !== state.status && (state.status === "interrupted" || state.status === "done")) onChanged(newPostingId);
    if (state.status === "interrupted" && prev !== "interrupted" && pick) {
      setMessage((m) => m || pick.message_template);
      setPicked([]);
    }
  }, [state.status, pick, onChanged, newPostingId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim() || busy) return;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    trace.reset();
    const hours = Number.parseInt(minHours, 10);
    await trace.run(
      "/api/employer/postings",
      { title: title.trim(), text: text.trim(), ...(hours > 0 && hours <= 80 ? { min_hours: hours } : {}) },
      ctrl.signal,
    );
  }

  async function sendPicks() {
    if (!state.threadId || busy) return;
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    await trace.run(`/api/employer/postings/${state.threadId}/contact`, { candidate_ids: picked, message: message.trim() || undefined }, ctrl.signal);
  }

  const profile = data.profile ?? null;
  const injection = data.injection ?? null;
  const variant = data.sim_variant ?? null;
  const shortlist = data.shortlist ?? [];

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <form onSubmit={submit} className="grid content-start gap-3">
        <div className="grid gap-1.5">
          <label htmlFor="post-title" className="text-sm font-medium text-ink">
            Job title
          </label>
          <input id="post-title" className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} placeholder="e.g. Warehouse Lead" />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor="post-text" className="text-sm font-medium text-ink">
            Job description
          </label>
          <textarea
            id="post-text"
            className={cn(inputClass, "min-h-44 resize-y leading-relaxed")}
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={8000}
            placeholder="Paste the job posting"
            required
          />
          <MonoLabel as="p">{text.length} / 8000</MonoLabel>
        </div>
        <div className="grid gap-1.5 sm:max-w-48">
          <label htmlFor="post-hours" className="text-sm font-medium text-ink">
            Minimum hours / week <span className="font-normal text-ink-muted">(optional)</span>
          </label>
          <input id="post-hours" inputMode="numeric" className={inputClass} value={minHours} onChange={(e) => setMinHours(e.target.value.replace(/\D/g, "").slice(0, 2))} />
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="submit" className={primaryButtonClass} disabled={busy || !text.trim()}>
            {busy ? "Reading posting…" : "Post job"}
          </button>
          <button
            type="button"
            className={secondaryButtonClass}
            disabled={busy}
            onClick={() => {
              setTitle(SAMPLE_TITLE);
              setText(SAMPLE_TEXT);
              setMinHours("");
            }}
          >
            Fill a sample posting
          </button>
        </div>
        {state.error ? <ErrorNote>{state.error}</ErrorNote> : null}
      </form>

      <div className="grid content-start gap-4">
        {state.status === "idle" ? (
          <EmptyNote>Post a job to see who fits.</EmptyNote>
        ) : (
          <TracePanel nodes={trace.nodes} state={state} title="Behind the scenes" />
        )}

        {injection?.attempt ? (
          <div role="status" className="grid gap-1.5 border border-warning/60 p-3 text-sm">
            <p className="flex items-center gap-2 font-medium text-warning">
              <ShieldAlert aria-hidden="true" className="size-4" /> Instructions found inside the posting
            </p>
            {injection.flag_text.length ? <p className="text-ink">{injection.flag_text.join(" · ")}</p> : null}
            {injection.handling ? <p className="text-ink-muted">{injection.handling}</p> : null}
            {injection.excerpts.map((x, i) => (
              <code key={i} className="block border border-line bg-bg px-2 py-1 font-mono text-xs break-words text-ink-muted">
                {x}
              </code>
            ))}
          </div>
        ) : null}

        {profile ? (
          <div className="grid gap-2 border border-line p-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-medium text-ink">{profile.role_title}</p>
              <MonoLabel>
                {[profile.career_title, profile.shift !== "unspecified" ? `${profile.shift} shift` : null, profile.min_hours_per_week ? `${profile.min_hours_per_week}+ h/wk` : null]
                  .filter(Boolean)
                  .join(" · ")}
              </MonoLabel>
            </div>
            {profile.summary ? <p className="text-sm text-ink-muted">{profile.summary}</p> : null}
            <MonoLabel as="p">Generated skills profile</MonoLabel>
            <ul className="flex flex-wrap gap-1.5" aria-label="Skills profile">
              {profile.skills.map((s) => (
                <li key={s.skill_id}>
                  <Chip tone={s.importance === "required" ? "accent" : "plain"} title={s.evidence ? `From the posting: "${s.evidence}"` : undefined}>
                    {s.name}
                    <span className="text-ink-faint">· {s.importance}</span>
                  </Chip>
                </li>
              ))}
              {!profile.skills.length ? <li className="text-sm text-ink-muted">No known skills found in this posting.</li> : null}
            </ul>
          </div>
        ) : null}

        {variant ? (
          <details className="group border border-line p-3" open>
            <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-2 focus-visible:outline-2 focus-visible:outline-accent">
              <span className="font-medium text-ink">Sim variant preview</span>
              <span className="text-[13px] border border-warning/60 px-2 py-0.5 text-warning">Needs human review</span>
            </summary>
            <div className="mt-3 grid gap-3">
              <MonoLabel as="p">Setting: {variant.setting}</MonoLabel>
              {variant.events.slice(0, 3).map((ev) => (
                <div key={ev.event_id} className="border-l-2 border-line-strong pl-3">
                  <p className="text-sm font-medium text-ink">
                    {ev.clock ? <span className="mr-2 font-mono text-ink-faint">{ev.clock}</span> : null}
                    {ev.title}
                  </p>
                  <p className="text-sm text-ink-muted">{ev.text}</p>
                </div>
              ))}
              {variant.note ? <p className="text-xs text-ink-faint">{variant.note}</p> : null}
            </div>
          </details>
        ) : null}

        {pick ? (
          <div className="grid gap-3 border border-accent/60 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-medium text-ink">Pick who to contact</p>
            </div>
            <p className="text-sm text-ink-muted">{pick.prompt}</p>
            {data.pool ? (
              <MonoLabel as="p">
                {data.pool.shortlisted} shortlisted of {data.pool.eligible} eligible ({data.pool.pool_size} in the pool)
              </MonoLabel>
            ) : null}
            {shortlist.length ? (
              <ul className="grid gap-2">
                {shortlist.map((c, i) => {
                  const on = picked.includes(c.candidate_id);
                  const id = `pick-${c.candidate_id}`;
                  return (
                    <li key={c.candidate_id} className={cn("border p-3", on ? "border-accent" : "border-line")}>
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <label htmlFor={id} className="flex items-center gap-2 text-sm font-medium text-ink">
                          <input
                            id={id}
                            type="checkbox"
                            className="size-4 accent-[var(--color-accent)]"
                            checked={on}
                            onChange={() => setPicked((p) => (on ? p.filter((x) => x !== c.candidate_id) : [...p, c.candidate_id]))}
                          />
                          Candidate {String(i + 1).padStart(2, "0")}
                        </label>
                        {c.match ? <MonoLabel tone="accent">match {pct(c.match.score)}</MonoLabel> : null}
                      </div>
                      <BlindFields card={c} matched={c.match?.matched} showLocked={false} />
                    </li>
                  );
                })}
              </ul>
            ) : (
              <EmptyNote>No one in the pool matches this posting yet. You can still finish the run.</EmptyNote>
            )}
            <div className="grid gap-1.5">
              <label htmlFor="pick-message" className="text-sm font-medium text-ink">
                Message they will see
              </label>
              <textarea id="pick-message" className={cn(inputClass, "min-h-20")} maxLength={600} value={message} onChange={(e) => setMessage(e.target.value)} />
            </div>
            <button type="button" className={cn(primaryButtonClass, "w-fit")} onClick={sendPicks} disabled={busy}>
              {picked.length ? `Send ${picked.length} consent request${picked.length > 1 ? "s" : ""}` : "Finish without contacting"}
            </button>
          </div>
        ) : null}

        {state.status === "done" && data.requests ? (
          <p role="status" className="border border-success/50 px-3 py-2 text-sm text-ink">
            {data.requests.length
              ? `${data.requests.length} consent request${data.requests.length > 1 ? "s" : ""} sent. They appear under Requests and unlock when the learner accepts.`
              : "Run finished. No one was contacted."}
          </p>
        ) : null}
      </div>
    </div>
  );
}
