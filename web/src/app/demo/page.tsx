import type { Metadata } from "next";
import { DemoChecks } from "@/components/demo/demo-checks";
import { MonoLabel } from "@/components/foothold/mono-label";
import { SheetFrame } from "@/components/foothold/sheet-frame";
import { DEMO_ACCOUNTS } from "@/lib/auth";
import { getSheet, sheetFrameProps } from "@/lib/sheets";

export const metadata: Metadata = { title: "Demo", robots: { index: false, follow: false } };

const TABS: { tab: number; persona: string; opens: string }[] = [
  { tab: 1, persona: "luis", opens: "/sim" },
  { tab: 2, persona: "tri_valley_freight", opens: "/employers" },
  { tab: 3, persona: "maya", opens: "/path" },
  { tab: 4, persona: "dev", opens: "/circle" },
];

const RUN: { time: string; tab: string; step: string }[] = [
  { time: "0:00", tab: "Landing", step: "Open / signed out. One line: the Central Valley has jobs and colleges, but no map between them. Click Sign in." },
  { time: "0:30", tab: "Tab 1 · Luis", step: "SIM: pick Diesel Mechanic. Play two moments with keys 1/2/3. Point at coworkers reacting in parallel in Behind the scenes." },
  { time: "1:30", tab: "Tab 1 · Luis", step: "Finish the day. Report: 21-trait radar, top-3 careers from the trained model, local wage with REAL source badges. Click Plan a route." },
  { time: "2:15", tab: "Tab 3 · Maya", step: "PATH: constraints prefilled from her profile (10 h/wk, $4,000, bus). Type “no classes before 9am, weekends off”, Turn into rules, Apply. Routes re-solve in ms; CP-SAT vs greedy." },
  { time: "3:00", tab: "Tab 3 · Maya", step: "Propose my plan. Reject with “too long”; the reason becomes a rule and it re-solves. Approve. Steps land on the board." },
  { time: "3:45", tab: "Tab 2 · Tri-Valley Freight", step: "EMPLOYERS: paste a posting, see blind talent cards, send a consent request to a learner." },
  { time: "4:15", tab: "Tab 1 · Luis", step: "INBOX: the request appears without a reload. Accept. Back in Tab 2 the card unlocks." },
  { time: "4:40", tab: "Tab 4 · Dev", step: "CIRCLE: support circle and the coach. Close on LAB: every model with its metrics and data provenance." },
];

const SETUP: { label: string; cmd: string; note: string }[] = [
  { label: "Reset demo state", cmd: "python scripts/reset_demo.py", note: "Run from the repo root before each run-through to put the demo accounts back to their starting state." },
  { label: "Tunnel (open network)", cmd: "bash scripts/tunnel.sh", note: "Opens a public HTTPS tunnel to the API on :8000. Leave it running; register the URL it prints (next step) if the script does not do it for you." },
  {
    label: "Register a URL by hand",
    cmd: "bash scripts/register_api_url.sh https://<your-tunnel-host>",
    note: "Writes the URL to Supabase public_config 'api_url'; every open copy of the site picks it up on its next load. No rebuild needed.",
  },
  { label: "Override in one browser", cmd: "?api=https://<host>   ·   ?api=clear", note: "Add to any page URL; saved in this browser until cleared." },
];

export default function DemoPage() {
  return (
    <SheetFrame {...sheetFrameProps("demo")} description={getSheet("demo").description}>
      <div className="grid gap-10 lg:grid-cols-12">
        <div className="space-y-8 lg:col-span-7">
          <section aria-labelledby="demo-tabs">
            <MonoLabel as="h2" id="demo-tabs" tone="ink" className="mb-3">
              Tabs · one account per tab
            </MonoLabel>
            <ul className="divide-y divide-line border border-line">
              {TABS.map((t) => {
                const acc = DEMO_ACCOUNTS.find((d) => d.persona_id === t.persona);
                if (!acc) return null;
                return (
                  <li key={t.tab} className="flex flex-wrap items-center gap-x-4 gap-y-1 p-3">
                    <span className="font-mono text-sm text-ink-muted tabular-nums">TAB {t.tab}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-ink">{acc.display_name}</span>
                      <span className="block text-xs text-ink-muted">
                        {acc.kind === "employer" ? "Employer" : "Learner"} · opens {t.opens}
                      </span>
                    </span>
                    <a
                      href={`/signin?as=${acc.persona_id}&next=${encodeURIComponent(t.opens)}`}
                      target="_blank"
                      rel="noopener"
                      className="border border-line-strong px-3 py-1.5 text-sm text-ink hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                    >
                      Open sign-in in new tab
                    </a>
                  </li>
                );
              })}
            </ul>
            <div className="mt-2 flex items-center gap-3">
              <MonoLabel tone="faint">The sign-in form opens pre-filled; press Sign in.</MonoLabel>
            </div>
          </section>

          <section aria-labelledby="demo-run">
            <MonoLabel as="h2" id="demo-run" tone="ink" className="mb-3">
              Run of show · 5 minutes
            </MonoLabel>
            <ol className="space-y-3">
              {RUN.map((r) => (
                <li key={r.time} className="grid grid-cols-[3.5rem_1fr] gap-3">
                  <span className="font-mono text-sm text-accent tabular-nums">{r.time}</span>
                  <span>
                    <MonoLabel as="span" className="block">
                      {r.tab}
                    </MonoLabel>
                    <span className="text-ink">{r.step}</span>
                  </span>
                </li>
              ))}
            </ol>
          </section>
        </div>
        <aside className="space-y-8 lg:col-span-5">
          <DemoChecks />
          <section aria-labelledby="demo-setup">
            <MonoLabel as="h2" id="demo-setup" tone="ink" className="mb-3">
              Setup · reset and tunnel
            </MonoLabel>
            <ol className="space-y-4">
              {SETUP.map((s) => (
                <li key={s.label} className="space-y-1">
                  <MonoLabel as="p">{s.label}</MonoLabel>
                  <code className="block overflow-x-auto border border-line bg-surface px-3 py-2 font-mono text-sm whitespace-pre text-ink">{s.cmd}</code>
                  <p className="text-sm text-ink-muted">{s.note}</p>
                </li>
              ))}
            </ol>
          </section>
          <MonoLabel as="p" tone="faint" className="mt-6">
            Unlinked presenter page · not indexed
          </MonoLabel>
        </aside>
      </div>
    </SheetFrame>
  );
}
