"use client";

import * as React from "react";
import Link from "next/link";
import { MonoLabel } from "@/components/foothold/mono-label";
import { ProvenanceBadge, PROVENANCE_META } from "@/components/foothold/provenance-badge";
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
  {
    title: "A two-sided consent network",
    body: "Learners and employers both hold accounts. Employers see blind skill cards; a name and contact appear only after the learner accepts that employer's request, from their own inbox.",
  },
  {
    title: "Trained models with measured results",
    body: (
      <>
        Career fit, event selection and recommendations are trained models, each scored against a plain baseline on held-out data. The numbers and the commands that rebuild them are on the{" "}
        <Link href="/lab" className="text-ink underline underline-offset-4 hover:text-accent">
          Lab sheet
        </Link>
        .
      </>
    ),
  },
  {
    title: "Solver guarantees, not suggestions",
    body: "Pathway plans come from a CP-SAT constraint solver. A plan it returns satisfies every hour, budget and commute limit you set, or it says no plan exists.",
  },
  {
    title: "A persistent agent loop",
    body: "Agents run as checkpointed graphs: work resumes where it stopped, independent steps run in parallel, and anything that commits you to something waits for your approval. Every number an agent states passes the claim verifier first.",
  },
  {
    title: "Alongside the Valley's own tools",
    body: "Foothold links to each college's Program Pathways Mapper and to ASSIST for transfer agreements instead of copying them. Official maps and your counselor stay the authority.",
  },
];

export function AboutSheet() {
  const sources = useApiResource<Source[]>("/api/meta/sources");
  const inv = useApiResource<Inventory>("/api/lab/inventory");
  const list = Array.isArray(sources.data) ? sources.data : [];
  const onet = list.find((s) => s.id.startsWith("onet"));
  const privacy = inv.data?.privacy;
  const minGroup = privacy?.min_group_sizes[0];
  const synthetic = inv.data?.datasets.filter((d) => d.id === "learners" || d.id === "talent_pool" || d.id === "employers") ?? [];

  return (
    <div className="space-y-14">
      <section aria-labelledby="why" className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-4">
          <MonoLabel as="p" tone="accent">
            Section 1
          </MonoLabel>
          <h2 id="why" className="type-display-md mt-1 text-ink">
            Why this isn&rsquo;t a chatbot
          </h2>
        </div>
        <ol className="space-y-6 lg:col-span-8">
          {WHY.map((w, i) => (
            <li key={w.title} className="grid grid-cols-[2.5rem_1fr] gap-3 border-t border-line pt-4">
              <span className="font-mono text-sm text-accent">{String(i + 1).padStart(2, "0")}</span>
              <div className="space-y-1">
                <h3 className="text-lg font-medium text-ink">{w.title}</h3>
                <p className="max-w-[62ch] text-[16px] leading-relaxed text-ink-muted">{w.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="sources" className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-4">
          <MonoLabel as="p" tone="accent">
            Section 2
          </MonoLabel>
          <h2 id="sources" className="type-display-md mt-1 text-ink">
            Data sources
          </h2>
          <p className="mt-2 text-sm text-ink-muted">Read live from the source register. Each badge says how far to trust the data.</p>
        </div>
        <div className="space-y-6 lg:col-span-8">
          <div aria-labelledby="legend">
            <h3 id="legend" className="label-mono text-ink-faint">
              Provenance legend
            </h3>
            <dl className="mt-3 grid gap-4 sm:grid-cols-2">
              {(["REAL", "SAMPLE", "SYNTHETIC", "FICTIONAL"] as const).map((p) => (
                <div key={p} className="space-y-2">
                  <dt>
                    <ProvenanceBadge status={p} />
                  </dt>
                  <dd className="text-sm text-ink-muted">{PROVENANCE_META[p].explain}</dd>
                </div>
              ))}
            </dl>
          </div>
          {sources.state === "loading" ? <p className="label-mono text-ink-faint">Reading sources…</p> : null}
          {sources.state === "offline" ? <p className="text-sm text-warning">API offline: sources load from the Foothold API.</p> : null}
          <ul className="divide-y divide-line border-y border-line">
            {list.map((s) => (
              <li key={s.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0 space-y-0.5">
                  {s.url ? <SourceLink href={s.url} label={s.title ?? s.id} /> : <span className="text-ink">{s.title ?? s.id}</span>}
                  <p className="text-xs text-ink-muted">
                    {[s.publisher, s.license, s.retrieved ? `retrieved ${s.retrieved}` : null].filter(Boolean).join(" · ")}
                  </p>
                </div>
                <ProvenanceBadge status={prov(s.status)} href={s.url} className="shrink-0" />
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section aria-labelledby="privacy" className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-4">
          <MonoLabel as="p" tone="accent">
            Section 3
          </MonoLabel>
          <h2 id="privacy" className="type-display-md mt-1 text-ink">
            Privacy model
          </h2>
        </div>
        <ul className="space-y-3 text-[16px] leading-relaxed text-ink-muted lg:col-span-8">
          <li>Employers see blind cards built from a whitelist of fields: demonstrated skills, evidence and availability. Name and contact stay hidden until the learner accepts that employer&rsquo;s request.</li>
          <li>Consent is per employer and per request, recorded with a timestamp; declining reveals nothing.</li>
          <li>
            Employer demand reaches learners only as aggregate skill counts
            {minGroup ? `, never below a group of ${minGroup.value}` : ""}.
          </li>
          <li>
            Sessions are per browser tab
            {privacy?.session ? ` (${privacy.session.signature}-signed token, ${privacy.session.token_ttl_hours} h, kept in sessionStorage)` : ""}; passwords are hashed
            {privacy?.password_hashing ? ` with ${privacy.password_hashing.algorithm} (N=${privacy.password_hashing.n}, r=${privacy.password_hashing.r}, p=${privacy.password_hashing.p})` : ""}.
          </li>
          <li>All demo people, employers and circle members are fictional. Learner profiles used for training are synthetic.</li>
        </ul>
      </section>

      <section aria-labelledby="limits" className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-4">
          <MonoLabel as="p" tone="accent">
            Section 4
          </MonoLabel>
          <h2 id="limits" className="type-display-md mt-1 text-ink">
            Limitations
          </h2>
        </div>
        <ul className="space-y-3 text-[16px] leading-relaxed text-ink-muted lg:col-span-8">
          <li>
            The models were trained and measured on synthetic learners
            {synthetic.length ? ` (${synthetic.map((d) => `${d.rows} ${d.label.toLowerCase()}`).join(", ")})` : ""}. They show the method works; they are not validated on real Valley students.
          </li>
          <li>Work-style profiles describe occupations nationally (O*NET), not specific Valley employers.</li>
          <li>Course costs and hours marked SAMPLE are placeholders until checked against the college catalog.</li>
          <li>The fairness audit uses synthetic group labels; passing it says nothing about real applicants.</li>
          <li>Foothold is a planning aid. It does not replace a counselor, an official program map or a transfer agreement.</li>
        </ul>
      </section>

      <section aria-labelledby="credit" className="border-t border-line pt-6">
        <h2 id="credit" className="label-mono text-ink-faint">
          Credit
        </h2>
        <p className="mt-2 max-w-[80ch] text-sm leading-relaxed text-ink-muted">
          {onet?.attribution ??
            "This page includes information from the O*NET 31.0 Database by the U.S. Department of Labor, Employment and Training Administration (USDOL/ETA). Used under the CC BY 4.0 license. O*NET® is a trademark of USDOL/ETA."}
        </p>
      </section>
    </div>
  );
}
