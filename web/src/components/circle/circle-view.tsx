"use client";

import * as React from "react";
import { toast } from "sonner";
import { Clock3, Users } from "lucide-react";
import { useAccount } from "@/components/auth/auth-provider";
import { QuietLabel as MonoLabel, TabBar, TabPanel } from "@/components/sim/fx";
import { postJSON } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  AccountGate,
  EmptyNote,
  ErrorNote,
  errorText,
  fmtTime,
  inputClass,
  Panel,
  primaryButtonClass,
  usePolling,
} from "@/components/employers/shared";
import { CoachPanel } from "./coach-panel";
import { CrisisPanel, type CrisisPayload } from "./crisis-panel";
import { EqPractice } from "./eq-practice";

interface Circle {
  id: string;
  name: string;
  topic?: string;
  description?: string;
  post_count: number;
  member_count?: number;
}
interface Post {
  id: string;
  handle: string;
  text: string;
  status: "approved" | "held";
  created_at: string | null;
  seed: boolean;
  mine: boolean;
  reasons?: string[];
  note?: string | null;
}
interface CreatePostResponse {
  post: Post;
  moderation: { status: string; reasons: string[]; note: string | null };
  crisis: boolean;
  crisis_payload: CrisisPayload | null;
}

type CircleTab = "circles" | "coach" | "practice";
const TABS = [
  { id: "circles", label: "Circles" },
  { id: "coach", label: "Coach" },
  { id: "practice", label: "Practice" },
] as const;
const BOX = "rounded-3xl border border-line bg-surface/30 p-5 sm:p-7";

export function CircleView() {
  return (
    <AccountGate kind="learner">
      <CircleSheet />
    </AccountGate>
  );
}

function joinedKey(accountId: string | undefined) {
  return `foothold.circles.${accountId ?? "anon"}`;
}

function CircleSheet() {
  const { account } = useAccount();
  const circles = usePolling<{ circles: Circle[]; fallback: boolean }>("/api/circle/circles", 0);
  const [joined, setJoined] = React.useState<string[]>(() => {
    try {
      const raw = window.localStorage.getItem(joinedKey(account?.id));
      const parsed: unknown = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === "string") : [];
    } catch {
      return []; // storage unavailable: join state lives for this page view only
    }
  });
  const [active, setActive] = React.useState<string | null>(null);
  const [tab, setTab] = React.useState<CircleTab>("circles");

  const toggleJoin = (id: string) => {
    setJoined((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id];
      try {
        window.localStorage.setItem(joinedKey(account?.id), JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
  };

  const list = circles.data?.circles ?? [];
  const activeId = active ?? joined.find((j) => list.some((c) => c.id === j)) ?? list[0]?.id ?? null;
  const activeCircle = list.find((c) => c.id === activeId) ?? null;

  return (
    <div className="grid gap-6">
      <TabBar tabs={TABS} value={tab} onChange={setTab} label="Circle sections" idBase="circle" />

      <TabPanel idBase="circle" tab={tab}>
        {tab === "circles" ? (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
            <div className="grid content-start gap-2">
              {circles.error && !circles.data ? <ErrorNote>{circles.error}</ErrorNote> : null}
              {!circles.data && !circles.error ? <MonoLabel as="p">Loading circles…</MonoLabel> : null}
              <ul className="grid gap-2">
                {list.map((c) => {
                  const isJoined = joined.includes(c.id);
                  const isActive = c.id === activeId;
                  return (
                    <li key={c.id}>
                      <button
                        type="button"
                        aria-current={isActive ? "true" : undefined}
                        onClick={() => setActive(c.id)}
                        className={cn(
                          "grid w-full gap-1 rounded-2xl border p-4 text-left transition-colors duration-300 focus-visible:outline-2 focus-visible:outline-accent",
                          isActive ? "border-accent/70 bg-accent-wash" : "border-line hover:border-line-strong",
                        )}
                      >
                        <span className="font-medium text-ink">{c.name}</span>
                        <span className="flex items-center gap-3 text-xs text-ink-faint">
                          {typeof c.member_count === "number" ? (
                            <span className="flex items-center gap-1">
                              <Users aria-hidden="true" className="size-3.5" /> {c.member_count}
                            </span>
                          ) : null}
                          <span>{c.post_count} posts</span>
                          {isJoined ? <span className="text-accent">Joined</span> : null}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
            {activeCircle ? <Thread key={activeCircle.id} circle={activeCircle} joined={joined.includes(activeCircle.id)} onJoin={() => toggleJoin(activeCircle.id)} /> : <div />}
          </div>
        ) : null}
        {tab === "coach" ? (
          <div className={BOX}>
            <CoachPanel />
          </div>
        ) : null}
        {tab === "practice" ? (
          <div className={BOX}>
            <EqPractice />
          </div>
        ) : null}
      </TabPanel>
    </div>
  );
}

function Thread({ circle, joined, onJoin }: { circle: Circle; joined: boolean; onJoin: () => void }) {
  const posts = usePolling<{ posts: Post[] }>(`/api/circle/${encodeURIComponent(circle.id)}/posts`, 8000);
  const [text, setText] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [crisis, setCrisis] = React.useState<CrisisPayload | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim() || busy) return;
    setBusy(true);
    setError(null);
    setCrisis(null);
    try {
      const res = await postJSON<CreatePostResponse>(`/api/circle/${encodeURIComponent(circle.id)}/posts`, { text: text.trim() }, { timeoutMs: 30_000 });
      setText("");
      if (res.crisis) setCrisis(res.crisis_payload ?? { crisis: true });
      else if (res.moderation.status === "held") toast("Your post is held for review. Only you can see it for now.");
      else toast.success("Posted to the circle.");
      await posts.refresh();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  const list = posts.data?.posts ?? [];
  return (
    <Panel label="Thread" title={circle.name}>
      <div className="grid gap-4">
        {crisis ? <CrisisPanel payload={crisis} /> : null}
        {joined ? (
          <form onSubmit={submit} className="grid gap-2">
            <label htmlFor="post-text-circle" className="text-sm font-medium text-ink">
              Share with the circle
            </label>
            <textarea
              id="post-text-circle"
              className={cn(inputClass, "min-h-20")}
              value={text}
              maxLength={1000}
              onChange={(e) => setText(e.target.value)}
              placeholder="What's on your mind?"
            />
            <button type="submit" className={cn(primaryButtonClass, "w-fit")} disabled={busy || !text.trim()}>
              {busy ? "Checking your post…" : "Post"}
            </button>
            {error ? <ErrorNote>{error}</ErrorNote> : null}
          </form>
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-3 border border-dashed border-line-strong p-3 rounded-2xl">
            <p className="text-sm text-ink-muted">Join to post.</p>
            <button type="button" className={cn(primaryButtonClass, "h-9")} onClick={onJoin}>
              Join circle
            </button>
          </div>
        )}
        {posts.error && !posts.data ? <ErrorNote>{posts.error}</ErrorNote> : null}
        {posts.data && !list.length ? <EmptyNote>No posts yet.</EmptyNote> : null}
        <ul className="grid gap-2">
          {list.map((p) => (
            <li key={p.id} className={cn("grid gap-1 rounded-2xl p-4", p.status === "held" ? "border border-dashed border-warning/60" : "bg-surface/50")}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium text-ink">
                  {p.handle}
                  {p.mine ? <span className="font-normal text-ink-muted"> (you)</span> : null}
                </p>
                <span className="flex items-center gap-2">
                  {p.created_at ? <MonoLabel>{fmtTime(p.created_at)}</MonoLabel> : null}
                  {p.status === "held" ? (
                    <span className="text-[13px] flex items-center gap-1 rounded-full border border-warning/60 px-2 py-0.5 text-warning">
                      <Clock3 aria-hidden="true" className="size-3" /> held
                    </span>
                  ) : null}
                </span>
              </div>
              <p className="text-sm text-ink">{p.text}</p>
              {p.status === "held" && p.note ? <p className="text-xs text-warning">{p.note}</p> : null}
            </li>
          ))}
        </ul>
      </div>
    </Panel>
  );
}
