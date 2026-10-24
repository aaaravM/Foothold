"use client";

import * as React from "react";
import { toast } from "sonner";
import { useAccount } from "@/components/auth/auth-provider";
import { QuietLabel as MonoLabel, TabBar, TabPanel } from "@/components/sim/fx";
import { cn } from "@/lib/utils";
import { Fairness, GapReportView } from "./insights";
import { PostJob } from "./post-job";
import { Requests } from "./requests";
import { AccountGate, fmtTime, Chip, ErrorNote, usePolling } from "./shared";
import { Talent } from "./talent";
import type { FairnessResponse, GapReport, PostingSummary, RequestsResponse, TalentResponse } from "./types";

type Tab = "post" | "talent" | "requests" | "insights";
const TAB_IDS: readonly Tab[] = ["post", "talent", "requests", "insights"];
const BOX = "rounded-3xl border border-line bg-surface/30 p-5 sm:p-7";

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
  const [maxKm, setMaxKm] = React.useState<number | null>(null);
  const [tab, setTabState] = React.useState<Tab>(() => {
    const h = (typeof window === "undefined" ? "" : window.location.hash.slice(1)) as Tab;
    return TAB_IDS.includes(h) ? h : "post";
  });
  const [insight, setInsight] = React.useState<"fairness" | "gaps">("fairness");
  const setTab = React.useCallback((t: Tab) => {
    setTabState(t);
    try {
      window.history.replaceState(null, "", `#${t}`);
    } catch {
      /* ignore */
    }
  }, []);
  const postings = usePolling<{ postings: PostingSummary[] }>("/api/employer/postings", 0);
  const talent = usePolling<TalentResponse>(`/api/employer/talent?limit=12${postingId ? `&posting_id=${encodeURIComponent(postingId)}` : ""}${maxKm ? `&max_km=${maxKm}` : ""}`, 0);
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
  const tabs = [
    { id: "post", label: "Post a job" },
    { id: "talent", label: "Talent", badge: talent.data ? String(talent.data.pool_size) : undefined },
    { id: "requests", label: "Requests", badge: counts?.pending ? String(counts.pending) : undefined },
    { id: "insights", label: "Insights" },
  ] as const;

  return (
    <div className="grid min-w-0 gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <TabBar tabs={tabs} value={tab} onChange={setTab} label="Employer sections" idBase="emp" />
        <MonoLabel>
          {account?.org ?? account?.display_name}
          {counts ? ` · ${counts.accepted} accepted` : ""}
        </MonoLabel>
      </div>

      <TabPanel idBase="emp" tab={tab} className={BOX}>
        {tab === "post" ? (
          <div className="grid gap-6">
            <PostJob onChanged={onPosted} />
            {postings.error ? <ErrorNote>{postings.error}</ErrorNote> : null}
            {postingList.length ? (
              <details className="border-t border-line pt-4">
                <summary className="cursor-pointer text-sm text-ink-muted hover:text-ink">Your postings ({postingList.length})</summary>
                <ul className="mt-3 grid gap-2">
                  {postingList.map((p) => (
                    <li key={p.id} className={cn("grid gap-2 rounded-2xl border p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start", p.id === postingId ? "border-accent" : "border-line")}>
                      <div className="grid gap-1.5">
                        <p className="font-medium text-ink">
                          {p.title} <span className="font-mono text-xs text-ink-faint">· {fmtTime(p.created_at)}</span>
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {p.skills.slice(0, 6).map((s) => (
                            <Chip key={s.skill_id} tone={s.importance === "required" ? "accent" : "plain"}>
                              {s.name}
                            </Chip>
                          ))}
                          {p.injection?.attempt ? <Chip tone="warning">injection filtered</Chip> : null}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setPostingId(p.id);
                          setTab("talent");
                        }}
                        className="text-left text-sm text-accent underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-accent"
                      >
                        Rank talent
                      </button>
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </div>
        ) : null}

        {tab === "talent" ? (
          <Talent
            postings={postingList}
            postingId={postingId}
            onPostingChange={setPostingId}
            talent={talent.data}
            error={talent.error}
            loading={talent.loading}
            onRequested={onRequested}
            maxKm={maxKm}
            onMaxKm={setMaxKm}
          />
        ) : null}

        {tab === "requests" ? <Requests requests={requests.data?.requests ?? null} error={requests.error} /> : null}

        {tab === "insights" ? (
          <div className="grid gap-6">
            <div className="flex gap-2" role="group" aria-label="Insight">
              {(["fairness", "gaps"] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  aria-pressed={insight === k}
                  onClick={() => setInsight(k)}
                  className={cn(
                    "h-8 rounded-full border px-3 text-sm transition-colors",
                    insight === k ? "border-accent text-ink" : "border-line text-ink-muted hover:text-ink",
                  )}
                >
                  {k === "fairness" ? "Fairness" : "Skill gaps"}
                </button>
              ))}
            </div>
            {insight === "fairness" ? <Fairness data={fairness.data} error={fairness.error} /> : <GapReportView data={gap.data} error={gap.error} />}
          </div>
        ) : null}
      </TabPanel>
    </div>
  );
}
