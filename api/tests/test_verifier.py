"""Claim verifier: tolerances, drops wrong numbers, flags unverifiable claims."""

from __future__ import annotations

import pytest

from simkit import patch_programs

WAGE = {"median_hourly": 24.5, "median_annual": 50960, "p25_annual": 41000, "p75_annual": 62000,
        "area": "Stockton-Lodi", "period": "2026 Q1", "source_id": "edd_oews", "status": "REAL"}


@pytest.fixture
def vdata(monkeypatch):
    from foothold import data

    patch_programs(monkeypatch)
    base = data.careers()
    careers = [dict(c, wage=dict(WAGE), outlook={"growth_pct": 8.2, "annual_openings": 120, "period": "2022-2032",
                                                  "source_id": "edd_proj", "status": "REAL"}) if c["id"] == "welder" else c
               for c in base]
    monkeypatch.setattr(data, "careers", lambda: careers)
    monkeypatch.setattr(data, "get_career", lambda cid: next((c for c in careers if c["id"] == cid), None))


def _v(**kw):
    from foothold import verifier

    return verifier.verify_claim(kw).status


def test_wage_claims(vdata):
    assert _v(kind="wage", value=50960, unit="usd_per_year", entity_id="welder", field="median_annual") == "verified"
    assert _v(kind="wage", value=51000, unit="usd_per_year", entity_id="welder", field="median_annual") == "verified"
    assert _v(kind="wage", value=60000, unit="usd_per_year", entity_id="welder", field="median_annual") == "mismatch"
    assert _v(kind="wage", value=24.5, unit="usd_per_hour", entity_id="welder", field="median_hourly") == "verified"
    assert _v(kind="wage", value=30, unit="usd_per_hour", entity_id="welder", field="median_hourly") == "mismatch"


def test_outlook_cost_duration(vdata):
    assert _v(kind="outlook", value=8.2, unit="percent", entity_id="welder", field="growth_pct") == "verified"
    assert _v(kind="outlook", value=12, unit="percent", entity_id="welder", field="growth_pct") == "mismatch"
    assert _v(kind="cost", value=368, unit="usd", entity_id="t_weld_cert") == "verified"
    assert _v(kind="cost", value=900, unit="usd", entity_id="t_weld_cert") == "mismatch"
    assert _v(kind="cost", value=138, unit="usd", entity_id="t_weld_cert/weld1") == "verified"


def test_unverifiable(vdata):
    assert _v(kind="wage", value=50000, unit="usd_per_year", entity_id="astronaut") == "unverifiable"


def test_templates():
    from foothold import verifier

    assert verifier.placeholder_problems("Earns {wage} a year", ["wage"]) == []
    assert verifier.placeholder_problems("Earns $70,000 a year", ["wage"])
    assert verifier.unbacked_numbers("about $51,000 or 12%", ["$51,000"]) == ["12%"]
