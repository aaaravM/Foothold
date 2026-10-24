"use client";

import * as React from "react";
import { TracePanel } from "@/components/foothold/trace-panel";
import { useTrace } from "@/components/foothold/use-trace";
import { MonoLabel } from "@/components/foothold/mono-label";
import { cn } from "@/lib/utils";
import { ErrorNote, inputClass, primaryButtonClass } from "@/components/employers/shared";
import { CrisisPanel, type CrisisPayload } from "./crisis-panel";

interface Turn {
  role: "you" | "coach";
  text: string;
}

function newSessionId(): string {
  return `s${Math.random().toString(36).slice(2, 12)}`;
}

export function CoachPanel() {
  const trace = useTrace();
  const { state } = trace;
  const [sessionId] = React.useState(newSessionId);
  const [text, setText] = React.useState("");
  const [memory, setMemory] = React.useState(false);
  const [turns, setTurns] = React.useState<Turn[]>([]);
  const abortRef = React.useRef<AbortController | null>(null);
  React.useEffect(() => () => abortRef.current?.abort(), []);

  const busy = state.status === "connecting" || state.status === "running";

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const msg = text.trim();
    if (!msg || busy) return;
    setTurns([...shown, { role: "you", text: msg }]);
    setText("");
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    trace.reset();
    await trace.run(
      "/api/circle/coach",
      { session_id: sessionId, text: msg, mode: "listening", memory_opt_in: memory },
      ctrl.signal,
    );
  }

  // The latest run's outcome, derived from the trace (no effect needed).
  const finished = state.status === "done";
  const result = (state.result ?? {}) as Record<string, unknown>;
  const data = state.data as Record<string, unknown>;
  const crisis: CrisisPayload | null =
    finished && (result.crisis === true || data.crisis === true)
      ? (((result.crisis ? result : data.crisis_payload) ?? { crisis: true }) as CrisisPayload)
      : null;
  const reply = finished && !crisis ? (typeof result.reply === "string" && result.reply) || (typeof data.reply === "string" && data.reply) || "" : "";
  const shown: Turn[] = reply ? [...turns, { role: "coach", text: reply }] : turns;

  return (
    <div className="grid gap-4">
      <p className="border-l-2 border-info pl-3 text-sm text-ink-muted">
        Peer support and practice, not therapy. The coach listens and reflects back; it doesn&apos;t diagnose or give medical or legal advice.
      </p>
      {crisis ? <CrisisPanel payload={crisis} /> : null}
      <ol className="grid max-h-80 gap-2 overflow-y-auto" aria-live="polite" aria-label="Conversation">
        {shown.map((t, i) => (
          <li
            key={i}
            className={cn("max-w-[85%] border px-3 py-2 text-sm", t.role === "you" ? "justify-self-end border-line-strong bg-surface-2 text-ink" : "border-line bg-bg text-ink")}
          >
            <span className="label-mono mb-1 block text-ink-faint">{t.role === "you" ? "You" : "Coach"}</span>
            {t.text}
          </li>
        ))}
        {busy ? (
          <li className="text-sm text-ink-muted" aria-live="polite">
            Coach is thinking…
          </li>
        ) : null}
      </ol>
      <form onSubmit={send} className="grid gap-2">
        <label htmlFor="coach-text" className="text-sm font-medium text-ink">
          Talk it through
        </label>
        <textarea
          id="coach-text"
          className={cn(inputClass, "min-h-20")}
          value={text}
          maxLength={1500}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. I'm nervous about asking my lead for different shifts so I can take a class."
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="flex items-center gap-2 text-sm text-ink-muted">
            <input type="checkbox" className="size-4 accent-[var(--color-accent)]" checked={memory} onChange={(e) => setMemory(e.target.checked)} />
            Remember this session (opt-in)
          </label>
          <button type="submit" className={primaryButtonClass} disabled={busy || !text.trim()}>
            {busy ? "Listening…" : "Send"}
          </button>
        </div>
      </form>
      {state.error ? <ErrorNote>{state.error}</ErrorNote> : null}
      {state.status !== "idle" ? <TracePanel nodes={trace.nodes} state={state} title="Coach graph" defaultOpen={false} /> : null}
      <MonoLabel as="p">Session {sessionId} · contact details you type are redacted before anything is stored</MonoLabel>
    </div>
  );
}
