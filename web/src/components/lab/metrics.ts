/**
 * Readers for ml/artifacts/metrics.json blocks (served by GET /api/metrics, CONTRACTS section 10).
 *
 * Each training script read-merge-writes its own top-level key. Key spellings inside a block
 * vary between scripts ("top1" / "top_1" / "Top-1"), so lookups compare keys normalized to
 * lowercase alphanumerics. A value is returned only when it sits at one of the listed paths:
 * nothing is inferred, interpolated or defaulted. Missing -> null -> "not trained yet".
 */

export type Block = Record<string, unknown>;

export interface Picked {
  value: number;
  /** the dotted path it was read from (shown in the "all recorded values" table and tooltips) */
  path: string;
}

export function asBlock(v: unknown): Block | null {
  return v !== null && typeof v === "object" && !Array.isArray(v) ? (v as Block) : null;
}

export function finite(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

const norm = (k: string) => k.toLowerCase().replace(/[^a-z0-9]/g, "");

function child(obj: unknown, segment: string): { value: unknown; key: string } | undefined {
  const b = asBlock(obj);
  if (!b) return undefined;
  if (segment in b) return { value: b[segment], key: segment };
  const want = norm(segment);
  for (const key of Object.keys(b)) {
    if (norm(key) === want) return { value: b[key], key };
  }
  return undefined;
}

/** Value at a dotted path (segments matched on normalized keys), with the real key path. */
export function at(obj: unknown, path: string): { value: unknown; path: string } | undefined {
  let cur: unknown = obj;
  const real: string[] = [];
  for (const seg of path.split(".")) {
    const next = child(cur, seg);
    if (!next) return undefined;
    real.push(next.key);
    cur = next.value;
  }
  return { value: cur, path: real.join(".") };
}

export function pickNum(obj: unknown, paths: readonly string[]): Picked | null {
  for (const p of paths) {
    const hit = at(obj, p);
    const n = hit ? finite(hit.value) : null;
    if (hit && n !== null) return { value: n, path: hit.path };
  }
  return null;
}

export function pickStr(obj: unknown, paths: readonly string[]): string | null {
  for (const p of paths) {
    const hit = at(obj, p);
    if (hit && typeof hit.value === "string" && hit.value.trim()) return hit.value.trim();
  }
  return null;
}

export function pickBool(obj: unknown, paths: readonly string[]): boolean | null {
  for (const p of paths) {
    const hit = at(obj, p);
    if (hit && typeof hit.value === "boolean") return hit.value;
  }
  return null;
}

export function pickAny(obj: unknown, paths: readonly string[]): unknown {
  for (const p of paths) {
    const hit = at(obj, p);
    if (hit && hit.value !== undefined && hit.value !== null) return hit.value;
  }
  return undefined;
}

/** Candidate paths for (model x metric) under optional scope prefixes, nested or flattened. */
function combos(models: readonly string[], metrics: readonly string[], scopes: readonly string[]): string[] {
  const out: string[] = [];
  for (const s of scopes) {
    for (const m of models) {
      for (const k of metrics) {
        if (s) {
          out.push(`${s}.${m}.${k}`, `${m}.${s}.${k}`, `${s}.${k}.${m}`, `${k}.${s}.${m}`, `${m}.${k}.${s}`, `${s}.${m}${k}`, `${m}${s}.${k}`, `${m}${k}${s}`, `${s}${m}${k}`, `${m}.${k}${s}`, `${m}.${s}${k}`);
        } else {
          out.push(`${m}.${k}`, `${k}.${m}`, `${m}${k}`, `metrics.${m}.${k}`, `results.${m}.${k}`, `test.${m}.${k}`, `${m}.test.${k}`);
        }
      }
    }
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* Career fit                                                          */
/* ------------------------------------------------------------------ */

const OVERALL = ["", "overall", "all", "allocc", "alloccupations", "occupations"] as const;
const EIGHT = ["careers8", "8careers", "8career", "eightcareer", "eightcareers", "foothold8", "foothold", "careers", "eight", "career8"] as const;

export interface CareerFitView {
  overall: { mlpTop1: Picked | null; mlpTop3: Picked | null; cosTop1: Picked | null; cosTop3: Picked | null };
  eight: { mlpTop1: Picked | null; mlpTop3: Picked | null; cosTop1: Picked | null; cosTop3: Picked | null };
  winner: string | null;
  nTest: Picked | null;
}

export function readCareerFit(b: Block | null): CareerFitView {
  const get = (model: string[], k: string[], scopes: readonly string[]) => pickNum(b, combos(model, k, scopes));
  const MLP = ["mlp"];
  const COS = ["cosine", "cos", "cosinebaseline", "baseline"];
  const T1 = ["top1", "top1acc", "top1accuracy", "acctop1", "accuracytop1"];
  const T3 = ["top3", "top3acc", "top3accuracy", "acctop3", "accuracytop3"];
  return {
    overall: { mlpTop1: get(MLP, T1, OVERALL), mlpTop3: get(MLP, T3, OVERALL), cosTop1: get(COS, T1, OVERALL), cosTop3: get(COS, T3, OVERALL) },
    eight: { mlpTop1: get(MLP, T1, EIGHT), mlpTop3: get(MLP, T3, EIGHT), cosTop1: get(COS, T1, EIGHT), cosTop3: get(COS, T3, EIGHT) },
    winner: pickStr(b, ["winner", "overall.winner", "best"]),
    nTest: pickNum(b, ["ntest", "testn", "ncases", "neval", "testsize", "n"]),
  };
}

/* ------------------------------------------------------------------ */
/* Adaptive selector                                                   */
/* ------------------------------------------------------------------ */

export interface CurveSeries {
  name: string;
  values: (number | null)[];
}
export interface Curve {
  xs: number[];
  series: CurveSeries[];
  xLabel: string;
}

const X_KEYS = ["k", "events", "event", "step", "steps", "n", "x", "nevents"];

/** Accepts [{k, adaptive, random, fixed}], {k:[..], adaptive:[..]}, or {adaptive:[[k,v]..] | [{k,acc}..]}. */
export function parseCurve(raw: unknown): Curve | null {
  if (Array.isArray(raw) && raw.length > 1 && raw.every((r) => asBlock(r))) {
    const rows = raw as Block[];
    const xKey = Object.keys(rows[0]).find((k) => X_KEYS.includes(norm(k)));
    if (!xKey) return null;
    const names = Object.keys(rows[0]).filter((k) => k !== xKey && typeof rows[0][k] === "number");
    const xs = rows.map((r) => finite(r[xKey]));
    if (xs.some((x) => x === null) || names.length === 0) return null;
    return { xs: xs as number[], series: names.map((n) => ({ name: n, values: rows.map((r) => finite(r[n])) })), xLabel: xKey };
  }
  const b = asBlock(raw);
  if (!b) return null;
  const keys = Object.keys(b);
  const xKey = keys.find((k) => X_KEYS.includes(norm(k)) && Array.isArray(b[k]));
  if (xKey) {
    const xsRaw = (b[xKey] as unknown[]).map(finite);
    if (xsRaw.some((x) => x === null) || xsRaw.length < 2) return null;
    const series = keys
      .filter((k) => k !== xKey && Array.isArray(b[k]) && (b[k] as unknown[]).length === xsRaw.length)
      .map((k) => ({ name: k, values: (b[k] as unknown[]).map(finite) }))
      .filter((s) => s.values.some((v) => v !== null));
    return series.length ? { xs: xsRaw as number[], series, xLabel: xKey } : null;
  }
  // {series: [[k, v], ...]} or {series: [{k, acc}, ...]}
  const series: { name: string; pts: [number, number][] }[] = [];
  for (const k of keys) {
    const arr = b[k];
    if (!Array.isArray(arr) || arr.length < 2) continue;
    const pts: [number, number][] = [];
    for (const p of arr) {
      if (Array.isArray(p) && p.length >= 2 && finite(p[0]) !== null && finite(p[1]) !== null) pts.push([p[0] as number, p[1] as number]);
      else if (asBlock(p)) {
        const pb = p as Block;
        const xk = Object.keys(pb).find((kk) => X_KEYS.includes(norm(kk)));
        const yk = Object.keys(pb).find((kk) => kk !== xk && typeof pb[kk] === "number");
        if (xk && yk && finite(pb[xk]) !== null && finite(pb[yk]) !== null) pts.push([pb[xk] as number, pb[yk] as number]);
      }
    }
    if (pts.length >= 2) series.push({ name: k, pts });
  }
  if (!series.length) return null;
  const xs = Array.from(new Set(series.flatMap((s) => s.pts.map((p) => p[0])))).sort((a, c) => a - c);
  return {
    xs,
    series: series.map((s) => ({ name: s.name, values: xs.map((x) => s.pts.find((p) => p[0] === x)?.[1] ?? null) })),
    xLabel: "k",
  };
}

export interface SelectorView {
  adaptive: Picked | null;
  random: Picked | null;
  fixed: Picked | null;
  curve: Curve | null;
  threshold: Picked | null;
  nPlayers: Picked | null;
}

export function readSelector(b: Block | null): SelectorView {
  const E = ["avgeventstoconfident", "eventstoconfident", "meaneventstoconfident", "avgevents", "meanevents", "events"];
  const strat = (s: string[]) => pickNum(b, [...combos(s, E, [""]), ...s]);
  return {
    adaptive: strat(["adaptive", "infogain", "adaptiveinfogain"]),
    random: strat(["random"]),
    fixed: strat(["fixed", "fixedorder", "static"]),
    curve: parseCurve(pickAny(b, ["curve", "accuracyafterk", "accafterk", "curves", "accuracycurve"])),
    threshold: pickNum(b, ["confidencethreshold", "threshold", "confidentat", "confidence"]),
    nPlayers: pickNum(b, ["nplayers", "nsimulated", "nsims", "ncases", "nruns", "n"]),
  };
}

/* ------------------------------------------------------------------ */
/* Graph recommender                                                   */
/* ------------------------------------------------------------------ */

export type RecModel = "gnn" | "mf" | "pop";
export type RecScope = "overall" | "cold";
export type RecMetric = "recall" | "ndcg";

const REC_MODELS: Record<RecModel, string[]> = {
  gnn: ["gnn", "graphsage", "sage", "gcn", "lightgcn"],
  mf: ["mf", "matrixfactorization", "als", "bpr"],
  pop: ["popularity", "pop", "popular", "mostpopular"],
};
const REC_METRICS: Record<RecMetric, string[]> = {
  recall: ["recall10", "recallat10", "recall"],
  ndcg: ["ndcg10", "ndcgat10", "ndcg"],
};
const REC_SCOPES: Record<RecScope, readonly string[]> = {
  overall: ["", "overall", "all", "test"],
  cold: ["coldstart", "cold", "coldstartlearners", "coldusers"],
};

export function readRecommender(b: Block | null) {
  const value = (m: RecModel, k: RecMetric, s: RecScope) => {
    // train_recommender.py writes {model}.{warm|cold}.all.{recall@10|ndcg@10}
    const direct = REC_MODELS[m].map((mm) => `${mm}.${s === "overall" ? "warm" : "cold"}.all.${k === "recall" ? "recall10" : "ndcg10"}`);
    return pickNum(b, [...direct, ...combos(REC_MODELS[m], REC_METRICS[k], REC_SCOPES[s])]);
  };
  return {
    value,
    modelType: pickStr(b, ["modeltype", "gnn.modeltype", "architecture", "gnntype"]),
    winnerWarm: pickStr(b, ["winner.warm", "winner"]),
    winnerCold: pickStr(b, ["winner.cold"]),
    coldDefinition: pickStr(b, ["colddefinition", "coldstartdefinition", "coldstart.definition", "colddef"]),
  };
}

/* ------------------------------------------------------------------ */
/* Planner                                                             */
/* ------------------------------------------------------------------ */

export function readPlanner(b: Block | null) {
  const F = ["feasibility", "feasible", "feasiblerate", "feasibilityrate"];
  const feas = (m: string[]) => pickNum(b, [...combos(m, F, [""]), ...m.flatMap((x) => [`feasibility.${x}`, `feasiblerate.${x}`])]);
  const P50 = ["solvems.p50", "solvemsp50", "cpsat.solvems.p50", "solvems.cpsat.p50", "cpsat.solvemsp50", "p50ms", "solve.p50ms", "solvetimems.p50"];
  const P95 = P50.map((p) => p.replace(/50/g, "95"));
  return {
    cpsat: feas(["cpsat", "cp_sat", "ortools"]),
    greedy: feas(["greedy"]),
    p50: pickNum(b, P50),
    p95: pickNum(b, P95),
    months: pickNum(b, ["improvementwhenbothfeasible.monthssavedmean", "monthsimprovement", "improvement.months", "monthssaved", "avgmonthssaved", "meanmonthssaved", "months.improvement", "monthsimprovementmean"]),
    cost: pickNum(b, ["improvementwhenbothfeasible.costsavedmeanusd", "costimprovement", "improvement.cost", "costsaved", "avgcostsavedusd", "costsavedusd", "meancostsaved", "cost.improvement", "costimprovementusd", "improvement.costusd"]),
    nCases: pickNum(b, ["ncases", "n", "cases"]),
  };
}

/* ------------------------------------------------------------------ */
/* Fairness                                                            */
/* ------------------------------------------------------------------ */

export interface GroupRate {
  group: string;
  rate: number;
  n: number | null;
}

export function parseRates(raw: unknown): GroupRate[] {
  if (Array.isArray(raw)) {
    return raw
      .map((r) => {
        const b = asBlock(r);
        if (!b) return null;
        const group = pickStr(b, ["group", "name", "label", "id"]);
        const rate = pickNum(b, ["rate", "selectionrate", "selected_rate", "value"]);
        return group && rate ? { group, rate: rate.value, n: pickNum(b, ["n", "count", "size"])?.value ?? null } : null;
      })
      .filter((x): x is GroupRate => x !== null);
  }
  const b = asBlock(raw);
  if (!b) return [];
  return Object.entries(b)
    .map(([group, v]) => {
      const direct = finite(v);
      if (direct !== null) return { group, rate: direct, n: null };
      const inner = asBlock(v);
      const rate = inner ? pickNum(inner, ["rate", "selectionrate", "value"]) : null;
      return rate ? { group, rate: rate.value, n: pickNum(inner, ["n", "count", "size"])?.value ?? null } : null;
    })
    .filter((x): x is GroupRate => x !== null);
}

export function readFairness(b: Block | null) {
  return {
    rates: parseRates(pickAny(b, ["selectionrates", "selectionratesbygroup", "rates", "groups", "bygroup"])),
    minImpactRatio: pickNum(b, ["minimpactratio", "impactratio", "minratio", "impact_ratio_min"]),
    passes: pickBool(b, ["passesfourfifths", "passes", "fourfifths.passes", "passesfourfifthsrule"]),
    note: pickStr(b, ["note", "limitation", "notes", "caveat"]),
    k: pickNum(b, ["k", "topk", "selected"]),
  };
}

/* ------------------------------------------------------------------ */
/* Verifier                                                            */
/* ------------------------------------------------------------------ */

export function readVerifier(b: Block | null) {
  return {
    nCases: pickNum(b, ["ncases", "n", "cases"]),
    catchRate: pickNum(b, ["catchrate", "recall", "caught"]),
    falsePositiveRate: pickNum(b, ["falsepositiverate", "fpr", "falsepositives"]),
  };
}

/* ------------------------------------------------------------------ */
/* Generic                                                             */
/* ------------------------------------------------------------------ */

export interface Leaf {
  path: string;
  value: string;
}

const META_KEYS = new Set(["status", "provenance", "data", "seed", "trainedat", "reproduce", "note"]);

/** Every scalar recorded in a block, for the "all recorded values" table (arrays summarized). */
export function leaves(b: Block | null, prefix = "", depth = 0, out: Leaf[] = []): Leaf[] {
  if (!b || depth > 5) return out;
  for (const [k, v] of Object.entries(b)) {
    if (!prefix && META_KEYS.has(norm(k))) continue;
    const path = prefix ? `${prefix}.${k}` : k;
    if (typeof v === "number") out.push({ path, value: Number.isInteger(v) ? String(v) : String(Number(v.toPrecision(6))) });
    else if (typeof v === "boolean") out.push({ path, value: v ? "true" : "false" });
    else if (typeof v === "string" && v.length <= 80) out.push({ path, value: v });
    else if (Array.isArray(v)) out.push({ path, value: `[${v.length} values]` });
    else if (asBlock(v)) leaves(v as Block, path, depth + 1, out);
  }
  return out;
}

/** 0..1 -> percent with one decimal; values already in 1..100 are shown as percent as-is. */
export function isFraction(values: (number | null | undefined)[]): boolean {
  const xs = values.filter((v): v is number => typeof v === "number");
  return xs.length > 0 && xs.every((v) => v >= 0 && v <= 1);
}

export function blockText(b: Block | null, key: string): string | null {
  if (!b) return null;
  const v = at(b, key)?.value;
  if (typeof v === "string") return v;
  if (v && typeof v === "object") {
    const parts = Object.entries(v as Block)
      .filter(([, x]) => typeof x === "string" || typeof x === "number")
      .map(([k, x]) => `${k.replace(/_/g, " ")}: ${x}`);
    return parts.length ? parts.join(" · ") : null;
  }
  return null;
}
