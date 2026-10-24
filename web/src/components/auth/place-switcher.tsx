"use client";

import * as React from "react";
import { Popover as P } from "radix-ui";
import { motion } from "motion/react";
import { Check, LocateFixed, MapPin } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { fetchPlaces, type Place } from "@/lib/profile";
import { EASE } from "@/components/motion/kit";
import { useAccount } from "./auth-provider";
import { useLocate } from "./place-picker";
import { useProfile } from "./use-profile";

/** "Near Modesto": a small place switcher for signed-in learners. Saves to the profile. */
export function PlaceSwitcher({ className }: { className?: string }) {
  const { account } = useAccount();
  const { profile, save } = useProfile();
  const [places, setPlaces] = React.useState<Place[]>([]);
  const [open, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!open || places.length) return;
    let live = true;
    fetchPlaces()
      .then((r) => {
        if (live) setPlaces(r.places);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [open, places.length]);

  const pick = React.useCallback(
    async (p: Place) => {
      setBusy(p.id);
      try {
        await save({ place_id: p.id });
        toast(`Showing what's near ${p.name}`);
        setOpen(false);
      } catch {
        toast("Couldn't change your place. Try again.");
      } finally {
        setBusy(null);
      }
    },
    [save],
  );
  const { state, locate } = useLocate(places, pick);

  if (!account || account.kind !== "learner") return null;
  const name = profile?.place?.name;

  return (
    <P.Root open={open} onOpenChange={setOpen}>
      <P.Trigger asChild>
        <button
          type="button"
          aria-label={name ? `Your place: near ${name}. Change place` : "Set your place"}
          className={cn(
            "group inline-flex h-9 items-center gap-1.5 rounded-full px-3 text-sm text-ink-muted transition-colors hover:bg-ink/5 hover:text-ink data-[state=open]:bg-ink/5 data-[state=open]:text-ink",
            className,
          )}
        >
          <MapPin aria-hidden="true" className="size-3.5 text-accent" />
          <span className="hidden sm:inline">{name ? `Near ${name}` : "Set your place"}</span>
        </button>
      </P.Trigger>
      <P.Portal>
        <P.Content align="end" sideOffset={10} collisionPadding={12} className="z-50 w-72 outline-none">
          <motion.div
            initial={{ opacity: 0, y: -6, filter: "blur(6px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            transition={{ duration: 0.45, ease: EASE }}
            className="overflow-hidden rounded-2xl border border-line bg-surface shadow-2xl shadow-black/40"
          >
            <div className="px-4 pt-4 pb-2">
              <p className="text-sm font-medium text-ink">Where are you?</p>
              <p className="text-xs text-ink-muted">We show programs, jobs and circles near you.</p>
            </div>
            <button
              type="button"
              onClick={locate}
              disabled={state === "busy" || !places.length}
              className="mx-2 flex w-[calc(100%-1rem)] items-center gap-2 rounded-lg px-2 py-2 text-left text-sm text-ink hover:bg-ink/5"
            >
              <LocateFixed aria-hidden="true" className="size-4 text-accent" />
              {state === "busy" ? "Finding you…" : state === "denied" ? "Location unavailable" : "Use my location"}
            </button>
            <ul className="max-h-72 overflow-y-auto px-2 pb-2">
              {places.length === 0 ? <li className="px-2 py-2 text-sm text-ink-faint">Loading towns…</li> : null}
              {places.map((p) => {
                const on = p.id === profile?.place_id;
                return (
                  <li key={p.id}>
                    <button
                      type="button"
                      onClick={() => void pick(p)}
                      disabled={busy !== null}
                      className="flex w-full items-center justify-between rounded-lg px-2 py-2 text-left text-sm transition-colors hover:bg-ink/5"
                    >
                      <span className={on ? "text-ink" : "text-ink-muted"}>
                        {p.name} <span className="text-ink-faint">· {p.county}</span>
                      </span>
                      {on ? <Check aria-hidden="true" className="size-4 text-accent" /> : busy === p.id ? <span className="text-xs text-ink-faint">Saving…</span> : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          </motion.div>
        </P.Content>
      </P.Portal>
    </P.Root>
  );
}
