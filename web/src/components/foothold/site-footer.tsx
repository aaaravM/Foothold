import * as React from "react";
import Link from "next/link";

const linkClass = "underline decoration-ink/25 underline-offset-4 transition-colors hover:text-ink hover:decoration-ink/60";

/** Quiet footer on every page: the name and the required credits. Nothing else. */
export function SiteFooter() {
  return (
    <footer className="relative mt-auto">
      <div className="page-container flex flex-col gap-3 py-10 text-[12px] leading-relaxed text-ink-faint md:flex-row md:items-start md:justify-between md:gap-12">
        <Link href="/" className="font-display text-[0.95rem] font-semibold tracking-[-0.02em] text-ink">
          Foothold
        </Link>
        <div className="max-w-3xl space-y-1.5">
          <p>
            Includes information from the O*NET 31.0 Database by the U.S. Department of Labor, Employment and Training Administration (USDOL/ETA), used under the{" "}
            <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer license" className={linkClass}>
              CC BY 4.0<span className="sr-only"> (opens in a new tab)</span>
            </a>{" "}
            license. O*NET® is a trademark of USDOL/ETA. Foothold has modified all or some of this information; USDOL/ETA has not approved, endorsed, or tested
            these modifications.
          </p>
          <p>UI: Cult UI, Watermelon UI, Skiper UI, shadcn/ui, Radix, Lucide. Type: Mona Sans, Hubot Sans, Martian Mono.</p>
        </div>
      </div>
    </footer>
  );
}
