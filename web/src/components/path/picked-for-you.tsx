"use client";

/**
 * "Picked for you": 3 courses + 2 jobs from the GNN recommender
 * (GET /api/graph/recommend/me?model=gnn), each with one plain-language reason
 * built from its explanation path. Falls back to the persona id for demo accounts.
 */
import * as React from "react";
import { motion, useReducedMotion } from "motion/react";
import { getJSON } from "@/lib/api";
import { cn } from "@/lib/utils";
import { EASE, QuietLabel } from "@/components/sim/fx";

interface PathStep {
  type: string;
  id: string;
  label: string | null;
  edge?: string | null;
}
interface RecItem {
  kind: string;
  id: string;
  title: string | null;
  provider?: string | null;
  url?: string | null;
  cost_usd?: number | null;
  path?: PathStep[];
  why?: string | null;
}
interface RecResponse {
  items: RecItem[];
}

const clip = (s: string, n = 30) => (s.length > n ? `${s.slice(0, n - 1).trimEnd()}…` : s);

/** One short reason from the explanation path. */
export function reasonFor(item: RecItem): string {
  const steps = item.path ?? [];
  const at = steps.findIndex((s) => s.id === item.id);
  const after = at >= 0 ? steps.slice(at + 1) : steps;
  const before = at >= 0 ? steps.slice(0, at) : [];
  const label = (s?: PathStep) => (s?.label ? clip(s.label) : null);
  if (item.kind === "course") {
    const taught = label(after.find((s) => s.type === "skill"));
    const job = label(after.find((s) => s.type === "job"));
    if (taught && job) return `Builds ${taught} → used by ${job}`;
    if (taught) return `Builds ${taught}`;
    const have = label(before.find((s) => s.type === "skill"));
    return have ? `Builds on your ${have}` : "Fits your skills";
  }
  const m = item.why?.match(/(\d+) of (\d+)/);
  const gap = label(after.find((s) => s.type === "skill"));
  const have = label(before.find((s) => s.type === "skill"));
  if (m && gap) return `${m[1]} of ${m[2]} skills · next: ${gap}`;
  if (have) return `Uses your ${have}`;
  return "Close to your skills";
}

function useRecs(personaId?: string | null) {
  const [items, setItems] = React.useState<RecItem[] | null>(null);
  const [failed, setFailed] = React.useState(false);
  React.useEffect(() => {
    const ctrl = new AbortController();
    const opts = { signal: ctrl.signal, timeoutMs: 20_000 };
    getJSON<RecResponse>("/api/graph/recommend/me?model=gnn&k=10", opts)
      .catch((err) => {
        if (ctrl.signal.aborted || !personaId) throw err;
        return getJSON<RecResponse>(`/api/graph/recommend/${encodeURIComponent(personaId)}?model=gnn&k=10`, opts);
      })
      .then((r) => {
        const courses = r.items.filter((i) => i.kind === "course").slice(0, 3);
        const jobs = r.items.filter((i) => i.kind === "job").slice(0, 2);
        setItems([...courses, ...jobs]);
      })
      .catch(() => {
        if (!ctrl.signal.aborted) setFailed(true);
      });
    return () => ctrl.abort();
  }, [personaId]);
  return { items, failed };
}

export function PickedForYou({ personaId, className }: { personaId?: string | null; className?: string }) {
  const { items, failed } = useRecs(personaId);
  const reduce = useReducedMotion();
  if (failed || (items && items.length === 0)) return null;
  return (
    <section aria-label="Picked for you" className={cn("space-y-3", className)}>
      <h2 className="font-display text-xl text-ink">Picked for you</h2>
      {!items ? (
        <QuietLabel as="p">Finding matches…</QuietLabel>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {items.map((it, i) => {
            const meta = [it.provider, typeof it.cost_usd === "number" ? (it.cost_usd === 0 ? "Free" : `$${Math.round(it.cost_usd).toLocaleString("en-US")}`) : null]
              .filter(Boolean)
              .join(" · ");
            const body = (
              <>
                <QuietLabel tone={it.kind === "job" ? "accent" : "muted"}>{it.kind === "job" ? "Job" : "Course"}</QuietLabel>
                <p className="mt-1 line-clamp-2 text-sm font-medium text-ink">{it.title ?? it.id}</p>
                {meta ? <QuietLabel as="p" className="line-clamp-1">{meta}</QuietLabel> : null}
                <p className="mt-2 text-[13px] leading-5 text-ink-muted">{reasonFor(it)}</p>
              </>
            );
            return (
              <motion.li
                key={`${it.kind}-${it.id}`}
                initial={reduce ? { opacity: 0 } : { opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, ease: EASE, delay: i * 0.08 }}
                className="rounded-2xl border border-line p-4 transition-colors hover:border-line-strong"
              >
                {it.url ? (
                  <a href={it.url} target="_blank" rel="noreferrer" className="block focus-visible:outline-2 focus-visible:outline-accent">
                    {body}
                  </a>
                ) : (
                  body
                )}
              </motion.li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
