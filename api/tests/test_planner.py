"""CP-SAT planner vs greedy on fictional programs; verify_plan re-checks every plan."""

from __future__ import annotations

from datetime import date

import pytest

from simkit import patch_programs

TODAY = date(2026, 10, 24)


@pytest.fixture
def progs(monkeypatch):
    return patch_programs(monkeypatch)


def _solve(**kw):
    from foothold import planner

    rules = kw.pop("rules", [])
    c = planner.make_constraints(rules=rules, **kw)
    return planner.solve_routes("welder", c, today=TODAY)


def test_routes_shape_and_timing(progs):
    out = _solve(hours_per_week=20, budget_usd=2000, commute_minutes=15, dependents=0, current_credits=0)
    cert = out["routes"]["certificate"]
    assert cert["feasible"] is True
    for k in ("months", "cost_usd", "terms", "solve_ms", "greedy", "expected_wage"):
        assert k in cert
    assert cert["cost_usd"] == pytest.approx(368)
    assert cert["verified"] is True
    assert cert["greedy"]["feasible"] in (True, False)
    assert out["solve_ms"] < 2000
    assert out["routes"]["direct_to_work"]["feasible"] is True


def test_rules_tighten(progs):
    out = _solve(hours_per_week=20, budget_usd=2000, commute_minutes=15, dependents=0,
                 rules=[{"type": "no_class_before", "time": "09:00"}, {"type": "day_off", "day": "Fri"}])
    cert = out["routes"]["certificate"]
    assert cert["feasible"]
    secs = [s for t in cert["terms"] for s in (t.get("steps") or t.get("items") or [])]
    assert secs  # something scheduled
    flat = repr(cert["terms"])
    assert "08:00" not in flat


def test_budget_infeasible(progs):
    out = _solve(hours_per_week=20, budget_usd=100, commute_minutes=15, dependents=0)
    cert = out["routes"]["certificate"]
    assert cert["feasible"] is False and cert.get("reason")


def test_rule_validation():
    from foothold import planner

    assert planner.validate_rule({"type": "day_off", "day": "friday"})["day"] == "Fri"
    assert planner.validate_rule({"type": "bogus"}) is None
    assert planner.validate_rule({"type": "no_class_before", "time": "5pm"})["time"] == "17:00"
