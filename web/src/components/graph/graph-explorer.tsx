"use client";

import * as React from "react";
import Link from "next/link";
import { Minus, Plus, RotateCcw } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { cn } from "@/lib/utils";
import { getJSON, isApiError, isOfflineError } from "@/lib/api";
import { useAccount } from "@/components/auth/auth-provider";
import { QuietLabel as MonoLabel } from "@/components/sim/fx";
import { NotTrainedYet } from "@/components/foothold/metric-value";
import { useApiResource } from "@/components/lab/use-api";
import { asBlock, isFraction, readRecommender, type RecModel } from "@/components/lab/metrics";
import { fmtValue } from "@/components/lab/charts";

interface GNode {
  id: string;
  type: string;
  label: string;
  x: number;
  y: number;
  degree?: number;
  learner_id?: string;
  persona?: boolean;
  skills?: number;
}
interface GLink {
  source: string;
  target: string;
  type?: string;
}
interface Sample {
  available: boolean;
  reason?: string;
  nodes: GNode[];
  links: GLink[];
  stats?: Record<string, number>;
  layout?: string;
  source?: string;
}
interface PathStep {
  type: string;
  id: string;
  label: string | null;
}
interface RecItem {
  kind: string;
  id: string;
  title: string | null;
  score: number;
  base_score: number;
  demand_boost: { added: number; skills: string[]; label: string } | null;
  path: PathStep[];
  provider?: string | null;
  url?: string | null;
  cost_usd?: number | null;
}
interface RecResponse {
  learner_id: string;
  model_requested: string;
  model_used: string;
  trained: boolean;
  note: string | null;
  items: RecItem[];
}

const MODELS: { id: RecModel; label: string }[] = [
  { id: "gnn", label: "GNN" },
  { id: "mf", label: "MF" },
  { id: "pop", label: "Popularity" },
];

const TYPE_STYLE: Record<string, { cls: string; label: string; r: number }> = {
  learner: { cls: "fill-ink-muted stroke-ink-muted", label: "Learner", r: 3 },
  career: { cls: "fill-accent stroke-accent", label: "Target career", r: 7 },
  neighborhood: { cls: "fill-bg stroke-ink-muted", label: "Neighborhood", r: 6 },
  skill: { cls: "fill-info stroke-info", label: "Skill", r: 5 },
  course: { cls: "fill-success stroke-success", label: "Course", r: 5 },
  job: { cls: "fill-warning stroke-warning", label: "Job", r: 6 },
};
const styleOf = (t: string) => TYPE_STYLE[t] ?? { cls: "fill-ink-muted stroke-ink-muted", label: t, r: 5 };

const W = 900;
const H = 620;
const PAD = 40;

export function GraphExplorer() {
  const { account } = useAccount();
  const sample = useApiResource<Sample>("/api/graph/sample", { pollMs: 0 });
  const metrics = useApiResource<Record<string, unknown>>("/api/metrics");
  const rec = readRecommender(asBlock(metrics.data?.recommender));

  const [model, setModel] = React.useState<RecModel>("gnn");
  const [selected, setSelected] = React.useState<string | null>(null); // learner_id or "me"
  const [hover, setHover] = React.useState<string | null>(null);
  const [view, setView] = React.useState<"map" | "list">("map");
  const [fetched, setFetched] = React.useState<{ key: string; data?: RecResponse; error?: string } | null>(null);
  const [active, setActive] = React.useState<{ key: string; i: number } | null>(null);
  const reqKey = selected ? `${selected}|${model}` : null;
  const result: { state: "idle" | "loading" | "ready" | "error"; data?: RecResponse; error?: string } = !reqKey
    ? { state: "idle" }
    : fetched?.key !== reqKey
      ? { state: "loading" }
      : fetched.error
        ? { state: "error", error: fetched.error }
        : { state: "ready", data: fetched.data };
  const activeItem = active && active.key === reqKey ? active.i : 0;
  const setActiveItem = (i: number) => reqKey && setActive({ key: reqKey, i });

  const youId = account?.kind === "learner" ? account.persona_id : null;
  const data = sample.data;
  const nodes = React.useMemo(() => (data?.available ? data.nodes : []), [data]);
  const byId = React.useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  // layout -> svg coords
  const pos = React.useMemo(() => {
    if (!nodes.length) return new Map<string, [number, number]>();
    const xs = nodes.map((n) => n.x);
    const ys = nodes.map((n) => n.y);
    const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const sx = (x: number) => PAD + ((x - minX) / Math.max(1e-9, maxX - minX)) * (W - 2 * PAD);
    const sy = (y: number) => PAD + ((y - minY) / Math.max(1e-9, maxY - minY)) * (H - 2 * PAD);
    return new Map(nodes.map((n) => [n.id, [sx(n.x), sy(n.y)] as [number, number]]));
  }, [nodes]);

  // fetch recommendations
  React.useEffect(() => {
    if (!selected) return;
    const key = `${selected}|${model}`;
    const ctrl = new AbortController();
    getJSON<RecResponse>(`/api/graph/recommend/${encodeURIComponent(selected)}?model=${model}&k=10`, { signal: ctrl.signal, timeoutMs: 20_000 })
      .then((d) => setFetched({ key, data: d }))
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return;
        const msg = isOfflineError(err) ? "API offline." : isApiError(err) ? `${err.status}: ${err.message}` : "Could not load recommendations.";
        setFetched({ key, error: msg });
      });
    return () => ctrl.abort();
  }, [selected, model]);

  const selectedNodeId = React.useMemo(() => {
    const lid = selected === "me" ? youId : selected;
    return nodes.find((n) => n.type === "learner" && n.learner_id === lid)?.id ?? null;
  }, [selected, youId, nodes]);

  // explanation path highlight: nodes on the active item's path that exist in the sample
  const highlight = React.useMemo(() => {
    const ids = new Set<string>();
    if (selectedNodeId) ids.add(selectedNodeId);
    const item = result.data?.items[activeItem];
    item?.path.forEach((p) => {
      const nid = `${p.type}:${p.id}`;
      if (byId.has(nid)) ids.add(nid);
    });
    return ids;
  }, [result.data, activeItem, selectedNodeId, byId]);

  // pan / zoom
  const [vb, setVb] = React.useState({ x: 0, y: 0, w: W, h: H });
  const svgRef = React.useRef<SVGSVGElement>(null);
  const drag = React.useRef<{ px: number; py: number; vx: number; vy: number } | null>(null);
  const zoom = (f: number, cx = vb.x + vb.w / 2, cy = vb.y + vb.h / 2) =>
    setVb((v) => {
      const w = Math.min(W * 2, Math.max(W / 6, v.w * f));
      const h = (w / W) * H;
      return { x: cx - ((cx - v.x) * w) / v.w, y: cy - ((cy - v.y) * h) / v.h, w, h };
    });
  React.useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      setVb((v) => {
        const cx = v.x + ((e.clientX - r.left) / r.width) * v.w;
        const cy = v.y + ((e.clientY - r.top) / r.height) * v.h;
        const w = Math.min(W * 2, Math.max(W / 6, v.w * (e.deltaY > 0 ? 1.12 : 0.89)));
        const h = (w / W) * H;
        return { x: cx - ((cx - v.x) * w) / v.w, y: cy - ((cy - v.y) * h) / v.h, w, h };
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [view, nodes.length]);

  const learners = nodes.filter((n) => n.type === "learner");
  const types = Array.from(new Set(nodes.map((n) => n.type)));
  const hovered = hover ? byId.get(hover) : null;
  const reduce = useReducedMotion();
  // neighbours of the hovered node, so hovering lights up its local web
  const near = React.useMemo(() => {
    if (!hover || !data) return null;
    const ids = new Set<string>([hover]);
    data.links.forEach((l) => {
      if (l.source === hover) ids.add(l.target);
      if (l.target === hover) ids.add(l.source);
    });
    return ids;
  }, [hover, data]);
  const labelFor = (n: GNode) => (youId && n.learner_id === youId ? "You" : n.label);
  const pct = isFraction([rec.value("gnn", "recall", "overall")?.value, rec.value("mf", "recall", "overall")?.value]);

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
      <div className="space-y-4 lg:col-span-8">
        <div className="flex flex-wrap items-center gap-3">
          <div role="group" aria-label="View" className="inline-flex overflow-hidden rounded-full border border-line p-0.5">
            {(["map", "list"] as const).map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                onClick={() => setView(v)}
                className={cn("text-[13px] h-7 rounded-full px-3 transition-colors focus-visible:outline-2 focus-visible:outline-accent", view === v ? "bg-ink text-bg" : "text-ink-muted hover:text-ink")}
              >
                {v === "map" ? "Graph" : "List"}
              </button>
            ))}
          </div>
          {view === "map" && nodes.length ? (
            <div className="inline-flex gap-1">
              {[
                { icon: Plus, label: "Zoom in", on: () => zoom(0.8) },
                { icon: Minus, label: "Zoom out", on: () => zoom(1.25) },
                { icon: RotateCcw, label: "Reset view", on: () => setVb({ x: 0, y: 0, w: W, h: H }) },
              ].map(({ icon: Icon, label, on }) => (
                <button key={label} type="button" aria-label={label} onClick={on} className="inline-flex size-8 items-center justify-center rounded-full border border-line transition-colors hover:border-line-strong text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent">
                  <Icon aria-hidden="true" className="size-3.5" />
                </button>
              ))}
            </div>
          ) : null}
          {youId ? (
            <button
              type="button"
              onClick={() => setSelected("me")}
              className="text-[13px] h-8 border border-accent px-3 text-ink hover:bg-accent/10 focus-visible:outline-2 focus-visible:outline-accent rounded-full"
            >
              My recommendations
            </button>
          ) : null}
        </div>

        {sample.state === "loading" ? (
          <p className="text-[13px] text-ink-faint">Reading the learner graph…</p>
        ) : sample.state === "offline" ? (
          <p role="status" className="border border-warning/50 px-4 py-3 text-sm text-warning">API offline: the graph is read live from the Foothold API.</p>
        ) : !data?.available ? (
          <div className="space-y-3 border border-dashed border-line-strong p-6 rounded-2xl">
            <MonoLabel as="p">Graph not built yet</MonoLabel>
            <p className="text-sm text-ink-muted">{data?.reason ?? "The learner sample is not available."} Recommendations for your own account still work below.</p>
          </div>
        ) : view === "map" ? (
          <div className="relative overflow-hidden rounded-2xl border border-line bg-[radial-gradient(ellipse_at_50%_40%,color-mix(in_oklab,var(--accent)_7%,transparent),transparent_65%)]">
            <svg
              ref={svgRef}
              viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
              className="h-auto w-full cursor-grab touch-none select-none active:cursor-grabbing"
              role="img"
              aria-label={`Learner graph: ${learners.length} learners and ${nodes.length - learners.length} other nodes. Use the List view to browse with a keyboard.`}
              onPointerDown={(e) => {
                drag.current = { px: e.clientX, py: e.clientY, vx: vb.x, vy: vb.y };
                (e.currentTarget as SVGSVGElement).setPointerCapture(e.pointerId);
              }}
              onPointerMove={(e) => {
                const d = drag.current;
                const el = svgRef.current;
                if (!d || !el) return;
                const r = el.getBoundingClientRect();
                setVb((v) => ({ ...v, x: d.vx - ((e.clientX - d.px) / r.width) * v.w, y: d.vy - ((e.clientY - d.py) / r.height) * v.h }));
              }}
              onPointerUp={() => (drag.current = null)}
            >
              <g>
                {data.links.map((l, i) => {
                  const a = pos.get(l.source);
                  const b = pos.get(l.target);
                  if (!a || !b) return null;
                  const on = highlight.has(l.source) && highlight.has(l.target);
                  const lit = !!near && (l.source === hover || l.target === hover);
                  return (
                    <motion.line
                      key={i}
                      x1={a[0]}
                      y1={a[1]}
                      x2={b[0]}
                      y2={b[1]}
                      className={cn("transition-[stroke,opacity] duration-300", on ? "stroke-accent" : lit ? "stroke-ink-muted" : "stroke-line")}
                      strokeWidth={on ? 2.5 : lit ? 1.5 : 1}
                      style={{ opacity: near && !lit && !on ? 0.35 : 1 }}
                      initial={reduce ? false : { pathLength: 0 }}
                      animate={{ pathLength: 1 }}
                      transition={{ duration: 0.9, delay: 0.25 + (i % 40) * 0.012, ease: [0.16, 1, 0.3, 1] }}
                    />
                  );
                })}
              </g>
              <g>
                {nodes.map((n) => {
                  const p = pos.get(n.id);
                  if (!p) return null;
                  const s = styleOf(n.type);
                  const isYou = !!youId && n.learner_id === youId;
                  const on = highlight.has(n.id);
                  const clickable = n.type === "learner";
                  const dim = !!near && !near.has(n.id) && !on && !isYou;
                  const showLabel = isYou || on || n.type === "career" || (!!near && near.has(n.id) && n.type !== "learner") || hover === n.id;
                  return (
                    <g
                      key={n.id}
                      transform={`translate(${p[0]},${p[1]})`}
                      style={{ opacity: dim ? 0.3 : 1, transition: "opacity 300ms" }}
                      onPointerEnter={() => setHover(n.id)}
                      onPointerLeave={() => setHover((h) => (h === n.id ? null : h))}
                      onPointerDown={(e) => clickable && e.stopPropagation()}
                      onClick={() => clickable && n.learner_id && setSelected(n.learner_id)}
                      className={clickable ? "cursor-pointer" : undefined}
                    >
                      {on || isYou ? <circle r={s.r + 5} className="fill-none stroke-accent" strokeWidth={1.5} /> : null}
                      <motion.g
                        initial={reduce ? false : { scale: 0, opacity: 0 }}
                        animate={{ scale: hover === n.id ? 1.35 : 1, opacity: 1 }}
                        transition={{ type: "spring", stiffness: 260, damping: 20, delay: reduce ? 0 : hover ? 0 : Math.min(0.9, (p[0] / W) * 0.6 + (n.type === "career" ? 0.3 : 0)) }}
                      >
                        {n.type === "career" ? (
                          <rect x={-s.r} y={-s.r} width={s.r * 2} height={s.r * 2} rx={2} className={s.cls} strokeWidth={1} />
                        ) : (
                          <circle r={isYou ? s.r + 3 : clickable ? s.r + 1 : s.r} className={isYou ? "fill-accent stroke-accent" : s.cls} strokeWidth={1} />
                        )}
                        {/* generous invisible hit area for small learner dots */}
                        {clickable ? <circle r={10} className="fill-transparent" /> : null}
                      </motion.g>
                      {showLabel ? (
                        <text
                          x={s.r + 6}
                          y={3.5}
                          className={cn("pointer-events-none", isYou || on || n.type === "career" ? "fill-ink" : "fill-ink-muted")}
                          style={{ fontSize: n.type === "career" ? 11 : 10, paintOrder: "stroke", stroke: "var(--bg)", strokeWidth: 3, strokeLinejoin: "round" }}
                        >
                          {labelFor(n)}
                        </text>
                      ) : null}
                    </g>
                  );
                })}
              </g>
            </svg>
            {hovered ? (
              <div className="pointer-events-none absolute top-3 left-3 rounded-xl border border-line bg-bg/90 px-3 py-2 backdrop-blur">
                <MonoLabel as="p" tone="faint">
                  {styleOf(hovered.type).label}
                </MonoLabel>
                <p className="text-sm text-ink">{labelFor(hovered)}</p>
                {hovered.type === "learner" ? <p className="text-xs text-ink-muted">{hovered.skills ?? 0} skills · click for recommendations</p> : null}
              </div>
            ) : null}
            <div className="flex flex-wrap gap-x-4 gap-y-1 border-t border-line px-3 py-2">
              {types.map((t) => (
                <span key={t} className="text-[13px] inline-flex items-center gap-1.5 text-ink-muted">
                  <svg width="12" height="12" aria-hidden="true">
                    {t === "career" ? <rect x="2" y="2" width="8" height="8" className={styleOf(t).cls} /> : <circle cx="6" cy="6" r="4" className={styleOf(t).cls} />}
                  </svg>
                  {styleOf(t).label}
                  {data.stats?.[t] !== undefined ? ` (${data.stats[t]})` : ""}
                </span>
              ))}
              <span className="text-[13px] ml-auto text-ink-faint">Drag to pan, scroll to zoom, click a dot</span>
            </div>
          </div>
        ) : (
          <ul className="max-h-[560px] divide-y divide-line overflow-y-auto rounded-2xl border border-line" aria-label="Learners">
            {learners.map((n) => (
              <li key={n.id}>
                <button
                  type="button"
                  aria-pressed={selected === n.learner_id}
                  onClick={() => n.learner_id && setSelected(n.learner_id)}
                  className={cn("flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-ink/5 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent", selected === n.learner_id && "bg-accent/10")}
                >
                  <span className="text-sm text-ink">{labelFor(n)}</span>
                  <span className="text-[13px] text-ink-faint">{n.skills ?? 0} skills</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <aside className="space-y-6 lg:col-span-4" aria-live="polite">
        <div className="space-y-3">
          <MonoLabel as="h2">Model</MonoLabel>
          <div role="radiogroup" aria-label="Recommender model" className="grid grid-cols-3 overflow-hidden rounded-full border border-line p-0.5">
            {MODELS.map((mo) => (
              <button
                key={mo.id}
                type="button"
                role="radio"
                aria-checked={model === mo.id}
                onClick={() => setModel(mo.id)}
                className={cn("text-[13px] h-8 rounded-full transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent", model === mo.id ? "bg-ink text-bg" : "text-ink-muted hover:text-ink")}
              >
                {mo.label}
              </button>
            ))}
          </div>
          <dl className="grid grid-cols-2 gap-3">
            {(["recall", "ndcg"] as const).map((k) => {
              const p = rec.value(model, k, "overall");
              return (
                <div key={k} className="rounded-xl border border-line px-3 py-2">
                  <dt className="text-[13px] text-ink-faint">{k === "recall" ? "Recall@10" : "NDCG@10"}</dt>
                  <dd className="font-mono text-lg text-ink tabular-nums">{p ? fmtValue(p.value, pct) : <NotTrainedYet className="text-xs" />}</dd>
                </div>
              );
            })}
          </dl>
          <Link href="/lab#recommender" className="text-[13px] text-ink-muted underline decoration-line-strong underline-offset-4 hover:text-ink">
            How these are measured →
          </Link>
        </div>

        <div className="space-y-3 border-t border-line pt-5">
          <MonoLabel as="h2">Recommendations</MonoLabel>
          {result.state === "idle" ? (
            <p className="text-sm text-ink-muted">{youId ? "Pick yourself or any learner in the graph." : "Click a learner in the graph (or use the List view)."}</p>
          ) : result.state === "loading" ? (
            <p className="text-[13px] text-ink-faint">Ranking…</p>
          ) : result.state === "error" ? (
            <p role="alert" className="text-sm text-danger">{result.error}</p>
          ) : result.data ? (
            <>
              <p className="text-sm text-ink-muted">
                For <span className="text-ink">{result.data.learner_id === youId ? "You" : result.data.learner_id}</span> · model used{" "}
                <span className="font-mono text-ink">{result.data.model_used}</span>
              </p>
              {!result.data.trained ? (
                <p className="border-l-2 border-warning pl-3 text-xs text-ink-muted">
                  The trained {model.toUpperCase()} model is not available yet{result.data.note ? ` (${result.data.note})` : ""}, so this list comes from the transparent skill-gap baseline.
                </p>
              ) : null}
              {result.data.items.length === 0 ? <p className="text-sm text-ink-muted">No recommendations for this learner.</p> : null}
              <ol className="space-y-2">
                {result.data.items.map((it, i) => (
                  <li key={`${it.kind}-${it.id}`}>
                    <button
                      type="button"
                      aria-pressed={activeItem === i}
                      onClick={() => setActiveItem(i)}
                      className={cn("w-full border px-3 py-2.5 text-left transition-colors focus-visible:outline-2 focus-visible:outline-accent", activeItem === i ? "border-accent" : "border-line hover:border-line-strong")}
                    >
                      <span className="flex items-baseline justify-between gap-2">
                        <span className="text-sm text-ink">{it.title ?? it.id}</span>
                        <span className="text-[13px] shrink-0 text-ink-faint">{it.kind}</span>
                      </span>
                      <span className="mt-1 block font-mono text-[11px] text-ink-muted tabular-nums">
                        score {it.score.toFixed(3)}
                        {it.demand_boost ? ` (base ${it.base_score.toFixed(3)} + demand ${it.demand_boost.added.toFixed(2)})` : ""}
                        {it.cost_usd !== undefined && it.cost_usd !== null ? ` · $${it.cost_usd.toLocaleString("en-US")}` : ""}
                      </span>
                      {activeItem === i && it.path.length ? (
                        <span className="mt-2 block text-xs text-ink-muted">
                          <span className="text-[13px] text-accent">Why · </span>
                          {it.path.map((p) => (p.type === "learner" && (p.id === youId || selected === "me") ? "You" : p.label ?? p.id)).join(" → ")}
                        </span>
                      ) : null}
                      {activeItem === i && it.demand_boost ? <span className="mt-1 block text-xs text-ink-faint">{it.demand_boost.label}</span> : null}
                    </button>
                    {activeItem === i && it.url ? (
                      <a href={it.url} target="_blank" rel="noreferrer" className="text-[13px] mt-1 inline-block text-ink-muted underline underline-offset-4 hover:text-ink">
                        {it.provider ?? "Course page"} ↗
                      </a>
                    ) : null}
                  </li>
                ))}
              </ol>
            </>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
