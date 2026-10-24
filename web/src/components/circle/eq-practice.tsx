"use client";

import * as React from "react";
import { MonoLabel } from "@/components/foothold/mono-label";
import { StatBar } from "@/components/foothold/stat-bar";
import { FictionalTag } from "@/components/foothold/fictional-tag";
import { postJSON } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ErrorNote, errorText, inputClass, primaryButtonClass, usePolling } from "@/components/employers/shared";
import { CrisisPanel, type CrisisPayload } from "./crisis-panel";

interface Scenario {
  id: string;
  title: string;
  situation?: string;
  setup?: string;
  prompt?: string;
  persona_line?: string;
  text?: string;
  counterpart?: string;
  skills?: string[];
}
interface RubricDim {
  id: string;
  label: string;
  anchors: Record<string, string>;
}
interface ScenariosResponse {
  scenarios: Scenario[];
  rubric: RubricDim[];
  fallback: boolean;
}
type Feedback =
  | ({ crisis: true; crisis_payload: CrisisPayload } & Record<string, unknown>)
  | {
      crisis: false;
      scenario_id: string;
      scores: Record<string, number>;
      strength: string;
      try_next: string;
      feedback: string;
      rubric: RubricDim[];
      llm: string;
      method: string;
    };

const ORDER = ["listening", "empathy", "assertiveness", "repair"];

export function EqPractice() {
  const sc = usePolling<ScenariosResponse>("/api/circle/eq/scenarios", 0);
  const [scenarioId, setScenarioId] = React.useState<string>("");
  const [response, setResponse] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<Feedback | null>(null);

  const scenarios = sc.data?.scenarios ?? [];
  const current = scenarios.find((s) => s.id === scenarioId) ?? scenarios[0];

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!current || !response.trim() || busy) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await postJSON<Feedback>("/api/circle/eq/feedback", { scenario_id: current.id, response: response.trim() }, { timeoutMs: 45_000 }));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  if (sc.error && !sc.data) return <ErrorNote>{sc.error}</ErrorNote>;
  if (!sc.data) return <MonoLabel as="p">Loading practice scenarios…</MonoLabel>;

  const rubric = result && !result.crisis ? result.rubric : sc.data.rubric;

  return (
    <div className="grid gap-4">
      <div className="grid gap-1.5">
        <label htmlFor="eq-scenario" className="text-sm font-medium text-ink">
          Scenario
        </label>
        <select
          id="eq-scenario"
          className={cn(inputClass, "h-10 py-0")}
          value={current?.id ?? ""}
          onChange={(e) => {
            setScenarioId(e.target.value);
            setResult(null);
          }}
        >
          {scenarios.map((s) => (
            <option key={s.id} value={s.id}>
              {s.title}
            </option>
          ))}
        </select>
      </div>
      {current ? (
        <div className="grid gap-2 border border-line bg-bg p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            {current.counterpart ? <MonoLabel>With {current.counterpart}</MonoLabel> : <span />}
            <FictionalTag compact />
          </div>
          <p className="text-sm text-ink">{current.setup ?? current.situation ?? current.text}</p>
          {current.persona_line ? <p className="border-l-2 border-line-strong pl-3 text-sm text-ink-muted">{current.persona_line}</p> : null}
          {current.prompt ? <p className="text-sm font-medium text-ink">{current.prompt}</p> : null}
        </div>
      ) : null}
      <form onSubmit={submit} className="grid gap-2">
        <label htmlFor="eq-response" className="text-sm font-medium text-ink">
          What would you say?
        </label>
        <textarea id="eq-response" className={cn(inputClass, "min-h-24")} value={response} maxLength={1500} onChange={(e) => setResponse(e.target.value)} />
        <button type="submit" className={cn(primaryButtonClass, "w-fit")} disabled={busy || !response.trim()}>
          {busy ? "Scoring…" : "Get feedback"}
        </button>
      </form>
      {error ? <ErrorNote>{error}</ErrorNote> : null}
      {result?.crisis ? <CrisisPanel payload={result.crisis_payload} /> : null}
      {result && !result.crisis ? (
        <div className="grid gap-3 border border-line p-4" aria-live="polite">
          <div className="grid gap-2.5">
            {ORDER.map((id) => {
              const dim = rubric.find((d) => d.id === id);
              const v = result.scores[id] ?? 0;
              return (
                <StatBar
                  key={id}
                  label={dim?.label ?? id}
                  value={v}
                  max={4}
                  tone={v >= 3 ? "success" : v === 2 ? "warning" : "danger"}
                  valueText={`${v} / 4`}
                />
              );
            })}
          </div>
          <p className="text-sm text-ink">
            <span className="font-medium">Strength: </span>
            {result.strength}
          </p>
          <p className="text-sm text-ink">
            <span className="font-medium">Try next: </span>
            {result.try_next}
          </p>
          <p className="text-sm text-ink-muted">{result.feedback}</p>
          <MonoLabel as="p">{result.method}</MonoLabel>
        </div>
      ) : null}
    </div>
  );
}
