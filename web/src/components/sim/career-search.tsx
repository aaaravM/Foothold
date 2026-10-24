"use client";

/**
 * "Search any career": debounced GET /api/careers/search?q= suggestions (O*NET occupations).
 * Picking one calls `onPick` (the sim then starts with {onet_soc}).
 */
import * as React from "react";
import { Search } from "lucide-react";
import { getJSON, isAbortError } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface CareerHit {
  onet_soc: string;
  title: string;
  summary?: string | null;
  /** set when the hit is one of the 8 core Foothold careers */
  career_id?: string | null;
}

function asHits(raw: unknown): CareerHit[] {
  const r = raw as Record<string, unknown> | unknown[] | null;
  const list = Array.isArray(r) ? r : ((r?.results ?? r?.careers ?? r?.items ?? r?.occupations ?? []) as unknown[]);
  if (!Array.isArray(list)) return [];
  const out: CareerHit[] = [];
  for (const x of list) {
    if (!x || typeof x !== "object") continue;
    const o = x as Record<string, unknown>;
    const code = typeof o.onet_soc === "string" ? o.onet_soc : typeof o.code === "string" ? o.code : null;
    const title = typeof o.title === "string" ? o.title : null;
    if (!code || !title) continue;
    out.push({
      onet_soc: code,
      title,
      summary: typeof o.summary === "string" ? o.summary : typeof o.description === "string" ? o.description : null,
      career_id: typeof o.career_id === "string" ? o.career_id : null,
    });
  }
  return out.slice(0, 8);
}

export function CareerSearch({ onPick, disabled, className }: { onPick: (hit: CareerHit) => void; disabled?: boolean; className?: string }) {
  const [q, setQ] = React.useState("");
  const [hits, setHits] = React.useState<CareerHit[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [open, setOpen] = React.useState(false);
  const [active, setActive] = React.useState(0);
  const listId = React.useId();
  const term = q.trim();

  React.useEffect(() => {
    if (term.length < 2) return;
    const ctrl = new AbortController();
    const t = window.setTimeout(() => {
      setLoading(true);
      getJSON<unknown>(`/api/careers/search?q=${encodeURIComponent(term)}`, { signal: ctrl.signal, timeoutMs: 8_000 })
        .then((r) => {
          setHits(asHits(r));
          setActive(0);
        })
        .catch((e) => {
          if (!isAbortError(e)) setHits([]);
        })
        .finally(() => setLoading(false));
    }, 220);
    return () => {
      ctrl.abort();
      window.clearTimeout(t);
    };
  }, [term]);

  const pick = (h: CareerHit | undefined) => {
    if (!h || disabled) return;
    setOpen(false);
    onPick(h);
  };

  const showList = open && term.length >= 2;

  return (
    <div className={cn("relative", className)}>
      <label className="flex items-center gap-3 rounded-full border border-line bg-surface/40 px-5 py-3 transition-colors focus-within:border-accent/60">
        <Search aria-hidden="true" className="size-4 shrink-0 text-ink-faint" />
        <span className="sr-only">Search any career</span>
        <input
          type="text"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && hits[active] ? `${listId}-${active}` : undefined}
          value={q}
          disabled={disabled}
          placeholder="Search any career"
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 150)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((a) => Math.min(a + 1, Math.max(0, hits.length - 1)));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(0, a - 1));
            } else if (e.key === "Enter") {
              e.preventDefault();
              pick(hits[active]);
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
          className="min-w-0 flex-1 bg-transparent text-ink placeholder:text-ink-faint focus:outline-none"
        />
        {loading ? <span aria-hidden="true" className="size-3 shrink-0 animate-spin rounded-full border border-ink-faint border-t-transparent" /> : null}
      </label>
      {showList ? (
        <ul
          id={listId}
          role="listbox"
          aria-label="Careers"
          className="absolute inset-x-0 top-full z-40 mt-2 max-h-80 overflow-auto rounded-2xl border border-line bg-bg/95 p-1.5 shadow-[0_20px_60px_-20px_rgba(0,0,0,0.6)] backdrop-blur-md"
        >
          {hits.length === 0 ? (
            <li className="px-4 py-3 text-sm text-ink-faint">{loading ? "Searching…" : "No matches"}</li>
          ) : (
            hits.map((h, i) => (
              <li key={h.onet_soc} id={`${listId}-${i}`} role="option" aria-selected={i === active}>
                <button
                  type="button"
                  tabIndex={-1}
                  onMouseDown={(e) => e.preventDefault()}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => pick(h)}
                  className={cn("block w-full rounded-xl px-4 py-2.5 text-left transition-colors", i === active ? "bg-surface" : "hover:bg-surface/60")}
                >
                  <span className="block text-sm text-ink">{h.title}</span>
                  {h.summary ? <span className="mt-0.5 line-clamp-1 block text-[13px] text-ink-faint">{h.summary}</span> : null}
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}
