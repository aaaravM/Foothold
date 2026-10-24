"""CP-SAT planner vs greedy baseline on 200 generated constraint sets (CONTRACTS section 10, key ``planner``).

Each case draws a career and learner constraints (hours/week, budget, commute, dependents, existing units,
plus 0-3 schedule rules such as "no class before 17:00", a day off, online only, no summer, campus-day
cap) and solves every route with ``planner.solve_routes`` over data/processed/programs.json (the same call
the API makes). For each (case, route) with program data we record CP-SAT and greedy feasibility,
months, cost and the end-to-end ``solve_ms`` of the case. Every CP-SAT plan is re-checked by
``planner.verify_plan`` (independent recomputation from the raw program data).

Run: C:/Users/MUTTA/.venvs/foothold/Scripts/python.exe ml/eval_planner.py
"""

from __future__ import annotations

import random
import statistics
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

from foothold import data, planner  # noqa: E402

SEED = 11
N_CASES = 200
TODAY = date(2026, 10, 24)  # fixed so the term grid is reproducible


def gen_case(rng: random.Random, careers: list[str]) -> dict:
    rules = []
    pool = [
        lambda: {"type": "no_class_before", "time": rng.choice(["09:00", "12:00", "17:00", "18:00"])},
        lambda: {"type": "no_class_after", "time": rng.choice(["14:00", "18:00", "21:00"])},
        lambda: {"type": "day_off", "day": rng.choice(planner.DAYS[:6])},
        lambda: {"type": "online_only"},
        lambda: {"type": "no_summer"},
        lambda: {"type": "max_campus_days", "number": rng.choice([1, 2, 3])},
        lambda: {"type": "max_courses_per_term", "number": rng.choice([1, 2, 3])},
    ]
    for f in rng.sample(pool, rng.choice([0, 1, 1, 2, 2, 3])):
        rules.append(f())
    return {
        "career_id": rng.choice(careers),
        "hours_per_week": rng.choice([6, 8, 10, 12, 15, 20, 25, 30]),
        "budget_usd": rng.choice([500, 1000, 2000, 3000, 5000, 8000, 15000]),
        "commute_minutes": rng.choice([0, 10, 20, 30, 45, 60]),
        "dependents": rng.choice([0, 0, 1, 2, 3]),
        "current_credits": rng.choice([0, 0, 0, 6, 12, 24]),
        "rules": planner.dedupe_rules(rules),
    }


def pct(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 1)


def main() -> dict:
    common.seed_everything(SEED)
    rng = random.Random(SEED)
    careers = sorted({p["career_id"] for p in data.programs() if isinstance(p, dict) and p.get("career_id")})
    if not careers:
        block = {"status": "no_data", "provenance": "SYNTHETIC", "data": "programs.json missing", "seed": SEED,
                 "trained_at": common.now_iso(), "reproduce": "python ml/eval_planner.py", "n_cases": 0}
        common.write_metrics("planner", block)
        return block
    case_ms: list[float] = []
    route_ms: list[float] = []
    n_routes = cp_feas = gr_feas = both = cp_only = gr_only = verified = 0
    months_gain: list[float] = []
    cost_gain: list[float] = []
    obj_better = 0
    for _ in range(N_CASES):
        case = gen_case(rng, careers)
        c = planner.make_constraints(hours_per_week=case["hours_per_week"], budget_usd=case["budget_usd"],
                                     commute_minutes=case["commute_minutes"], dependents=case["dependents"],
                                     current_credits=case["current_credits"], rules=case["rules"])
        out = planner.solve_routes(case["career_id"], c, today=TODAY)
        case_ms.append(out["solve_ms"])
        for rt, r in out["routes"].items():
            if not r.get("available") or r.get("excluded"):
                continue
            n_routes += 1
            route_ms.append(r.get("solve_ms") or 0)
            g = r.get("greedy") or {}
            cf, gf = bool(r.get("feasible")), bool(g.get("feasible"))
            cp_feas += cf
            gr_feas += gf
            cp_only += cf and not gf
            gr_only += gf and not cf
            if cf:
                verified += bool(r.get("verified"))
            if cf and gf:
                both += 1
                months_gain.append(g["months"] - r["months"])
                cost_gain.append(g["cost_usd"] - r["cost_usd"])
                go = planner.DEFAULT_WEIGHTS["months"] * g["months"] + g["cost_usd"]
                co = planner.DEFAULT_WEIGHTS["months"] * r["months"] + r["cost_usd"]
                obj_better += co < go - 1e-6
    block = {
        "status": "ok",
        "provenance": "SYNTHETIC",
        "data": f"{N_CASES} generated constraint sets over data/processed/programs.json ({len(data.programs())} programs, "
                f"{len(careers)} careers); program records keep their own REAL/SAMPLE status",
        "seed": SEED,
        "trained_at": common.now_iso(),
        "reproduce": "python ml/eval_planner.py",
        "n_cases": N_CASES,
        "n_route_solves": n_routes,
        "feasibility": {"cpsat": round(cp_feas / n_routes, 4), "greedy": round(gr_feas / n_routes, 4),
                        "cpsat_only": cp_only, "greedy_only": gr_only},
        "solve_ms": {"p50": pct(case_ms, 0.5), "p95": pct(case_ms, 0.95), "max": max(case_ms),
                     "per_route_p50": pct(route_ms, 0.5), "per_route_p95": pct(route_ms, 0.95),
                     "note": "p50/p95 = one /api/path/solve call (all routes of a career, solved in parallel)"},
        "improvement_when_both_feasible": {
            "n": both,
            "months_saved_mean": round(statistics.mean(months_gain), 3) if months_gain else None,
            "months_saved_max": max(months_gain) if months_gain else None,
            "cost_saved_mean_usd": round(statistics.mean(cost_gain), 2) if cost_gain else None,
            "share_cpsat_strictly_better": round(obj_better / both, 4) if both else None,
        },
        "cpsat_plans_verified": round(verified / cp_feas, 4) if cp_feas else None,
        "time_limit_s": planner.DEFAULT_TIME_LIMIT_S,
    }
    common.write_metrics("planner", block)
    return block


if __name__ == "__main__":
    b = main()
    print({k: b.get(k) for k in ("n_cases", "n_route_solves", "feasibility", "solve_ms", "improvement_when_both_feasible",
                                 "cpsat_plans_verified")})
