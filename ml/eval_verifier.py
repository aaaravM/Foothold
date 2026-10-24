"""Adversarial evaluation of foothold.verifier (CONTRACTS section 10, key ``verifier``).

Cases are built from the real structured data (careers.json wages/outlook, programs.json costs and
durations):

* correct controls: the true value, plus the rounding prose uses ("$76k" for $75,589, cents/dollar
  rounding for hourly wages, whole weeks for durations) and hourly<->annual conversions;
* adversarial drafts: injected wrong numbers (scaled by 0.5..2x, digit slips x10, another career's
  value, the wrong statistic such as p75 for the median, hourly figure claimed as annual, a fake
  source id). A wrong case is only kept when it differs from the truth by >= 3% (clearly wrong).

catch_rate = wrong claims not verified / wrong claims; false_positive_rate = correct controls not
verified / correct controls. A second block checks prose: drafts whose numbers are injected must
be rejected by ``unbacked_numbers`` while the faithful draft passes.

Run: C:/Users/MUTTA/.venvs/foothold/Scripts/python.exe ml/eval_verifier.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402  (puts api/ on sys.path)

from foothold import data, verifier  # noqa: E402

SEED = 7
WAGE_FIELDS = (("median_annual", "usd_per_year"), ("median_hourly", "usd_per_hour"), ("p25_annual", "usd_per_year"),
               ("p75_annual", "usd_per_year"))
OUTLOOK_FIELDS = (("growth_pct", "percent"), ("annual_openings", "openings_per_year"))


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def clearly_wrong(v: float, truth: float) -> bool:
    return abs(v - truth) >= 0.03 * max(abs(truth), 1e-9) and abs(v - truth) > 0.5


def build_cases(rng: random.Random) -> list[dict]:
    cases: list[dict] = []
    careers = [c for c in data.careers() if isinstance(c, dict)]
    by_field: dict[str, list[float]] = {}
    for c in careers:
        for blk, fields in (("wage", WAGE_FIELDS), ("outlook", OUTLOOK_FIELDS)):
            for f, _ in fields:
                v = _num((c.get(blk) or {}).get(f))
                if v is not None:
                    by_field.setdefault(f, []).append(v)

    def add(claim: dict, correct: bool, kind: str) -> None:
        cases.append({"claim": claim, "correct": correct, "attack": kind})

    for c in careers:
        cid = c["id"]
        w = c.get("wage") or {}
        src = w.get("source_id")
        for f, unit in WAGE_FIELDS:
            truth = _num(w.get(f))
            if truth is None:
                continue
            base = {"kind": "wage", "unit": unit, "entity_id": cid, "field": f, "source_id": src}
            add({**base, "value": truth}, True, "exact")
            add({**base, "value": round(truth / 1000) * 1000 if unit == "usd_per_year" else round(truth, 1)}, True, "rounded")
            if f == "median_hourly":
                add({**base, "value": round(truth * 2080), "unit": "usd_per_year"}, True, "hourly_as_yearly_2080h")
            for k in (0.5, 0.8, 0.88, 1.12, 1.25, 2.0):
                add({**base, "value": round(truth * k, 2)}, False, f"scaled_{k}")
            add({**base, "value": truth * 10}, False, "digit_slip")
            others = [v for v in by_field.get(f, []) if clearly_wrong(v, truth)]
            if others:
                add({**base, "value": rng.choice(others)}, False, "other_career")
            for g, gunit in WAGE_FIELDS:
                gv = _num(w.get(g))
                if g != f and gunit == unit and gv is not None and clearly_wrong(gv, truth):
                    add({**base, "value": gv}, False, f"wrong_stat_{g}")
            if unit == "usd_per_year" and _num(w.get("median_hourly")) is not None:
                add({**base, "value": _num(w.get("median_hourly"))}, False, "hourly_as_annual")
            add({**base, "value": truth, "source_id": "made_up_source"}, False, "fake_source")
        o = c.get("outlook") or {}
        for f, unit in OUTLOOK_FIELDS:
            truth = _num(o.get(f))
            if truth is None:
                continue
            base = {"kind": "outlook", "unit": unit, "entity_id": cid, "field": f, "source_id": o.get("source_id")}
            add({**base, "value": truth}, True, "exact")
            for delta in ((3.0, 7.5, -4.0) if unit == "percent" else (0.5, 1.5, 3.0)):
                v = truth + delta if unit == "percent" else round(truth * delta)
                if clearly_wrong(v, truth):
                    add({**base, "value": v}, False, f"outlook_{delta}")

    for p in data.programs():
        if not isinstance(p, dict) or not p.get("id"):
            continue
        cost = verifier.program_total_cost(p)
        if cost is not None and cost > 0:
            base = {"kind": "cost", "unit": "usd", "entity_id": p["id"], "source_id": p.get("source_id"), "field": None}
            add({**base, "value": cost}, True, "exact")
            add({**base, "value": round(cost)}, True, "rounded")
            for k in (0.5, 0.75, 1.3, 3.0):
                add({**base, "value": round(cost * k, 2)}, False, f"cost_scaled_{k}")
        weeks = verifier.program_duration_weeks(p)
        if weeks is not None and weeks > 2:
            base = {"kind": "duration", "unit": "weeks", "entity_id": p["id"], "source_id": p.get("source_id"), "field": None}
            add({**base, "value": round(weeks, 1)}, True, "exact")
            add({**base, "value": round(weeks / verifier.WEEKS_PER_MONTH, 1), "unit": "months"}, True, "as_months")
            for k in (0.5, 1.5, 2.0):
                add({**base, "value": round(weeks * k, 1)}, False, f"duration_scaled_{k}")
    return cases


def prose_cases(rng: random.Random) -> dict:
    """Template-filled drafts vs. drafts with injected numbers."""
    n_ok = n_ok_pass = n_bad = n_bad_caught = 0
    for c in data.careers():
        w = (c or {}).get("wage") or {}
        med = _num(w.get("median_annual"))
        if med is None:
            continue
        allowed = [f"${med:,.0f}"]
        good = f"Median pay in the area is about {allowed[0]} a year."
        n_ok += 1
        n_ok_pass += not verifier.unbacked_numbers(good, allowed)
        for wrong in (med * 1.2, med * 0.7, med + 9000):
            bad = f"Median pay in the area is about ${wrong:,.0f} a year, with {rng.randint(10, 40)}% growth."
            n_bad += 1
            n_bad_caught += bool(verifier.unbacked_numbers(bad, allowed))
    return {"faithful_drafts": n_ok, "faithful_pass_rate": round(n_ok_pass / n_ok, 4) if n_ok else None,
            "injected_drafts": n_bad, "injected_catch_rate": round(n_bad_caught / n_bad, 4) if n_bad else None}


def main() -> dict:
    common.seed_everything(SEED)
    rng = random.Random(SEED)
    cases = build_cases(rng)
    wrong = [c for c in cases if not c["correct"]]
    right = [c for c in cases if c["correct"]]
    by_attack: dict[str, list[int]] = {}
    caught = fp = 0
    for c in cases:
        status = verifier.verify_claim(c["claim"]).status
        ok = status == "verified"
        if c["correct"]:
            fp += not ok
        else:
            caught += not ok
        a = by_attack.setdefault(c["attack"], [0, 0])
        a[0] += 1
        a[1] += (not ok) if not c["correct"] else ok
    block = {
        "status": "ok" if cases else "no_data",
        "provenance": "SYNTHETIC",
        "data": "adversarial claims generated from data/processed careers.json + programs.json",
        "seed": SEED,
        "trained_at": common.now_iso(),
        "reproduce": "python ml/eval_verifier.py",
        "n_cases": len(cases),
        "n_wrong": len(wrong),
        "n_correct": len(right),
        "catch_rate": round(caught / len(wrong), 4) if wrong else None,
        "false_positive_rate": round(fp / len(right), 4) if right else None,
        "by_attack": {k: {"n": v[0], "handled": v[1]} for k, v in sorted(by_attack.items())},
        "prose": prose_cases(rng),
        "note": "A wrong claim counts as caught when it is not verified (mismatch is dropped, unverifiable is flagged).",
    }
    common.write_metrics("verifier", block)
    return block


if __name__ == "__main__":
    out = main()
    print({k: out[k] for k in ("n_cases", "n_wrong", "n_correct", "catch_rate", "false_positive_rate")}, out["prose"])
