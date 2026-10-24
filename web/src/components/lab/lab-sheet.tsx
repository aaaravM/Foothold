"use client";

import * as React from "react";
import { MonoLabel } from "@/components/foothold/mono-label";
import { ProvenanceBadge } from "@/components/foothold/provenance-badge";
import { NotTrainedYet } from "@/components/foothold/metric-value";
import { useApiResource } from "./use-api";
import {
  asBlock,
  blockText,
  isFraction,
  leaves,
  pickStr,
  readCareerFit,
  readFairness,
  readPlanner,
  readRecommender,
  readSelector,
  readVerifier,
  type Block,
  type Picked,
} from "./metrics";
import { AsideBlock, DetailFrame, Readout, RecordedValues, ReproduceCommand, type FrameStatus } from "./frame";
import { BarCompare, LineCurve, fmtValue } from "./charts";

type Metrics = Record<string, unknown>;

interface InventoryModel {
  key: string;
  script: string;
  script_exists: boolean;
  in_metrics: boolean;
  reproduce: string | null;
}
interface InventoryDataset {
  id: string;
  label: string;
  rows: number;
  exists: boolean;
  group_count?: number;
}
interface Inventory {
  generated_at: string;
  models: InventoryModel[];
  datasets: InventoryDataset[];
}

type Prov = "REAL" | "SAMPLE" | "SYNTHETIC" | "FICTIONAL";

function provOf(b: Block | null): Prov | null {
  const raw = pickStr(b, ["provenance", "provenance.status", "status_label"]);
  if (!raw) return null;
  const up = raw.toUpperCase();
  if (up.includes("SYNTH")) return "SYNTHETIC";
  if (up.includes("REAL") || up.includes("DERIVED")) return "REAL";
  if (up.includes("SAMPLE")) return "SAMPLE";
  if (up.includes("FICTION")) return "FICTIONAL";
  return null;
}

function statusFor(state: string, values: (Picked | null | undefined)[]): FrameStatus {
  if (state === "loading") return "loading";
  if (state === "offline") return "offline";
  const have = values.filter(Boolean).length;
  if (have === 0) return "not_trained";
  return have === values.length ? "trained" : "partial";
}

const v = (p: Picked | null) => (p ? p.value : null);

function Value({ p, percent, digits = 1, suffix }: { p: Picked | null; percent?: boolean; digits?: number; suffix?: string }) {
  if (!p) return <NotTrainedYet />;
  return (
    <span className="tabular-nums" title={`metrics.json: ${p.path}`}>
      {fmtValue(p.value, !!percent, digits)}
      {suffix ? <span className="ml-1 text-[0.45em] text-ink-muted">{suffix}</span> : null}
    </span>
  );
}

function FrameFooter({ block, model, keyName }: { block: Block | null; model: InventoryModel | undefined; keyName: string }) {
  // scripts sometimes record the absolute interpreter path; show the portable command
  const fromMetrics = pickStr(block, ["reproduce"])?.replace(/^\S*python(\.exe)?(?=\s)/i, "python") ?? null;
  const command = fromMetrics ?? (model?.script_exists ? `python ${model.script}` : null);
  const trainedAt = pickStr(block, ["trained_at"]);
  const seed = block && typeof block.seed === "number" ? block.seed : null;
  const meta = [trainedAt ? `trained ${trainedAt.slice(0, 16).replace("T", " ")}` : null, seed !== null ? `seed ${seed}` : null].filter(Boolean).join(" · ");
  return (
    <>
      <ReproduceCommand
        command={command}
        pending={model ? `${model.script} has not been written yet.` : "The training script has not been written yet."}
        meta={meta || undefined}
      />
      <RecordedValues rows={leaves(block)} source={`ml/artifacts/metrics.json → ${keyName}`} />
    </>
  );
}

function DataNote({ block }: { block: Block | null }) {
  const text = blockText(block, "data");
  return <AsideBlock term="Training data">{text ?? "Recorded with the metrics once the script runs."}</AsideBlock>;
}

export function LabSheet() {
  const metrics = useApiResource<Metrics>("/api/metrics", { pollMs: 30_000 });
  const inventory = useApiResource<Inventory>("/api/lab/inventory", { pollMs: 60_000 });
  const m = metrics.data ?? {};
  const state = metrics.state;
  const model = (k: string) => inventory.data?.models.find((x) => x.key === k);
  const block = (k: string) => asBlock(m[k]);

  const cfB = block("career_fit");
  const cf = readCareerFit(cfB);
  const selB = block("selector");
  const sel = readSelector(selB);
  const recB = block("recommender");
  const rec = readRecommender(recB);
  const plB = block("planner");
  const pl = readPlanner(plB);
  const faB = block("fairness");
  const fa = readFairness(faB);
  const veB = block("verifier");
  const ve = readVerifier(veB);

  const traits = inventory.data?.datasets.find((d) => d.id === "traits");
  const badge = (b: Block | null, fallback: Prov) => <ProvenanceBadge status={provOf(b) ?? fallback} />;
  const recPct = isFraction([v(rec.value("gnn", "recall", "overall")), v(rec.value("mf", "recall", "overall"))]);

  return (
    <div className="space-y-10">
      {state === "offline" ? (
        <p role="status" className="border border-warning/50 px-4 py-3 text-sm text-warning">
          API offline: the Lab reads every number live from the Foothold API, so nothing is shown until it is reachable.
        </p>
      ) : null}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <p className="max-w-[62ch] text-[17px] leading-relaxed text-ink-muted lg:col-span-8">
          Six models sit behind the sheets. Each frame says what it was trained on, how it was measured against a plain baseline, and the
          command that rebuilds the number. Values are read live from <code className="font-mono text-[0.9em] text-ink">ml/artifacts/metrics.json</code>; a
          model that has not been trained shows &ldquo;not trained yet&rdquo;, never a placeholder.
        </p>
        <aside className="border-l border-line pl-4 lg:col-span-4">
          <MonoLabel as="p" tone="accent">
            Note 1
          </MonoLabel>
          <p className="mt-1 text-sm text-ink-muted">
            O*NET 31.0 replaced the 16 classic work styles with 21. Foothold&rsquo;s trait vectors use all 21
            {traits?.exists ? ` (${traits.rows} rows loaded from traits.json)` : ""}.
          </p>
        </aside>
      </div>

      {/* A: career fit */}
      <DetailFrame
        id="career-fit"
        letter="A"
        sheet="06"
        title="Career fit"
        kicker="MLP vs cosine baseline"
        usedOn={{ label: "Sim · fit result", href: "/sim" }}
        status={statusFor(state, [cf.overall.mlpTop1, cf.overall.cosTop1, cf.overall.mlpTop3, cf.overall.cosTop3])}
        badges={badge(cfB, "SYNTHETIC")}
        aside={
          <>
            <AsideBlock term="What it does">
              Maps the 21 work-style scores a workday reveals to the occupations whose O*NET profiles they match best.
            </AsideBlock>
            <DataNote block={cfB} />
            <AsideBlock term="How it is measured">Top-1 and top-3 accuracy on held-out practice players against a cosine-similarity baseline.</AsideBlock>
          </>
        }
        footer={<FrameFooter block={cfB} model={model("career_fit")} keyName="career_fit" />}
      >
        <div className="grid gap-6 sm:grid-cols-2">
          <Readout label="MLP top-1" emphasis>
            <Value p={cf.overall.mlpTop1} percent />
          </Readout>
          <Readout label="Cosine top-1">
            <Value p={cf.overall.cosTop1} percent />
          </Readout>
        </div>
        <BarCompare
          caption="Accuracy (held-out)"
          percent
          max={1}
          rows={[
            { label: "MLP top-1", value: v(cf.overall.mlpTop1), primary: true },
            { label: "Cosine top-1", value: v(cf.overall.cosTop1) },
            { label: "MLP top-3", value: v(cf.overall.mlpTop3), primary: true },
            { label: "Cosine top-3", value: v(cf.overall.cosTop3) },
          ]}
        />
        {cf.eight.mlpTop1 || cf.eight.cosTop1 ? (
          <BarCompare
            caption="The 8 Foothold careers only"
            percent
            max={1}
            rows={[
              { label: "MLP top-1", value: v(cf.eight.mlpTop1), primary: true },
              { label: "Cosine top-1", value: v(cf.eight.cosTop1) },
              { label: "MLP top-3", value: v(cf.eight.mlpTop3), primary: true },
              { label: "Cosine top-3", value: v(cf.eight.cosTop3) },
            ]}
          />
        ) : null}
        <p className="label-mono text-ink-faint">
          {[cf.winner ? `Winner: ${cf.winner}` : null, cf.nTest ? `n test = ${cf.nTest.value.toLocaleString("en-US")}` : null, pickStr(cfB, ["model_type"])].filter(Boolean).join(" · ")}
        </p>
        {pickStr(cfB, ["note"]) ? <p className="border-l-2 border-line-strong pl-3 text-sm text-ink-muted">{pickStr(cfB, ["note"])}</p> : null}
      </DetailFrame>

      {/* B: adaptive selector */}
      <DetailFrame
        id="selector"
        letter="B"
        sheet="06"
        title="Adaptive event selector"
        kicker="Information gain vs random vs fixed order"
        usedOn={{ label: "Sim · next event", href: "/sim" }}
        status={statusFor(state, [sel.adaptive, sel.random, sel.fixed])}
        badges={badge(selB, "SYNTHETIC")}
        aside={
          <>
            <AsideBlock term="What it does">Picks the next workday event that tells the fit model the most, so a shift stays short.</AsideBlock>
            <DataNote block={selB} />
            <AsideBlock term="How it is measured">
              Average events until the fit model is confident, over simulated players{sel.nPlayers ? ` (n = ${sel.nPlayers.value})` : ""}; plus accuracy after k events.
            </AsideBlock>
          </>
        }
        footer={<FrameFooter block={selB} model={model("selector")} keyName="selector" />}
      >
        <div className="grid gap-6 sm:grid-cols-3">
          <Readout label="Adaptive" emphasis sub="events to confident">
            <Value p={sel.adaptive} />
          </Readout>
          <Readout label="Random" sub="events to confident">
            <Value p={sel.random} />
          </Readout>
          <Readout label="Fixed order" sub="events to confident">
            <Value p={sel.fixed} />
          </Readout>
        </div>
        {sel.curve ? (
          <LineCurve curve={sel.curve} percent={isFraction(sel.curve.series.flatMap((s) => s.values))} yLabel="Accuracy" />
        ) : (
          <div className="space-y-1">
            <MonoLabel as="p">Accuracy after k events</MonoLabel>
            <NotTrainedYet />
          </div>
        )}
      </DetailFrame>

      {/* C: recommender */}
      <DetailFrame
        id="recommender"
        letter="C"
        sheet="06"
        title="Graph recommender"
        kicker={`${rec.modelType ?? "GNN"} vs matrix factorization vs popularity`}
        usedOn={{ label: "Graph · recommendations", href: "/graph" }}
        status={statusFor(state, [rec.value("gnn", "recall", "overall"), rec.value("mf", "recall", "overall"), rec.value("pop", "recall", "overall")])}
        badges={badge(recB, "SYNTHETIC")}
        aside={
          <>
            <AsideBlock term="What it does">Ranks courses and jobs for a learner from the learner, skill, course and job graph.</AsideBlock>
            <DataNote block={recB} />
            <AsideBlock term="How it is measured">
              Recall@10 and NDCG@10 on held-out links, overall and for cold-start learners{rec.coldDefinition ? ` (${rec.coldDefinition})` : ""}.
            </AsideBlock>
          </>
        }
        footer={<FrameFooter block={recB} model={model("recommender")} keyName="recommender" />}
      >
        <div className="grid gap-8 md:grid-cols-2">
          {(["overall", "cold"] as const).map((scope) => (
            <div key={scope} className="space-y-6">
              <MonoLabel as="p" tone="muted">
                {scope === "overall" ? "Warm learners (all items)" : "Cold-start learners (all items)"}
              </MonoLabel>
              {(["recall", "ndcg"] as const).map((metric) => (
                <BarCompare
                  key={metric}
                  caption={metric === "recall" ? "Recall@10" : "NDCG@10"}
                  percent={recPct}
                  max={recPct ? 1 : undefined}
                  rows={[
                    { label: rec.modelType ?? "GNN", value: v(rec.value("gnn", metric, scope)), primary: true },
                    { label: "Matrix fact.", value: v(rec.value("mf", metric, scope)) },
                    { label: "Popularity", value: v(rec.value("pop", metric, scope)) },
                  ]}
                />
              ))}
            </div>
          ))}
        </div>
        {rec.winnerWarm || rec.winnerCold ? (
          <p className="border-l-2 border-line-strong pl-3 text-sm text-ink-muted">
            Best on this test set: {rec.winnerWarm ? `${rec.winnerWarm} for warm learners` : ""}
            {rec.winnerWarm && rec.winnerCold ? ", " : ""}
            {rec.winnerCold ? `${rec.winnerCold} for cold-start learners` : ""}. Reported as measured, including where a simpler baseline wins.
          </p>
        ) : null}
      </DetailFrame>

      {/* D: planner */}
      <DetailFrame
        id="planner"
        letter="D"
        sheet="06"
        title="Pathway planner"
        kicker="CP-SAT solver vs greedy"
        usedOn={{ label: "Path · plan", href: "/path" }}
        status={statusFor(state, [pl.cpsat, pl.greedy, pl.p50])}
        badges={badge(plB, "SYNTHETIC")}
        aside={
          <>
            <AsideBlock term="What it does">
              Schedules program steps under hard limits on hours, budget, commute and dependents. CP-SAT returns a plan that satisfies every constraint or proves none exists.
            </AsideBlock>
            <DataNote block={plB} />
            <AsideBlock term="How it is measured">
              Feasibility rate and plan quality against a greedy scheduler on generated cases{pl.nCases ? ` (n = ${pl.nCases.value})` : ""}; solve time p50 and p95.
            </AsideBlock>
          </>
        }
        footer={<FrameFooter block={plB} model={model("planner")} keyName="planner" />}
      >
        <BarCompare
          caption="Feasible plans found"
          percent={isFraction([v(pl.cpsat), v(pl.greedy)])}
          max={isFraction([v(pl.cpsat), v(pl.greedy)]) ? 1 : undefined}
          rows={[
            { label: "CP-SAT", value: v(pl.cpsat), primary: true },
            { label: "Greedy", value: v(pl.greedy) },
          ]}
        />
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <Readout label="Solve p50">
            <Value p={pl.p50} digits={0} suffix="ms" />
          </Readout>
          <Readout label="Solve p95">
            <Value p={pl.p95} digits={0} suffix="ms" />
          </Readout>
          <Readout label="Months saved" sub="vs greedy, mean">
            <Value p={pl.months} />
          </Readout>
          <Readout label="Cost saved" sub="vs greedy, mean">
            {pl.cost ? <span className="tabular-nums">${Math.round(pl.cost.value).toLocaleString("en-US")}</span> : <NotTrainedYet />}
          </Readout>
        </div>
      </DetailFrame>

      {/* E: fairness */}
      <DetailFrame
        id="fairness"
        letter="E"
        sheet="06"
        title="Fairness audit"
        kicker="Selection rates by group"
        usedOn={{ label: "Employers · fairness", href: "/employers" }}
        status={statusFor(state, [fa.minImpactRatio, fa.rates.length ? { value: 1, path: "rates" } : null])}
        badges={badge(faB, "SYNTHETIC")}
        aside={
          <>
            <AsideBlock term="What it does">Checks whether blind talent ranking surfaces each group at similar rates (the four-fifths rule).</AsideBlock>
            <DataNote block={faB} />
            <AsideBlock term="Limitation">
              {fa.note ??
                "Group labels are assigned for testing only. Passing here says the ranking code treats these groups alike; it says nothing about real applicants."}
            </AsideBlock>
          </>
        }
        footer={<FrameFooter block={faB} model={model("fairness")} keyName="fairness" />}
      >
        <div className="grid gap-6 sm:grid-cols-2">
          <Readout label="Minimum impact ratio" emphasis sub="0.80 or higher passes the four-fifths rule">
            <Value p={fa.minImpactRatio} digits={1} />
          </Readout>
          <Readout label="Four-fifths rule">{fa.passes === null ? <NotTrainedYet /> : fa.passes ? "Passes" : "Fails"}</Readout>
        </div>
        {fa.rates.length ? (
          <BarCompare
            caption={`Selection rate by group${fa.k ? ` (top ${fa.k.value})` : ""}`}
            percent={isFraction(fa.rates.map((r) => r.rate))}
            max={isFraction(fa.rates.map((r) => r.rate)) ? 1 : undefined}
            rows={fa.rates.map((r) => ({ label: r.group, value: r.rate, sub: r.n !== null ? `n = ${r.n}` : undefined }))}
          />
        ) : (
          <div className="space-y-1">
            <MonoLabel as="p">Selection rate by group</MonoLabel>
            <NotTrainedYet />
          </div>
        )}
      </DetailFrame>

      {/* F: verifier */}
      <DetailFrame
        id="verifier"
        letter="F"
        sheet="06"
        title="Claim verifier"
        kicker="Every number an agent says, checked against data"
        usedOn={{ label: "Path · agent notes", href: "/path" }}
        status={statusFor(state, [ve.catchRate, ve.falsePositiveRate])}
        badges={badge(veB, "SYNTHETIC")}
        aside={
          <>
            <AsideBlock term="What it does">
              Pulls numbers (wages, costs, hours, months) out of agent text and compares each with the source data within a set tolerance. Unsupported claims are flagged before you see them.
            </AsideBlock>
            <DataNote block={veB} />
            <AsideBlock term="How it is measured">
              Seeded wrong numbers vs correct ones{ve.nCases ? ` (n = ${ve.nCases.value})` : ""}: catch rate and false-positive rate.
            </AsideBlock>
          </>
        }
        footer={<FrameFooter block={veB} model={model("verifier")} keyName="verifier" />}
      >
        <div className="grid gap-6 sm:grid-cols-2">
          <Readout label="Catch rate" emphasis sub="wrong numbers flagged">
            <Value p={ve.catchRate} percent />
          </Readout>
          <Readout label="False positives" sub="correct numbers flagged">
            <Value p={ve.falsePositiveRate} percent />
          </Readout>
        </div>
      </DetailFrame>

      {inventory.data ? (
        <p className="label-mono text-ink-faint">
          Inventory read {inventory.data.generated_at.replace("T", " ").slice(0, 19)} UTC · {inventory.data.models.filter((x) => x.in_metrics).length} of{" "}
          {inventory.data.models.length} models recorded
        </p>
      ) : null}
    </div>
  );
}
