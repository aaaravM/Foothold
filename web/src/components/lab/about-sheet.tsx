"use client";

import * as React from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { PROVENANCE_META } from "@/components/foothold/provenance-badge";
import type { Provenance } from "@/lib/types";

/** Text status label, shown only on this sources page. */
function StatusLabel({ status, className }: { status: Provenance; className?: string }) {
  const meta = PROVENANCE_META[status];
  return (
    <span className={`label-mono inline-flex h-5 items-center rounded-sm border px-1.5 leading-none ${meta.className} ${className ?? ""}`}>{status}</span>
  );
}
import { SourceLink } from "@/components/foothold/source-link";
import { useApiResource } from "./use-api";

interface Source {
  id: string;
  title?: string;
  url?: string;
  publisher?: string;
  license?: string;
  license_url?: string;
  retrieved?: string;
  status?: string;
  attribution?: string;
  note?: string;
}
interface Inventory {
  datasets: { id: string; label: string; rows: number; exists: boolean; fictional?: boolean | null }[];
  privacy: {
    session: { token_ttl_hours: number; signature: string; storage: string } | null;
    password_hashing: { algorithm: string; n: number; r: number; p: number } | null;
    min_group_sizes: { name: string; value: number; file: string }[];
  };
}

type Prov = "REAL" | "SAMPLE" | "SYNTHETIC" | "FICTIONAL";
function prov(s?: string): Prov {
  const up = (s ?? "").toUpperCase();
  if (up === "REAL" || up === "DERIVED") return "REAL";
  if (up === "SYNTHETIC") return "SYNTHETIC";
  if (up === "FICTIONAL") return "FICTIONAL";
  return "SAMPLE";
}

const WHY: { title: string; body: React.ReactNode }[] = [
  { title: "Two-sided consent", body: "Employers see blind skill cards; names appear only after the learner says yes." },
  {
    title: "Measured models",
    body: (
      <>
        Each model beats a plain baseline on held-out data.{" "}
        <Link href="/lab" className="text-ink underline underline-offset-4 hover:text-accent">
          See the Lab
        </Link>
        .
      </>
    ),
  },
  { title: "Solver-backed plans", body: "Plans meet every hour, budget and commute limit, or say none exists." },
  { title: "Agents that wait", body: "Anything that commits you waits for your approval; every number is verified." },
  { title: "Official tools first", body: "We link to Pathways Mappers and ASSIST; your counselor stays the authority." },
];

const TABS = [
  { id: "how", label: "How it works" },
  { id: "sources", label: "Sources" },
  { id: "privacy", label: "Privacy" },
  { id: "limits", label: "Limits" },
] as const;
type TabId = (typeof TABS)[number]["id"];

function Bullets({ items }: { items: React.ReactNode[] }) {
  return (
    <ul className="max-w-[62ch] space-y-3 text-[16px] leading-relaxed text-ink-muted">
      {items.map((it, i) => (
        <li key={i} className="flex gap-3">
          <span aria-hidden="true" className="mt-2.5 size-1.5 shrink-0 rounded-full bg-accent" />
          <span>{it}</span>
        </li>
      ))}
    </ul>
  );
}

export function AboutSheet() {
  const sources = useApiResource<Source[]>("/api/meta/sources");
  const inv = useApiResource<Inventory>("/api/lab/inventory");
  const [tab, setTab] = React.useState<TabId>("how");
  const list = Array.isArray(sources.data) ? sources.data : [];
  const privacy = inv.data?.privacy;
  const minGroup = privacy?.min_group_sizes[0];
  const synthetic = inv.data?.datasets.filter((d) => d.id === "learners" || d.id === "talent_pool" || d.id === "employers") ?? [];

  return (
    <div className="space-y-10">
      <div role="tablist" aria-label="About sections" className="flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`about-tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`about-panel-${t.id}`}
            onClick={() => setTab(t.id)}
            className={cn(
              "rounded-full border px-4 py-1.5 text-[15px] transition-colors",
              tab === t.id ? "border-accent bg-accent text-bg" : "border-line text-ink-muted hover:text-ink",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <section role="tabpanel" id={`about-panel-${tab}`} aria-labelledby={`about-tab-${tab}`} className="min-h-[18rem]">
        {tab === "how" ? (
          <ol className="grid gap-x-10 gap-y-6 sm:grid-cols-2">
            {WHY.map((w, i) => (
              <li key={w.title} className="grid grid-cols-[2.5rem_1fr] gap-3 border-t border-line pt-4">
                <span className="font-mono text-sm text-accent">{String(i + 1).padStart(2, "0")}</span>
                <div className="space-y-1">
                  <h2 className="text-lg font-medium text-ink">{w.title}</h2>
                  <p className="text-[16px] leading-relaxed text-ink-muted">{w.body}</p>
                </div>
              </li>
            ))}
          </ol>
        ) : null}

        {tab === "sources" ? (
          <div className="space-y-4">
            <p className="text-sm text-ink-muted">Read live. Each label says how far to trust it.</p>
            {sources.state === "loading" ? <p className="label-mono text-ink-faint">Reading sources…</p> : null}
            {sources.state === "offline" ? <p className="text-sm text-warning">API offline.</p> : null}
            <ul className="divide-y divide-line border-y border-line">
              {list.map((s) => (
                <li key={s.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0 space-y-0.5">
                    {s.url ? <SourceLink href={s.url} label={s.title ?? s.id} /> : <span className="text-ink">{s.title ?? s.id}</span>}
                    <p className="text-xs text-ink-muted">{[s.publisher, s.license].filter(Boolean).join(" · ")}</p>
                  </div>
                  <span title={PROVENANCE_META[prov(s.status)].explain}>
                    <StatusLabel status={prov(s.status)} className="shrink-0" />
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {tab === "privacy" ? (
          <Bullets
            items={[
              "Employers see skills, evidence and availability. Never a name until you accept.",
              "Consent is per employer, per request. Declining reveals nothing.",
              `Demand data is aggregate only${minGroup ? `, groups of ${minGroup.value}+` : ""}.`,
              `Sessions are per tab${privacy?.session ? ` (${privacy.session.token_ttl_hours} h)` : ""}; passwords are hashed${privacy?.password_hashing ? ` with ${privacy.password_hashing.algorithm}` : ""}.`,
              "Demo people and employers are fictional; training learners are synthetic.",
            ]}
          />
        ) : null}

        {tab === "limits" ? (
          <Bullets
            items={[
              `Models are measured on synthetic learners${synthetic.length ? ` (${synthetic.map((d) => `${d.rows} ${d.label.toLowerCase()}`).join(", ")})` : ""}, not real students.`,
              "Work-style profiles are national (O*NET), not Valley-specific.",
              "SAMPLE costs and hours are placeholders.",
              "The fairness audit uses synthetic group labels.",
              "A planning aid, not a counselor or official map.",
            ]}
          />
        ) : null}
      </section>

    </div>
  );
}
