"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { sheetForPath, sheetOfLabel } from "@/lib/sheets";
import { MonoLabel } from "./mono-label";
import { TitleBlock } from "./title-block";

/** Exact modified-version credit required by the O*NET 31.0 license (docs/research/data-onet.md section 2). */
function OnetCredit() {
  return (
    <p className="max-w-4xl text-xs leading-relaxed text-ink-muted">
      This page includes information from the O*NET 31.0 Database by the U.S. Department of Labor, Employment and
      Training Administration (USDOL/ETA). Used under the{" "}
      <a
        href="https://creativecommons.org/licenses/by/4.0/"
        target="_blank"
        rel="noopener noreferrer license"
        className="text-ink underline decoration-line-strong underline-offset-4 hover:text-accent hover:decoration-accent"
      >
        CC BY 4.0<span className="sr-only"> (opens in a new tab)</span>
      </a>{" "}
      license. O*NET® is a trademark of USDOL/ETA. Foothold has modified all or some of this information. USDOL/ETA has
      not approved, endorsed, or tested these modifications.
    </p>
  );
}

function RouteTitleBlock({ pathname }: { pathname: string | null }) {
  const meta = sheetForPath(pathname);
  const title = meta.id === "home" ? "Foothold / Cover" : `Foothold / ${meta.title}`;
  return <TitleBlock dwg={meta.dwg} sheetOf={sheetOfLabel(meta)} title={title} />;
}

function ActiveTitleBlock() {
  const pathname = usePathname();
  return <RouteTitleBlock pathname={pathname} />;
}

/** Footer on every page: drawing title block for the current route + colophon and data credits. */
export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-line">
      <div className="mx-auto max-w-[1440px] space-y-8 px-3 py-8 sm:px-6 lg:px-8">
        <React.Suspense fallback={<RouteTitleBlock pathname={null} />}>
          <ActiveTitleBlock />
        </React.Suspense>

        <div className="grid gap-6 md:grid-cols-[10rem_minmax(0,1fr)]">
          <MonoLabel as="h2">Data</MonoLabel>
          <div className="space-y-2">
            <OnetCredit />
            <p className="max-w-4xl text-xs leading-relaxed text-ink-muted">
              All people, employers and circle members in Foothold are fictional. Wages, costs and program details carry a
              provenance label (REAL, SAMPLE, SYNTHETIC or FICTIONAL) with a link to verify. Sources and methods:{" "}
              <Link href="/about" className="text-ink underline decoration-line-strong underline-offset-4 hover:text-accent hover:decoration-accent">
                About &amp; data sources
              </Link>
              . How the models are measured:{" "}
              <Link href="/lab" className="text-ink underline decoration-line-strong underline-offset-4 hover:text-accent hover:decoration-accent">
                Model lab
              </Link>
              .
            </p>
          </div>

          <MonoLabel as="h2">Colophon</MonoLabel>
          <p className="max-w-4xl text-xs leading-relaxed text-ink-muted">
            UI components from Cult UI (MIT), Watermelon UI (MIT) and Skiper UI (free components), on shadcn/ui and Radix
            primitives (MIT). Icons: Lucide (ISC). Type: Mona Sans and Hubot Sans by GitHub, Martian Mono by Evil Martians
            (SIL Open Font License 1.1).
          </p>

          <MonoLabel as="h2">Care</MonoLabel>
          <p className="max-w-4xl text-xs leading-relaxed text-ink-muted">
            Foothold&apos;s coach is a practice tool, not therapy. If you are in crisis, call or text 988 or reach out to
            someone you trust.
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
          <MonoLabel tone="muted">Foothold · Try the job. Prove the skill. Get the foothold.</MonoLabel>
          <MonoLabel>Central Valley, California</MonoLabel>
        </div>
      </div>
    </footer>
  );
}
