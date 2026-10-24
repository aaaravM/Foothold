"use client";

import * as React from "react";
import { motion, useReducedMotion } from "motion/react";
import { Check, ChevronDown, CircleAlert, Cpu, GitBranch, Hand, Sigma, Sparkles, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { traceProgress, traceRows, type TraceNodeState, type TraceState } from "@/lib/trace";
import type { LlmSource, TraceNode, TraceNodeKind } from "@/lib/types";

export interface TracePanelProps {
  /** graph nodes in order (from the `meta` event); usually `trace.nodes` from useTrace() */
  nodes: readonly TraceNode[];
  /** reduced trace state from useTrace() */
  state: TraceState;
  /** default "Behind the scenes" */
  title?: string;
  /** start expanded (default true) */
  defaultOpen?: boolean;
  className?: string;
}

const KIND_ICON: Record<TraceNodeKind, LucideIcon> = {
  llm: Sparkles,
  model: Cpu,
  solver: Sigma,
  human: Hand,
  logic: GitBranch,
};

const KIND_LABEL: Record<TraceNodeKind, string> = {
  llm: "LLM",
  model: "Model",
  solver: "Solver",
  human: "Human",
  logic: "Logic",
};

const LLM_STYLE: Record<LlmSource, string> = {
  openai: "border-accent/60 text-accent",
  cache: "border-info/60 text-info",
  mock: "border-dashed border-line-strong text-ink-muted",
};

function formatMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(ms >= 10_000 ? 0 : 1)} s`;
  return `${Math.round(ms)} ms`;
}

function PulseDot({ className }: { className?: string }) {
  const reduce = useReducedMotion();
  return (
    <span aria-hidden="true" className={cn("relative inline-flex size-2.5 shrink-0", className)}>
      {!reduce ? (
        <motion.span
          className="absolute inset-0 rounded-full bg-accent"
          initial={{ scale: 1, opacity: 0.55 }}
          animate={{ scale: 2.4, opacity: 0 }}
          transition={{ duration: 1.3, repeat: Infinity, ease: "easeOut" }}
        />
      ) : null}
      <span className="relative inline-flex size-2.5 rounded-full bg-accent" />
    </span>
  );
}

function StatusMark({ status }: { status: TraceNodeState["status"] }) {
  switch (status) {
    case "active":
      return <PulseDot />;
    case "done":
      return <Check aria-hidden="true" className="size-3.5 shrink-0 text-success" />;
    case "waiting":
      return <Hand aria-hidden="true" className="size-3.5 shrink-0 text-accent" />;
    case "error":
      return <CircleAlert aria-hidden="true" className="size-3.5 shrink-0 text-danger" />;
    default:
      return <span aria-hidden="true" className="inline-flex size-2.5 shrink-0 rounded-full border border-line-strong" />;
  }
}

const STATUS_WORD: Record<TraceNodeState["status"], string> = {
  pending: "pending",
  active: "running",
  done: "done",
  waiting: "waiting for you",
  error: "error",
};

function NodeCard({ node, ns }: { node: TraceNode; ns: TraceNodeState | undefined }) {
  const status = ns?.status ?? "pending";
  const Icon = KIND_ICON[node.kind] ?? GitBranch;
  return (
    <div
      className={cn(
        "min-w-0 flex-1 basis-56 rounded-sm border bg-background px-3 py-2 transition-colors",
        status === "pending" && "border-line",
        status === "active" && "border-accent",
        status === "done" && "border-line-strong",
        status === "waiting" && "border-accent bg-accent-wash",
        status === "error" && "border-danger",
      )}
    >
      <div className="flex items-center gap-2">
        <StatusMark status={status} />
        <Icon aria-hidden="true" className={cn("size-3.5 shrink-0", status === "pending" ? "text-ink-faint" : "text-ink-muted")} />
        <span className={cn("min-w-0 flex-1 truncate text-sm", status === "pending" ? "text-ink-muted" : "text-ink")}>{node.label}</span>
        <span className="sr-only">
          {`, ${KIND_LABEL[node.kind] ?? "Logic"} step, ${STATUS_WORD[status]}`}
        </span>
        {typeof ns?.ms === "number" ? (
          <span className="font-mono text-[11px] text-ink-muted tabular-nums">{formatMs(ns.ms)}</span>
        ) : null}
        {ns?.llm ? (
          <span className={cn("label-mono rounded-sm border px-1 leading-4", LLM_STYLE[ns.llm])}>
            <span className="sr-only">LLM source: </span>
            {ns.llm}
          </span>
        ) : null}
      </div>
      {status === "waiting" ? (
        <p className="label-mono mt-1.5 text-accent">Waiting for you</p>
      ) : ns?.summary ? (
        <p className="mt-1.5 text-xs leading-relaxed text-ink-muted">{ns.summary}</p>
      ) : null}
    </div>
  );
}

function rowStatus(row: readonly TraceNode[], state: TraceState): TraceNodeState["status"] {
  const statuses = row.map((n) => state.nodeState[n.id]?.status ?? "pending");
  if (statuses.includes("error")) return "error";
  if (statuses.includes("waiting")) return "waiting";
  if (statuses.includes("active")) return "active";
  if (statuses.every((s) => s === "done")) return "done";
  return "pending";
}

function headline(state: TraceState): { text: string; tone: string } {
  const { done, total } = traceProgress(state);
  switch (state.status) {
    case "connecting":
      return { text: "connecting", tone: "text-ink-muted" };
    case "running":
      return { text: total ? `running · ${done}/${total}` : "running", tone: "text-accent" };
    case "interrupted":
      return { text: "waiting for you", tone: "text-accent" };
    case "done":
      return { text: total ? `done · ${done}/${total}` : "done", tone: "text-success" };
    case "error":
      return { text: "error", tone: "text-danger" };
    default:
      return { text: "idle", tone: "text-ink-faint" };
  }
}

/**
 * "Behind the scenes": the live LangGraph run (CONTRACTS section 6).
 * Nodes in order, parallel groups side by side, the active node pulses, each node shows
 * ms, its LLM source (openai / cache / mock) and a short summary; interrupts read "waiting for you".
 */
export function TracePanel({ nodes, state, title = "Behind the scenes", defaultOpen = true, className }: TracePanelProps) {
  const [open, setOpen] = React.useState(defaultOpen);
  const bodyId = React.useId();
  const rows = React.useMemo(() => traceRows(nodes), [nodes]);
  const head = headline(state);
  const interruptLabel = state.interrupt ? (nodes.find((n) => n.id === state.interrupt?.node)?.label ?? state.interrupt.node) : null;

  const announcement =
    state.status === "interrupted"
      ? `Waiting for you${interruptLabel ? `: ${interruptLabel}` : ""}.`
      : state.status === "done"
        ? "Run finished."
        : state.status === "error"
          ? `Error: ${state.error ?? "something went wrong"}.`
          : state.status === "running" && state.lastSummary
            ? state.lastSummary
            : "";

  return (
    <section className={cn("rounded-sm border border-line bg-surface", className)} aria-label={title}>
      <h2 className="m-0">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={bodyId}
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center gap-3 px-4 py-3 text-left"
        >
          <span className="label-mono text-ink">{title}</span>
          {state.graph ? <span className="label-mono hidden text-ink-faint sm:inline">{state.graph} graph</span> : null}
          <span className={cn("label-mono ml-auto", head.tone)}>{head.text}</span>
          <ChevronDown aria-hidden="true" className={cn("size-4 shrink-0 text-ink-muted transition-transform", open && "rotate-180")} />
        </button>
      </h2>

      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>

      <div id={bodyId} hidden={!open} className="border-t border-line px-4 py-4">
        {rows.length === 0 ? (
          <p className="text-sm text-ink-muted">
            {state.status === "connecting" ? "Connecting to the API…" : "Start a run to see each step of the graph here."}
          </p>
        ) : (
          <ol className="relative ml-1.5 space-y-3 border-l border-line pl-5">
            {rows.map((row) => {
              const rs = rowStatus(row, state);
              const group = row.length > 1 || row[0].group ? row[0].group : undefined;
              return (
                <li key={row.map((n) => n.id).join("|")} className="relative">
                  <span
                    aria-hidden="true"
                    className={cn(
                      "absolute top-3 -left-[25px] size-2 rounded-full border",
                      rs === "done" && "border-success bg-success",
                      rs === "active" && "border-accent bg-accent",
                      rs === "waiting" && "border-accent bg-background",
                      rs === "error" && "border-danger bg-danger",
                      rs === "pending" && "border-line-strong bg-background",
                    )}
                  />
                  {group ? (
                    <p className="label-mono mb-1.5 text-ink-faint">
                      parallel · {group.replace(/_/g, " ")}
                    </p>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    {row.map((node) => (
                      <NodeCard key={node.id} node={node} ns={state.nodeState[node.id]} />
                    ))}
                  </div>
                </li>
              );
            })}
          </ol>
        )}

        {state.status === "interrupted" ? (
          <p className="mt-4 flex items-center gap-2 rounded-sm border border-accent bg-accent-wash px-3 py-2 text-sm text-ink">
            <Hand aria-hidden="true" className="size-4 text-accent" />
            <span>
              <span className="label-mono mr-2 text-accent">Waiting for you</span>
              {interruptLabel}
            </span>
          </p>
        ) : null}

        {state.status === "error" && state.error ? (
          <p role="alert" className="mt-4 flex items-start gap-2 rounded-sm border border-danger px-3 py-2 text-sm text-ink">
            <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-danger" />
            <span>{state.error}</span>
          </p>
        ) : null}
      </div>
    </section>
  );
}
