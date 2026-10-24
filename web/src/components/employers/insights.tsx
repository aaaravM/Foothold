"use client";

import { CheckCircle2, XCircle } from "lucide-react";
import { QuietLabel as MonoLabel } from "@/components/sim/fx";
import { StatBar } from "@/components/foothold/stat-bar";
import { cn } from "@/lib/utils";
import { EmptyNote, ErrorNote, fmtTime, pct } from "./shared";
import type { FairnessResponse, GapReport } from "./types";

export function Fairness({ data, error }: { data: FairnessResponse | null; error: string | null }) {
  if (error && !data) return <ErrorNote>{error}</ErrorNote>;
  if (!data) return <MonoLabel as="p">Running the audit…</MonoLabel>;
  const a = data.audit;
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        {data.posting_title ? <MonoLabel>Latest posting: {data.posting_title} · top {data.shortlist_size} shortlist</MonoLabel> : null}
      </div>
      {!a.available ? (
        <EmptyNote>Audit not run: {a.reason ?? "no data yet"}.</EmptyNote>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="border border-line p-3">
              <MonoLabel>Impact ratio</MonoLabel>
              <p className="font-mono text-2xl text-ink tabular-nums">{typeof a.impact_ratio === "number" ? a.impact_ratio.toFixed(2) : "n/a"}</p>
              <p className="text-xs text-ink-muted">lowest group rate / highest</p>
            </div>
            <div className={cn("border p-3", a.passes_four_fifths === true ? "border-success/60" : a.passes_four_fifths === false ? "border-danger/60" : "border-line")}>
              <MonoLabel>Four-fifths rule</MonoLabel>
              <p className={cn("flex items-center gap-2 text-xl font-semibold", a.passes_four_fifths === true ? "text-success" : a.passes_four_fifths === false ? "text-danger" : "text-ink-muted")}>
                {a.passes_four_fifths === true ? <CheckCircle2 aria-hidden="true" className="size-5" /> : a.passes_four_fifths === false ? <XCircle aria-hidden="true" className="size-5" /> : null}
                {a.passes_four_fifths === true ? "Pass" : a.passes_four_fifths === false ? "Fail" : "No ratio yet"}
              </p>
              <p className="text-xs text-ink-muted">threshold 0.80</p>
            </div>
            <div className="border border-line p-3">
              <MonoLabel>Shortlisted / eligible</MonoLabel>
              <p className="font-mono text-2xl text-ink tabular-nums">
                {a.selected ?? 0} / {a.pool ?? 0}
              </p>
              <p className="text-xs text-ink-muted">groups under {a.min_group_size ?? 5} suppressed</p>
            </div>
          </div>
          <div className="grid gap-2.5">
            <MonoLabel as="p">Selection rate by group</MonoLabel>
            {(a.rates ?? []).map((r) =>
              r.suppressed ? (
                <p key={r.group} className="text-sm text-ink-muted">
                  {r.group}: suppressed (fewer than {a.min_group_size ?? 5} people)
                </p>
              ) : (
                <StatBar key={r.group} label={`${r.group} (n=${r.n})`} value={r.rate ?? 0} max={1} tone="info" valueText={`${pct(r.rate, 1)} · ${r.selected}/${r.n}`} />
              ),
            )}
          </div>
          
        </>
      )}
      <p className="text-xs text-ink-faint">Group labels are never used for ranking.</p>
    </div>
  );
}

export function GapReportView({ data, error }: { data: GapReport | null; error: string | null }) {
  if (error && !data) return <ErrorNote>{error}</ErrorNote>;
  if (!data) return <MonoLabel as="p">Building the report…</MonoLabel>;
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <MonoLabel>
          {data.postings} posting{data.postings === 1 ? "" : "s"} · pool {data.pool_size} · min group size {data.min_group_size}
          {data.updated_at ? ` · updated ${fmtTime(data.updated_at)}` : ""}
        </MonoLabel>
      </div>
      {!data.available ? (
        <EmptyNote>Not available yet: {data.reason ?? "no data"}.</EmptyNote>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[34rem] text-left text-sm">
            <caption className="sr-only">Skills employers ask for versus skills the pool has demonstrated</caption>
            <thead>
              <tr className="border-b border-line-strong">
                {["Skill", "Postings", "Required", "Demand", "Pool coverage", "Gap"].map((h) => (
                  <th key={h} scope="col" className="text-[13px] py-2 pr-3 font-normal text-ink-faint">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.skill_id} className="border-b border-line">
                  <th scope="row" className="py-2 pr-3 font-medium text-ink">
                    {r.skill_name}
                  </th>
                  <td className="py-2 pr-3 font-mono tabular-nums">{r.postings}</td>
                  <td className="py-2 pr-3 font-mono tabular-nums">{r.required}</td>
                  <td className="py-2 pr-3 font-mono tabular-nums">{r.demand_score.toFixed(2)}</td>
                  <td className="py-2 pr-3 font-mono tabular-nums">{r.suppressed ? <span className="text-ink-muted">suppressed</span> : pct(r.coverage)}</td>
                  <td className="py-2 pr-3">
                    {r.gap === null ? (
                      <span className="text-ink-muted">n &lt; {data.min_group_size}</span>
                    ) : (
                      <span className="flex items-center gap-2">
                        <span aria-hidden="true" className="h-2 w-16 bg-line">
                          <span className="block h-full bg-warning" style={{ width: `${r.gap * 100}%` }} />
                        </span>
                        <span className="font-mono tabular-nums">{pct(r.gap)}</span>
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-xs text-ink-faint">Small groups are hidden for privacy.</p>
    </div>
  );
}
