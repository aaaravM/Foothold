"use client";

import * as React from "react";
import { toast } from "sonner";
import { Clock3, Users } from "lucide-react";
import { useAccount } from "@/components/auth/auth-provider";
import { MonoLabel } from "@/components/foothold/mono-label";
import { FictionalTag } from "@/components/foothold/fictional-tag";
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
  secondaryButtonClass,
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
      <p className="border border-line bg-surface px-4 py-3 text-sm text-ink-muted">
        <span className="font-medium text-ink">Peer support and practice, not therapy.</span> Circles are small groups of people in similar situations. Posts are
        checked for safety and contact details before anyone else sees them. Everyone here is fictional.
      </p>

      <Panel label="Circles" title="Find your people" aside={<FictionalTag />}>
        {circles.error && !circles.data ? <ErrorNote>{circles.error}</ErrorNote> : null}
        {!circles.data && !circles.error ? <MonoLabel as="p">Loading circles…</MonoLabel> : null}
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {list.map((c) => {
            const isJoined = joined.includes(c.id);
            const isActive = c.id === activeId;
            return (
              <li key={c.id} className={cn("grid content-start gap-2 border bg-bg p-4", isActive ? "border-accent" : "border-line")}>
                <p className="font-medium text-ink">{c.name}</p>
                {c.topic ? <MonoLabel>{c.topic}</MonoLabel> : null}
                {c.description ? <p className="text-sm text-ink-muted">{c.description}</p> : null}
                <p className="flex items-center gap-3 text-xs text-ink-faint">
                  <span>{c.post_count} posts</span>
                  {typeof c.member_count === "number" ? (
                    <span className="flex items-center gap-1">
                      <Users aria-hidden="true" className="size-3.5" /> {c.member_count} members
                    </span>
                  ) : null}
                </p>
                <div className="mt-1 flex flex-wrap gap-2">
                  <button type="button" className={cn(isJoined ? secondaryButtonClass : primaryButtonClass, "h-9")} aria-pressed={isJoined} onClick={() => toggleJoin(c.id)}>
                    {isJoined ? "Joined" : "Join"}
                  </button>
                  <button
                    type="button"
                    className={cn(secondaryButtonClass, "h-9")}
                    aria-current={isActive ? "true" : undefined}
                    onClick={() => setActive(c.id)}
                  >
                    {isActive ? "Viewing" : "Open thread"}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      </Panel>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        {activeCircle ? <Thread key={activeCircle.id} circle={activeCircle} joined={joined.includes(activeCircle.id)} onJoin={() => toggleJoin(activeCircle.id)} /> : <div />}
        <div className="grid content-start gap-6">
          <Panel label="Coach" title="Talk something through">
            <CoachPanel />
          </Panel>
          <Panel label="EQ practice" title="Practice a hard conversation">
            <EqPractice />
          </Panel>
        </div>
      </div>
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
    <Panel label="Thread" title={circle.name} aside={<FictionalTag compact />}>
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
              placeholder="What's on your mind? Posts with phone numbers or emails are held for review."
            />
            <button type="submit" className={cn(primaryButtonClass, "w-fit")} disabled={busy || !text.trim()}>
              {busy ? "Checking your post…" : "Post"}
            </button>
            {error ? <ErrorNote>{error}</ErrorNote> : null}
          </form>
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-3 border border-dashed border-line-strong p-3">
            <p className="text-sm text-ink-muted">Join this circle to post. Joining is opt-in and you can leave anytime.</p>
            <button type="button" className={cn(primaryButtonClass, "h-9")} onClick={onJoin}>
              Join circle
            </button>
          </div>
        )}
        {posts.error && !posts.data ? <ErrorNote>{posts.error}</ErrorNote> : null}
        {posts.data && !list.length ? <EmptyNote>No posts yet. Be the first to say hello.</EmptyNote> : null}
        <ul className="grid gap-2">
          {list.map((p) => (
            <li key={p.id} className={cn("grid gap-1 border p-3", p.status === "held" ? "border-dashed border-warning/60" : "border-line")}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium text-ink">
                  {p.handle}
                  {p.mine ? <span className="font-normal text-ink-muted"> (you)</span> : null}
                </p>
                <span className="flex items-center gap-2">
                  {p.created_at ? <MonoLabel>{fmtTime(p.created_at)}</MonoLabel> : null}
                  {p.status === "held" ? (
                    <span className="label-mono flex items-center gap-1 border border-warning/60 px-1.5 py-0.5 text-warning">
                      <Clock3 aria-hidden="true" className="size-3" /> held
                    </span>
                  ) : (
                    <span className="label-mono border border-success/50 px-1.5 py-0.5 text-success">approved</span>
                  )}
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
