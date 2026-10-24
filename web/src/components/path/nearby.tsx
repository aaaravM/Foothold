"use client";

import * as React from "react";
import { AnimatePresence, motion } from "motion/react";
import { MapPin } from "lucide-react";
import { getJSON, patchJSON } from "@/lib/api";
import { cn } from "@/lib/utils";
import { EASE, staggerChild, staggerParent } from "@/components/sim/fx";

export interface Place {
  id: string;
  name: string;
  county?: string;
  lat?: number;
  lon?: number;
}
interface NearProgram {
  id: string;
  name: string;
  career_id: string;
  route_type: string;
  credential?: string;
  url?: string;
}
interface Provider {
  id: string;
  name: string;
  kind: string;
  distance_km: number;
  drive_minutes: number;
  programs: NearProgram[];
}
interface NearResponse {
  origin: { place_id?: string; name?: string } | null;
  providers: Provider[];
  circles?: { id: string; name: string; meets?: string; nearest_meetup?: string | null }[];
}
interface Profile {
  place_id?: string | null;
  place?: { id: string; name: string; county?: string } | null;
}

/** Places list + the signed-in user's saved place (shared by Path and Circles). */
export function usePlaces() {
  const [places, setPlaces] = React.useState<Place[]>([]);
  const [placeId, setPlaceId] = React.useState<string | null>(null);
  const [ready, setReady] = React.useState(false);
  React.useEffect(() => {
    let live = true;
    Promise.allSettled([getJSON<{ places: Place[] }>("/api/meta/places"), getJSON<Profile>("/api/auth/me/profile")]).then(([p, prof]) => {
      if (!live) return;
      if (p.status === "fulfilled") setPlaces(p.value.places ?? []);
      if (prof.status === "fulfilled") setPlaceId(prof.value.place_id ?? prof.value.place?.id ?? null);
      setReady(true);
    });
    return () => {
      live = false;
    };
  }, []);
  const save = React.useCallback(async (id: string) => {
    setPlaceId(id);
    try {
      await patchJSON("/api/auth/me/profile", { place_id: id });
    } catch {
      /* keep the local choice even if saving fails */
    }
  }, []);
  return { places, placeId, ready, save };
}

/** Pill-shaped place picker. */
export function PlacePicker({
  places,
  value,
  onChange,
  className,
  label = "Your area",
}: {
  places: Place[];
  value: string | null;
  onChange: (id: string) => void;
  className?: string;
  label?: string;
}) {
  return (
    <label className={cn("group relative inline-flex items-center gap-2 rounded-full border border-line py-1.5 pr-3 pl-3 text-sm transition-colors hover:border-line-strong", className)}>
      <MapPin aria-hidden="true" className="size-4 text-accent" />
      <span className="sr-only">{label}</span>
      <select
        value={value ?? ""}
        onChange={(e) => e.target.value && onChange(e.target.value)}
        className="cursor-pointer appearance-none bg-transparent pr-4 text-ink focus-visible:outline-none"
      >
        {!value ? <option value="">Choose your area</option> : null}
        {places.map((p) => (
          <option key={p.id} value={p.id} className="bg-bg text-ink">
            {p.name}
            {p.county ? `, ${p.county}` : ""}
          </option>
        ))}
      </select>
      <span aria-hidden="true" className="pointer-events-none absolute right-3 text-xs text-ink-faint">
        ▾
      </span>
    </label>
  );
}

const KIND: Record<string, string> = { community_college: "Community college", apprenticeship: "Apprenticeship center", university: "University", csu: "CSU", uc: "UC" };

/** "Programs near <place>": nearest campuses, drive time, and programs for the chosen career first. */
export function NearbyPrograms({ placeId, placeName, careerId }: { placeId: string | null; placeName?: string; careerId: string }) {
  const [data, setData] = React.useState<NearResponse | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  React.useEffect(() => {
    if (!placeId) return;
    let live = true;
    getJSON<NearResponse>(`/api/places/near?place_id=${encodeURIComponent(placeId)}&limit=8`)
      .then((r) => {
        if (!live) return;
        setData(r);
        setErr(null);
      })
      .catch(() => live && setErr("Couldn't load nearby programs right now."));
    return () => {
      live = false;
    };
  }, [placeId]);

  if (!placeId) return <p className="text-sm text-ink-muted">Choose your area to see the nearest campuses and programs.</p>;
  if (err) return <p className="text-sm text-ink-muted">{err}</p>;
  if (!data) return <div className="h-32 animate-pulse rounded-2xl bg-surface/50" />;

  const ranked = [...data.providers]
    .map((p) => ({ ...p, match: p.programs.filter((g) => g.career_id === careerId) }))
    .sort((a, b) => Number(b.match.length > 0) - Number(a.match.length > 0) || a.drive_minutes - b.drive_minutes)
    .slice(0, 4);

  return (
    <div>
      <h3 className="text-lg text-ink">
        Programs near <span className="text-accent">{data.origin?.name ?? placeName ?? "you"}</span>
      </h3>
      <AnimatePresence mode="wait">
        <motion.ul
          key={`${placeId}-${careerId}`}
          className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2"
          variants={staggerParent(0.07)}
          initial="hidden"
          animate="show"
          exit={{ opacity: 0, transition: { duration: 0.2 } }}
        >
          {ranked.map((p) => (
            <motion.li key={p.id} variants={staggerChild} className="min-w-0 rounded-2xl border border-line p-4 transition-colors duration-300 hover:border-line-strong">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-ink" title={p.name}>
                    {p.name}
                  </p>
                  <p className="text-xs text-ink-faint">{KIND[p.kind] ?? p.kind.replace(/_/g, " ")}</p>
                </div>
                <span className="shrink-0 text-right">
                  <span className="block font-mono text-lg leading-none text-ink tabular-nums">{p.drive_minutes}</span>
                  <span className="text-xs text-ink-faint">min drive</span>
                </span>
              </div>
              <div className="mt-3 h-1 overflow-hidden rounded-full bg-line">
                <motion.div
                  className="h-full origin-left rounded-full bg-accent/70"
                  initial={{ scaleX: 0 }}
                  animate={{ scaleX: Math.max(0.06, 1 - p.drive_minutes / 120) }}
                  transition={{ duration: 1, ease: EASE, delay: 0.2 }}
                />
              </div>
              {p.match.length ? (
                <ul className="mt-3 space-y-1 text-sm">
                  {p.match.slice(0, 2).map((g) => (
                    <li key={g.id} className="truncate">
                      {g.url ? (
                        <a href={g.url} target="_blank" rel="noreferrer" className="link-draw text-ink-muted hover:text-ink" title={g.name}>
                          {g.name}
                        </a>
                      ) : (
                        <span className="text-ink-muted">{g.name}</span>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm text-ink-faint">{p.programs.length ? `${p.programs.length} other programs` : "Ask about programs"}</p>
              )}
            </motion.li>
          ))}
        </motion.ul>
      </AnimatePresence>
    </div>
  );
}
