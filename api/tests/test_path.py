"""Pathway routes + agent graph (mock LLM, fictional programs)."""

from __future__ import annotations

import pytest

from simkit import client_for, parse_sse, patch_programs, signed_in


@pytest.fixture
def path_client(monkeypatch):
    patch_programs(monkeypatch)
    from foothold.routes import path as path_routes

    headers = signed_in(monkeypatch, "maya")
    return client_for(path_routes.router), headers


def test_solve_public(path_client):
    client, _ = path_client
    r = client.post("/api/path/solve", json={"career_id": "welder", "current_credits": 0, "hours_per_week": 15,
                                             "budget_usd": 2000, "commute_minutes": 15, "dependents": 1,
                                             "extra_constraints": {"days_off": ["Fri"]}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["routes"]["certificate"]["feasible"]
    assert body["solve_ms"] < 2000
    assert body["rules"][0]["label"] == "Fri off"
    assert client.post("/api/path/solve", json={"career_id": "nope"}).status_code == 400


def test_regex_translate():
    from foothold.graphs import pathway

    rules = pathway.regex_rules("I work days so no classes before 5pm, Fridays off, online only, budget $1,500, "
                                "max 10 hours a week, no summer, and no apprenticeship")
    types = {r["type"] for r in rules}
    assert {"no_class_before", "day_off", "online_only", "max_budget", "max_hours_per_week", "no_summer", "avoid_route"} <= types
    assert {"type": "no_class_before", "time": "17:00"} in rules
    assert {"type": "day_off", "day": "Fri"} in rules


def test_translate_route(path_client):
    client, _ = path_client
    r = client.post("/api/path/translate", json={"text": "no class before 9am and I can't do Fridays"})
    body = r.json()
    assert body["source"] == "mock"
    assert {x["label"] for x in body["rules"]} == {"No class before 09:00", "Fri off"}


def test_agent_confirm_reject_approve(path_client):
    client, headers = path_client
    r = client.post("/api/path/start", json={"career_id": "welder", "hours_per_week": 15, "budget_usd": 2000,
                                             "text": "no class before 9am, Fridays off"}, headers=headers)
    assert r.status_code == 200, r.text
    evs = parse_sse(r.text)
    tid = evs[0]["thread_id"]
    intr = [e for e in evs if e["type"] == "interrupt"][-1]
    assert intr["payload"]["kind"] == "confirm_rules"
    assert len(intr["payload"]["proposed"]) == 2
    evs = parse_sse(client.post(f"/api/path/{tid}/decision", json={"approve": True}, headers=headers).text)
    intr = [e for e in evs if e["type"] == "interrupt"][-1]
    assert intr["payload"]["kind"] == "approve_plan"
    assert intr["payload"]["best_route"]
    assert "solve" in {e.get("node") for e in evs if e["type"] == "node"}
    best = intr["payload"]["best_route"]
    # reject: "I don't want this route" -> avoid_route rule -> re-solve picks another route
    evs = parse_sse(client.post(f"/api/path/{tid}/decision", json={"approve": False, "reason": "I don't want this route"},
                                headers=headers).text)
    intr = [e for e in evs if e["type"] == "interrupt"][-1]
    assert intr["payload"]["kind"] == "approve_plan"
    assert {"type": "avoid_route", "route_type": best, "label": intr["payload"]["rules"][-1]["label"]} in intr["payload"]["rules"]
    assert intr["payload"]["best_route"] != best
    evs = parse_sse(client.post(f"/api/path/{tid}/decision", json={"approve": True}, headers=headers).text)
    done = [e for e in evs if e["type"] == "done"]
    assert done and done[0]["result"]["approved"] is True
    kb = client.get("/api/path/kanban", headers=headers).json()
    assert kb["items"]
    items = kb["items"]
    items[0]["column"] = "doing"
    kb2 = client.put("/api/path/kanban", json={"items": items}, headers=headers).json()
    assert kb2["items"][0]["column"] == "doing"
    st = client.get(f"/api/path/{tid}/state", headers=headers).json()
    assert st["status"] == "done"


def test_kanban_requires_learner(path_client):
    client, _ = path_client
    assert client.get("/api/path/kanban").status_code == 401


def test_rejection_relaxes_when_infeasible(path_client):
    client, headers = path_client
    evs = parse_sse(client.post("/api/path/start", json={"career_id": "welder", "hours_per_week": 15, "budget_usd": 2000},
                                headers=headers).text)
    tid = evs[0]["thread_id"]
    intr = [e for e in evs if e["type"] == "interrupt"][-1]["payload"]
    assert intr["kind"] == "approve_plan"  # no free text -> no rule confirmation step
    # ask for something impossible: finish within 1 month
    evs = parse_sse(client.post(f"/api/path/{tid}/decision", json={"approve": False, "reason": "finish within 1 month"},
                                headers=headers).text)
    intr = [e for e in evs if e["type"] == "interrupt"][-1]["payload"]
    assert intr["best_route"] is not None
    assert intr["proposal"]["relaxed_rules"] == ["Finish within 1 month"]
    assert intr["proposal"]["text"].startswith("No route could meet")
