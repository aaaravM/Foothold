"use client";

import * as React from "react";
import Link from "next/link";
import { useProfile } from "@/components/auth/use-profile";
import { useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Check } from "lucide-react";
import { toast } from "sonner";
import { useAccount } from "@/components/auth/auth-provider";
import { PlacePicker } from "@/components/auth/place-picker";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { EASE, Magnetic, SplitWords, SwapArrow, TextRoll } from "@/components/motion/kit";
import { destinationFor, safeNextPath } from "@/lib/auth";
import { fetchPlaces, INTEREST_OPTIONS, saveProfile, type Place, type ProfilePatch } from "@/lib/profile";
import { cn } from "@/lib/utils";

type StepId = "place" | "week" | "interests" | "visible";

const LEARNER_STEPS: StepId[] = ["place", "week", "interests", "visible"];
const EMPLOYER_STEPS: StepId[] = ["place"];

const TITLES: Record<StepId, { title: string; lead: string }> = {
  place: { title: "Where's home?", lead: "We'll keep things close." },
  week: { title: "Your week?", lead: "Plans use only your real time." },
  interests: { title: "What interests you?", lead: "Pick a few." },
  visible: { title: "Let employers find you?", lead: "Skills only, never your name." },
};

function money(n: number) {
  return n >= 10000 ? `$${Math.round(n / 1000)}k` : `$${n.toLocaleString()}`;
}

export function Onboarding() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNextPath(params.get("next"));
  const reduce = useReducedMotion();
  const { account, status } = useAccount();
  const [places, setPlaces] = React.useState<Place[]>([]);
  const [placesError, setPlacesError] = React.useState(false);
  const [i, setI] = React.useState(0);
  const [dir, setDir] = React.useState(1);
  const [placeId, setPlaceId] = React.useState<string | null>(null);
  const [hours, setHours] = React.useState(12);
  const [budget, setBudget] = React.useState(2000);
  const [interests, setInterests] = React.useState<string[]>([]);
  const [optIn, setOptIn] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const { profile } = useProfile();
  const [seeded, setSeeded] = React.useState(false);

  /* Returning visitors start from what they already saved (state adjusted during render, once). */
  if (profile && !seeded) {
    setSeeded(true);
    if (profile.place_id) setPlaceId(profile.place_id);
    if (profile.hours_per_week) setHours(profile.hours_per_week);
    if (profile.budget_usd) setBudget(profile.budget_usd);
    if (profile.interests?.length) setInterests(profile.interests);
    setOptIn(!!profile.talent_opt_in);
  }

  React.useEffect(() => {
    let live = true;
    fetchPlaces()
      .then((r) => {
        if (live) setPlaces(r.places);
      })
      .catch(() => {
        if (live) setPlacesError(true);
      });
    return () => {
      live = false;
    };
  }, []);

  if (status === "loading") return <div className="page-container py-24 text-sm text-ink-muted">Loading…</div>;
  if (!account) {
    return (
      <div className="page-container flex flex-col items-start gap-6 py-[14svh]">
        <h1 className="type-display-md text-ink">Create an account first.</h1>
        <Link href="/signup" className="btn-primary group">
          <TextRoll text="Sign up" />
          <SwapArrow />
        </Link>
      </div>
    );
  }

  const steps = account.kind === "employer" ? EMPLOYER_STEPS : LEARNER_STEPS;
  const step = steps[i];
  const last = i === steps.length - 1;
  const firstName = account.display_name.split(" ")[0];

  const go = (d: number) => {
    setDir(d);
    setI((v) => Math.max(0, Math.min(steps.length - 1, v + d)));
  };

  async function finish(skip = false) {
    if (!account) return;
    setSaving(true);
    const patch: ProfilePatch = {};
    if (placeId) patch.place_id = placeId;
    if (account.kind === "learner" && !skip) {
      patch.hours_per_week = hours;
      patch.budget_usd = budget;
      patch.interests = interests;
      patch.talent_opt_in = optIn;
    }
    try {
      if (Object.keys(patch).length) await saveProfile(patch);
      router.push(destinationFor(account, next));
    } catch {
      toast("Couldn't save that. Try again.");
      setSaving(false);
    }
  }

  const canNext = step !== "place" || !!placeId;

  return (
    <div className="page-container flex flex-1 flex-col py-[6svh] lg:py-[9svh]">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm text-ink-muted">Welcome, {firstName}</p>
        <div className="flex items-center gap-1.5" aria-label={`Step ${i + 1} of ${steps.length}`}>
          {steps.map((s, k) => (
            <span key={s} className="relative h-1 w-8 overflow-hidden rounded-full bg-ink/10">
              <motion.span className="absolute inset-0 rounded-full bg-accent" initial={false} animate={{ scaleX: k <= i ? 1 : 0 }} style={{ originX: 0 }} transition={{ duration: 0.6, ease: EASE }} />
            </span>
          ))}
        </div>
      </div>

      <div className="relative mt-10 flex-1">
        <AnimatePresence mode="wait" custom={dir} initial={false}>
          <motion.section
            key={step}
            custom={dir}
            initial={reduce ? false : { opacity: 0, x: dir * 40, filter: "blur(8px)" }}
            animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, x: dir * -40, filter: "blur(8px)" }}
            transition={{ duration: 0.6, ease: EASE }}
            aria-labelledby={`ob-${step}`}
          >
            <SplitWords as="h1" id={`ob-${step}`} immediate text={TITLES[step].title} className="max-w-[18ch] type-display-lg text-ink" />
            <p className="mt-4 max-w-[48ch] text-[18px] text-ink-muted">{TITLES[step].lead}</p>

            <div className="mt-10">
              {step === "place" ? (
                placesError ? (
                  <p className="text-ink-muted">Towns didn&rsquo;t load. Set it later.</p>
                ) : places.length ? (
                  <PlacePicker places={places} value={placeId} onChange={setPlaceId} />
                ) : (
                  <p className="text-ink-muted">Loading towns…</p>
                )
              ) : null}

              {step === "week" ? (
                <div className="grid max-w-3xl gap-10 md:grid-cols-2">
                  <div>
                    <div className="flex items-baseline justify-between">
                      <label id="ob-hours" className="text-sm font-medium text-ink">
                        Hours a week for learning
                      </label>
                      <span className="font-mono text-2xl text-ink tabular-nums">{hours}h</span>
                    </div>
                    <Slider aria-labelledby="ob-hours" className="mt-5" min={2} max={40} step={1} value={[hours]} onValueChange={(v) => setHours(v[0] ?? hours)} />
                  </div>
                  <div>
                    <div className="flex items-baseline justify-between">
                      <label id="ob-budget" className="text-sm font-medium text-ink">
                        Budget for school
                      </label>
                      <span className="font-mono text-2xl text-ink tabular-nums">{money(budget)}</span>
                    </div>
                    <Slider aria-labelledby="ob-budget" className="mt-5" min={0} max={20000} step={250} value={[budget]} onValueChange={(v) => setBudget(v[0] ?? budget)} />
                  </div>
                </div>
              ) : null}

              {step === "interests" ? (
                <div className="flex max-w-3xl flex-wrap gap-2.5">
                  {INTEREST_OPTIONS.map((o, k) => {
                    const on = interests.includes(o.id);
                    return (
                      <motion.button
                        key={o.id}
                        type="button"
                        aria-pressed={on}
                        initial={reduce ? false : { opacity: 0, y: 12 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6, ease: EASE, delay: 0.1 + k * 0.04 }}
                        onClick={() => setInterests((cur) => (on ? cur.filter((x) => x !== o.id) : [...cur, o.id]))}
                        className={cn(
                          "inline-flex items-center gap-2 rounded-full border px-4 py-2.5 text-[15px] transition-colors duration-300",
                          on ? "border-accent bg-accent text-accent-ink" : "border-line text-ink-muted hover:border-line-strong hover:text-ink",
                        )}
                      >
                        <AnimatePresence initial={false}>
                          {on ? (
                            <motion.span initial={{ width: 0, opacity: 0 }} animate={{ width: 16, opacity: 1 }} exit={{ width: 0, opacity: 0 }} className="inline-flex overflow-hidden">
                              <Check aria-hidden="true" className="size-4" />
                            </motion.span>
                          ) : null}
                        </AnimatePresence>
                        {o.label}
                      </motion.button>
                    );
                  })}
                </div>
              ) : null}

              {step === "visible" ? (
                <label htmlFor="ob-optin" className="soft-card flex max-w-xl cursor-pointer items-start justify-between gap-6 p-6">
                  <span>
                    <span className="block text-lg font-medium text-ink">Show my skill card to employers</span>
                    <span className="mt-1 block text-sm text-ink-muted">Built from your workdays. No name, school or photo. You can turn this off any time.</span>
                  </span>
                  <Switch id="ob-optin" checked={optIn} onCheckedChange={setOptIn} />
                </label>
              ) : null}
            </div>
          </motion.section>
        </AnimatePresence>
      </div>

      <div className="mt-12 flex flex-wrap items-center gap-3">
        {i > 0 ? (
          <button type="button" onClick={() => go(-1)} className="btn-ghost">
            Back
          </button>
        ) : null}
        {last ? (
          <Magnetic>
            <button type="button" disabled={saving || !canNext} onClick={() => void finish()} className="btn-primary group">
              <TextRoll text={saving ? "Saving…" : "Take me in"} />
              <SwapArrow />
            </button>
          </Magnetic>
        ) : (
          <button type="button" disabled={!canNext} onClick={() => go(1)} className="btn-primary group">
            <TextRoll text="Continue" />
            <SwapArrow />
          </button>
        )}
        <button type="button" disabled={saving} onClick={() => void finish(true)} className="ml-auto text-sm text-ink-faint underline-offset-4 hover:text-ink hover:underline">
          Skip for now
        </button>
      </div>
    </div>
  );
}
