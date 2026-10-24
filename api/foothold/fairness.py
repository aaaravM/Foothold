"""Four-fifths selection audit (brief 6.5). SYNTHETIC talent pool, synthetic group labels.

The ranker NEVER sees the group attribute: candidates are scored only from blind-card fields
(demonstrated skills) plus the graph recommender's affinity score. The group label is joined
back only afterwards, to compute selection rates per group.

Public API
----------
four_fifths(groups, selected, min_group_size=5) -> dict
    groups[i] = synthetic group of pool member i; selected[i] = bool.
    -> {rates: {g: {n, selected, rate}}, suppressed_groups: [g], min_impact_ratio: float|None,
        impact_ratios: {g: rate/max_rate}, lowest_group, highest_group, passes_four_fifths: bool|None,
        n_pool, n_selected, min_group_size, method, note, p_value (chi-square, None if scipy missing)}
    Groups with fewer than ``min_group_size`` members are excluded from the ratio (reported in
    ``suppressed_groups``, without their counts). No selections, or < 2 comparable groups -> ratio None.
rank_candidates(required_skills, preferred_skills=None, pool=None, use_recommender=True) -> list[dict]
    [{id, score, skill_match, recommender}] best first; score = 0.7*skill_match + 0.3*recommender
    (skill_match only if the recommender is unavailable).
audit_posting(required_skills, preferred_skills=None, top_n=15, pool=None, use_recommender=True, posting=None)
    -> {posting, top_n, selected_ids, ranking_inputs, recommender_used, **four_fifths(...)}
NOTE
    "Audit runs on synthetic data and demonstrates the mechanism, not real-world fairness."
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from foothold import data

MIN_GROUP_SIZE = 5
THRESHOLD = 0.8
W_SKILL, W_REC = 0.7, 0.3
NOTE = "Audit runs on synthetic data and demonstrates the mechanism, not real-world fairness."
METHOD = "four-fifths rule: lowest group selection rate / highest group selection rate >= 0.8"


def four_fifths(groups: list[Any], selected: list[bool], min_group_size: int = MIN_GROUP_SIZE) -> dict[str, Any]:
    if len(groups) != len(selected):
        raise ValueError("groups and selected must have the same length")
    n_by = Counter(groups)
    sel_by = Counter(g for g, s in zip(groups, selected) if s)
    rates = {str(g): {"n": n, "selected": sel_by[g], "rate": round(sel_by[g] / n, 4)}
             for g, n in sorted(n_by.items(), key=lambda t: str(t[0])) if n >= min_group_size}
    suppressed = sorted(str(g) for g, n in n_by.items() if n < min_group_size)
    base = {"rates": rates, "suppressed_groups": suppressed, "n_pool": len(groups), "n_selected": int(sum(selected)),
            "min_group_size": min_group_size, "threshold": THRESHOLD, "method": METHOD, "note": NOTE}
    if len(rates) < 2:
        return {**base, "min_impact_ratio": None, "impact_ratios": {}, "lowest_group": None, "highest_group": None,
                "passes_four_fifths": None, "reason": "fewer than two groups meet the minimum group size"}
    top_g = max(rates, key=lambda g: (rates[g]["rate"], g))
    low_g = min(rates, key=lambda g: (rates[g]["rate"], g))
    top = rates[top_g]["rate"]
    if top <= 0:
        return {**base, "min_impact_ratio": None, "impact_ratios": {}, "lowest_group": None, "highest_group": None,
                "passes_four_fifths": None, "reason": "no one selected yet"}
    ratios = {g: round(r["rate"] / top, 4) for g, r in rates.items()}
    base["p_value"] = _chi2_p(rates)
    mir = round(rates[low_g]["rate"] / top, 4)
    return {**base, "min_impact_ratio": mir, "impact_ratios": ratios, "lowest_group": low_g, "highest_group": top_g,
            "passes_four_fifths": bool(mir >= THRESHOLD)}


def _chi2_p(rates: dict[str, dict[str, Any]]) -> float | None:
    """Chi-square test of selection vs group (small counts make the four-fifths ratio noisy)."""
    try:
        from scipy.stats import chi2_contingency

        table = [[r["selected"], r["n"] - r["selected"]] for r in rates.values()]
        return round(float(chi2_contingency(table)[1]), 4)
    except Exception:  # noqa: BLE001
        return None


def _blind_skills(card: dict[str, Any]) -> set[str]:
    b = card.get("blind") or {}
    return set(b.get("demonstrated_skills") or card.get("demonstrated_skills") or [])


def _strip_group(card: dict[str, Any]) -> dict[str, Any]:
    """Copy of a card without any group-like field: what the ranker is allowed to see."""
    return {k: v for k, v in card.items() if k not in ("group", "synthetic_group", "fairness_group", "demographic_group")}


def rank_candidates(required_skills: list[str], preferred_skills: list[str] | None = None,
                    pool: list[dict[str, Any]] | None = None, use_recommender: bool = True) -> tuple[list[dict[str, Any]], bool]:
    pool = data.talent_pool() if pool is None else pool
    cards = [_strip_group(c) for c in pool if isinstance(c, dict) and (c.get("id") or c.get("candidate_id"))]
    req = [s for s in dict.fromkeys(required_skills or [])]
    pref = [s for s in dict.fromkeys(preferred_skills or []) if s not in req]
    weights = {**{s: 1.0 for s in req}, **{s: 0.5 for s in pref}}
    total = sum(weights.values()) or 1.0
    rec: dict[str, float] = {}
    if use_recommender and weights:
        try:
            from foothold import recommender

            rec = recommender.score_talent(cards, {"skills": [{"skill_id": s, "importance": "required" if w == 1.0 else "preferred"}
                                                              for s, w in weights.items()]})
        except Exception:  # noqa: BLE001
            rec = {}
    used = bool(rec)
    out = []
    for c in cards:
        cid = str(c.get("id") or c.get("candidate_id"))
        have = _blind_skills(c)
        match = sum(w for s, w in weights.items() if s in have) / total
        r = rec.get(cid)
        score = W_SKILL * match + W_REC * r if (used and r is not None) else match
        out.append({"id": cid, "score": round(score, 4), "skill_match": round(match, 4),
                    "recommender": None if r is None else round(r, 4)})
    out.sort(key=lambda x: (-x["score"], -x["skill_match"], x["id"]))
    return out, used


def audit_posting(required_skills: list[str], preferred_skills: list[str] | None = None, top_n: int = 15,
                  pool: list[dict[str, Any]] | None = None, use_recommender: bool = True,
                  posting: dict[str, Any] | None = None, min_group_size: int = MIN_GROUP_SIZE) -> dict[str, Any]:
    pool = data.talent_pool() if pool is None else pool
    ranked, used = rank_candidates(required_skills, preferred_skills, pool, use_recommender)
    chosen = {r["id"] for r in ranked[:top_n]}
    members = [c for c in pool if isinstance(c, dict) and (c.get("id") or c.get("candidate_id"))]
    groups = [c.get("group") for c in members]
    if any(g is None for g in groups):
        return {"posting": posting, "available": False, "reason": "pool has no synthetic group labels", "note": NOTE}
    selected = [str(c.get("id") or c.get("candidate_id")) in chosen for c in members]
    res = four_fifths(groups, selected, min_group_size=min_group_size)
    return {"posting": posting, "available": True, "top_n": top_n, "selected_ids": [r["id"] for r in ranked[:top_n]],
            "recommender_used": used,
            "ranking_inputs": "blind demonstrated skills + recommender score; group label never used",
            "weights": {"skill_match": W_SKILL if used else 1.0, "recommender": W_REC if used else 0.0}, **res}


__all__ = ["four_fifths", "rank_candidates", "audit_posting", "NOTE", "MIN_GROUP_SIZE"]
