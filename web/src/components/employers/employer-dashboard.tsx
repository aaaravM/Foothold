"use client";

import * as React from "react";
import { toast } from "sonner";
import { useAccount } from "@/components/auth/auth-provider";
import { MonoLabel } from "@/components/foothold/mono-label";
import { FictionalTag } from "@/components/foothold/fictional-tag";
import { cn } from "@/lib/utils";
import { Fairness, GapReportView } from "./insights";
import { PostJob } from "./post-job";
import { Requests } from "./requests";
import { AccountGate, fmtTime, Chip, EmptyNote, ErrorNote, Panel, pct, usePolling } from "./shared";
import { Talent } from "./talent";
import type { FairnessResponse, GapReport, PostingSummary, RequestsResponse, TalentResponse } from "./types";

const SECTIONS = [
  { id: "postings", label: "Postings" },
  { id: "talent", label: "Talent" },
  { id: "requests", label: "Requests" },
  { id: "fairness", label: "Fairness" },
  { id: "gap", label: "Gap report" },
] as const;

export function EmployerDashboard() {
  return (
    <AccountGate kind="employer">
      <Dashboard />
    </AccountGate>
  );
}

function Dashboard() {
  const { account } = useAccount();
  const [postingId, setPostingId] = React.useState("");
  const postings = usePolling<{ postings: PostingSummary[] }>("/api/employer/postings", 0);
  const talent = usePolling<TalentResponse>(`/api/employer/talent?limit=12${postingId ? `&posting_id=${encodeURIComponent(postingId)}` : ""}`, 0);
  const requests = usePolling<RequestsResponse>("/api/employer/requests", 4000);
  const fairness = usePolling<FairnessResponse>("/api/employer/fairness", 0);
  const gap = usePolling<GapReport>("/api/employer/gap-report", 0);

  const { refresh: refreshPostings } = postings;
  const { refresh: refreshTalent } = talent;
  const { refresh: refreshFairness } = fairness;
  const { refresh: refreshGap } = gap;
  const { refresh: refreshRequests } = requests;

  const onPosted = React.useCallback((newId?: string) => {
    if (newId) setPostingId(newId);
    void refreshPostings();
    void refreshTalent();
    void refreshFairness();
    void refreshGap();
    void refreshRequests();
  }, [refreshPostings, refreshTalent, refreshFairness, refreshGap, refreshRequests]);

  const onRequested = React.useCallback(() => {
    void refreshRequests();
    void refreshTalent();
  }, [refreshRequests, refreshTalent]);

  // Toast when a learner accepts or declines in another tab.
  const seen = React.useRef<Map<string, string> | null>(null);
  React.useEffect(() => {
    const list = requests.data?.requests;
    if (!list) return;
    const prev = seen.current;
    const next = new Map(list.map((r) => [r.id, r.status]));
    if (prev) {
      let changed = false;
      for (const r of list) {
        const before = prev.get(r.id);
        if (before === "pending" && r.status !== "pending") {
          changed = true;
          if (r.status === "accepted") toast.success(`A candidate accepted${r.posting_title ? ` for ${r.posting_title}` : ""}. Contact details unlocked.`);
          else toast(`A candidate declined${r.posting_title ? ` for ${r.posting_title}` : ""}.`);
        }
      }
      if (changed) void refreshTalent();
    }
    seen.current = next;
  }, [requests.data, refreshTalent]);

  const counts = requests.data?.counts;
  const postingList = postings.data?.postings ?? [];
  const kpis: { label: string; value: string; sub: string }[] = [
    { label: "Postings", value: postings.data ? String(postingList.length) : "…", sub: "parsed into skills profiles" },
    { label: "Talent pool", value: talent.data ? String(talent.data.pool_size) : "…", sub: "blind synthetic cards" },
    { label: "Pending", value: counts ? String(counts.pending) : "…", sub: "awaiting the learner" },
    { label: "Accepted", value: counts ? String(counts.accepted) : "…", sub: counts ? `acceptance rate ${counts.acceptance_rate === null ? "n/a" : pct(counts.acceptance_rate)}` : "consented contacts" },
  ];

  return (
    <div className="grid gap-6 lg:grid-cols-[11rem_minmax(0,1fr)]">
      <nav aria-label="Employer sections" className="lg:sticky lg:top-24 lg:self-start">
        <MonoLabel as="p" className="mb-2 hidden lg:block">
          {account?.org ?? account?.display_name}
        </MonoLabel>
        <ul className="flex gap-1 overflow-x-auto pb-1 lg:grid lg:gap-0.5 lg:overflow-visible">
          {SECTIONS.map((s, i) => (
            <li key={s.id}>
              <a
                href={`#${s.id}`}
                className="flex h-9 items-center gap-2 border border-transparent px-2 text-sm whitespace-nowrap text-ink-muted hover:border-line hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
              >
                <span className="font-mono text-xs text-ink-faint">{String(i + 1).padStart(2, "0")}</span>
                {s.label}
                {s.id === "requests" && counts?.pending ? <span className="ml-auto font-mono text-xs text-warning">{counts.pending}</span> : null}
              </a>
            </li>
          ))}
        </ul>
        <div className="mt-3 hidden lg:block">
          <FictionalTag />
        </div>
      </nav>

      <div className="grid min-w-0 gap-6">
        <dl className="grid grid-cols-2 gap-px border border-line bg-line md:grid-cols-4">
          {kpis.map((k) => (
            <div key={k.label} className="grid gap-1 bg-surface p-4">
              <dt>
                <MonoLabel>{k.label}</MonoLabel>
              </dt>
              <dd className="font-mono text-3xl text-ink tabular-nums">{k.value}</dd>
              <dd className="text-xs text-ink-muted">{k.sub}</dd>
            </div>
          ))}
        </dl>

        <Panel id="postings" label="01 · Postings" title="Post a job">
          <PostJob onChanged={onPosted} />
          <div className="mt-6 grid gap-2 border-t border-line pt-4">
            <MonoLabel as="p">Your postings</MonoLabel>
            {postings.error ? <ErrorNote>{postings.error}</ErrorNote> : null}
            {postings.data && !postingList.length ? <EmptyNote>No postings yet.</EmptyNote> : null}
            <ul className="grid gap-2">
              {postingList.map((p) => (
                <li key={p.id} className={cn("grid gap-2 border p-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start", p.id === postingId ? "border-accent" : "border-line")}>
                  <div className="grid gap-1.5">
                    <p className="font-medium text-ink">
                      {p.title} <span className="font-mono text-xs text-ink-faint">· {fmtTime(p.created_at)}</span>
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {p.skills.slice(0, 8).map((s) => (
                        <Chip key={s.skill_id} tone={s.importance === "required" ? "accent" : "plain"}>
                          {s.name}
                        </Chip>
                      ))}
                      {p.injection?.attempt ? <Chip tone="warning">injection filtered</Chip> : null}
                    </div>
                  </div>
                  <a
                    href="#talent"
                    onClick={() => setPostingId(p.id)}
                    className="text-sm text-accent underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-accent"
                  >
                    Rank talent for this
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </Panel>

        <Panel id="talent" label="02 · Talent" title="Blind talent cards">
          <Talent
            postings={postingList}
            postingId={postingId}
            onPostingChange={setPostingId}
            talent={talent.data}
            error={talent.error}
            loading={talent.loading}
            onRequested={onRequested}
          />
        </Panel>

        <Panel id="requests" label="03 · Requests" title="Consent requests" aside={<FictionalTag />}>
          <Requests requests={requests.data?.requests ?? null} error={requests.error} />
        </Panel>

        <Panel id="fairness" label="04 · Fairness" title="Shortlist audit">
          <Fairness data={fairness.data} error={fairness.error} />
        </Panel>

        <Panel id="gap" label="05 · Gap report" title="Skill gaps across postings">
          <GapReportView data={gap.data} error={gap.error} />
        </Panel>
      </div>
    </div>
  );
}
