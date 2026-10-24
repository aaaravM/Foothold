"""Four-fifths audit over synthetic postings (brief 6.5).

For one posting per career (the first job in data/processed/jobs.json for that career, plus every
job of the demo employer's hiring career), rank the SYNTHETIC talent pool by blind skill match +
recommender score (group label never used), select the top N, and compare selection rates by
synthetic group with the four-fifths rule.

Run:  C:/Users/MUTTA/.venvs/foothold/Scripts/python.exe ml/audit_fairness.py
Writes the "fairness" key of ml/artifacts/metrics.json.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, now_iso, seed_everything, write_metrics  # noqa: E402

from foothold import data, fairness  # noqa: E402

SEED = 7
TOP_N = 15


def postings() -> list[dict]:
    jobs = json.loads((ROOT / "data" / "processed" / "jobs.json").read_text(encoding="utf-8"))
    jobs = jobs if isinstance(jobs, list) else jobs.get("jobs", [])
    seen, out = set(), []
    for j in jobs:
        if j.get("career_id") not in seen and len(j.get("required_skills") or []) >= 3:
            seen.add(j["career_id"])
            out.append(j)
    return out


def main() -> None:
    seed_everything(SEED)
    pool = data.talent_pool()
    groups = Counter(c.get("group") for c in pool)
    rows = []
    for j in postings():
        for use_rec in (True, False):
            r = fairness.audit_posting(j["required_skills"], top_n=TOP_N, pool=pool, use_recommender=use_rec,
                                       posting={"job_id": j["id"], "title": j["title"], "career_id": j["career_id"]})
            rows.append({"job_id": j["id"], "title": j["title"], "career_id": j["career_id"],
                         "ranker": "skill_match+recommender" if use_rec else "skill_match_only",
                         "recommender_used": r["recommender_used"], "rates": r["rates"],
                         "min_impact_ratio": r["min_impact_ratio"], "passes_four_fifths": r["passes_four_fifths"],
                         "lowest_group": r["lowest_group"], "highest_group": r["highest_group"],
                         "p_value": r.get("p_value")})
    summary = {}
    for ranker in ("skill_match+recommender", "skill_match_only"):
        rs = [x for x in rows if x["ranker"] == ranker and x["min_impact_ratio"] is not None]
        summary[ranker] = {
            "n_postings": len(rs),
            "n_pass": sum(1 for x in rs if x["passes_four_fifths"]),
            "min_impact_ratio": min((x["min_impact_ratio"] for x in rs), default=None),
            "median_impact_ratio": sorted(x["min_impact_ratio"] for x in rs)[len(rs) // 2] if rs else None,
            "n_fail_significant_p05": sum(1 for x in rs if not x["passes_four_fifths"] and (x["p_value"] or 1) < 0.05),
        }
    main_rows = [x for x in rows if x["ranker"] == "skill_match+recommender"]
    agg_sel = Counter()
    for x in main_rows:
        for g, v in x["rates"].items():
            agg_sel[g] += v["selected"]
    n_post = len(main_rows)
    pooled_rates = {g: round(agg_sel[g] / (groups[g] * n_post), 4) for g in sorted(agg_sel) if groups[g]}
    hi = max(pooled_rates.values()) if pooled_rates else 0
    block = {
        "status": "audited", "provenance": "SYNTHETIC", "seed": SEED, "trained_at": now_iso(),
        "data": {"pool": len(pool), "groups": dict(sorted((str(k), v) for k, v in groups.items())),
                 "postings": n_post, "top_n": TOP_N, "source": "data/processed/synthetic/talent_pool.json + jobs.json"},
        "reproduce": "C:/Users/MUTTA/.venvs/foothold/Scripts/python.exe ml/audit_fairness.py",
        "method": fairness.METHOD, "min_group_size": fairness.MIN_GROUP_SIZE,
        "ranking_inputs": "blind demonstrated skills (0.7) + recommender score (0.3); group label never used",
        "selection_rates_by_group": pooled_rates,
        "min_impact_ratio": summary["skill_match+recommender"]["min_impact_ratio"],
        "pooled_impact_ratio": round(min(pooled_rates.values()) / hi, 4) if hi else None,
        "passes_four_fifths": (summary["skill_match+recommender"]["n_pass"] == summary["skill_match+recommender"]["n_postings"]),
        "summary": summary, "postings": rows,
        "note": fairness.NOTE,
        "interpretation": ("With a top-15 shortlist from 150 candidates (groups of 53/61/36), each group expects only "
                           "about 4-6 selections, so one or two candidates swing the per-posting ratio; the chi-square "
                           "p-value shows whether a failure is distinguishable from chance. The pooled ratio aggregates "
                           "all postings."),
    }
    write_metrics("fairness", block)
    print(json.dumps({k: block[k] for k in ("selection_rates_by_group", "min_impact_ratio", "pooled_impact_ratio",
                                            "passes_four_fifths", "summary", "note")}, indent=1))
    for x in rows:
        print(f"{x['ranker']:24s} {x['job_id']:28s} ratio={x['min_impact_ratio']} pass={x['passes_four_fifths']} p={x['p_value']} "
              + " ".join(f"{g}:{v['selected']}/{v['n']}" for g, v in x["rates"].items()))


if __name__ == "__main__":
    main()
