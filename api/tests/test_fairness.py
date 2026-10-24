"""Four-fifths audit (foothold.fairness)."""

from __future__ import annotations

from foothold import data, fairness


def test_four_fifths_pass_and_fail():
    groups = ["A"] * 10 + ["B"] * 10
    ok = fairness.four_fifths(groups, [True] * 5 + [False] * 5 + [True] * 4 + [False] * 6)
    assert ok["rates"]["A"]["rate"] == 0.5 and ok["rates"]["B"]["rate"] == 0.4
    assert ok["min_impact_ratio"] == 0.8 and ok["passes_four_fifths"] is True
    bad = fairness.four_fifths(groups, [True] * 5 + [False] * 5 + [True] * 2 + [False] * 8)
    assert bad["min_impact_ratio"] == 0.4 and bad["passes_four_fifths"] is False
    assert bad["lowest_group"] == "B" and bad["highest_group"] == "A"
    assert bad["note"] == fairness.NOTE


def test_small_groups_suppressed_and_no_selection():
    groups = ["A"] * 10 + ["B"] * 10 + ["C"] * 3
    sel = [True] * 5 + [False] * 5 + [True] * 5 + [False] * 5 + [False] * 3
    r = fairness.four_fifths(groups, sel)
    assert "C" not in r["rates"] and r["suppressed_groups"] == ["C"] and r["passes_four_fifths"] is True
    none = fairness.four_fifths(groups, [False] * len(groups))
    assert none["min_impact_ratio"] is None and none["passes_four_fifths"] is None
    one = fairness.four_fifths(["A"] * 10 + ["B"] * 2, [True] * 12)
    assert one["passes_four_fifths"] is None


def test_ranker_never_sees_group():
    pool = data.talent_pool()
    req = ["osha_safety", "forklift_safety", "inventory_control"]
    a, _ = fairness.rank_candidates(req, pool=pool)
    b, _ = fairness.rank_candidates(req, pool=[{**c, "group": "X"} for c in pool])
    assert [x["id"] for x in a] == [x["id"] for x in b]
    assert all("group" not in x for x in a)


def test_audit_posting_shape():
    r = fairness.audit_posting(["osha_safety", "forklift_safety", "coordination"], top_n=15,
                               posting={"job_id": "warehouse_associate"})
    assert r["available"] and len(r["selected_ids"]) == 15 and r["n_selected"] == 15
    assert set(r["rates"]) <= {"A", "B", "C"} and r["passes_four_fifths"] in (True, False)
    assert 0.0 <= r["min_impact_ratio"] <= 1.0
