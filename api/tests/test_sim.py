"""Career Sim graph + routes (mock LLM, synthetic events)."""

from __future__ import annotations

import pytest

from simkit import client_for, parse_sse, patch_events, signed_in


@pytest.fixture
def sim_client(monkeypatch):
    patch_events(monkeypatch)
    from foothold.routes import sim as sim_routes

    headers = signed_in(monkeypatch, "maya")
    return client_for(sim_routes.router), headers


def _types(evs):
    return [e["type"] for e in evs]


def _play(client, headers, career_id):
    r = client.post("/api/sim/start", json={"career_id": career_id}, headers=headers)
    assert r.status_code == 200, r.text
    evs = parse_sse(r.text)
    assert evs[0]["type"] == "meta" and evs[0]["graph"] == "sim"
    tid = evs[0]["thread_id"]
    seen = []
    for _ in range(8):
        intr = [e for e in evs if e["type"] == "interrupt"]
        if not intr:
            break
        payload = intr[-1]["payload"]
        ev = payload["event"]
        seen.append(ev["event_id"])
        for c in ev["choices"]:
            assert set(c) == {"choice_id", "text"}  # hidden deltas never reach the client
        choice = "b"  # the stressful choice, to exercise the crunch branch
        r = client.post(f"/api/sim/{tid}/choose", json={"choice_id": choice}, headers=headers)
        assert r.status_code == 200, r.text
        evs = parse_sse(r.text)
        assert "error" not in _types(evs), evs
    done = [e for e in evs if e["type"] == "done"]
    assert done, _types(evs)
    return tid, seen, done[0]["result"], evs


def test_chosen_career_full_day(sim_client):
    client, headers = sim_client
    tid, seen, result, evs = _play(client, headers, "welder")
    assert 5 <= len(seen) <= 6
    assert seen[0] == "welder_01"
    assert "welder_crunch" in seen  # stress climbs past 75 with choice b
    rep = result["report"]
    assert rep and result["saved"] is True
    assert len(rep["top_careers"]) == 3
    assert {t["career_id"] for t in rep["top_careers"]} <= {
        "logistics_lead", "registered_nurse", "diesel_mechanic", "welder", "electrician", "software_dev",
        "farm_ops_manager", "robotics_tech"}
    nodes = {e.get("node") for e in evs if e["type"] == "node"}
    assert "report" in nodes
    st = client.get(f"/api/sim/{tid}/state", headers=headers).json()
    assert st["status"] == "done" and st["report"]
    # report numbers come only from verified claims
    assert "summary" in rep


def test_coworker_fanout_and_trace(sim_client):
    client, headers = sim_client
    r = client.post("/api/sim/start", json={"career_id": "registered_nurse"}, headers=headers)
    evs = parse_sse(r.text)
    meta = evs[0]
    groups = [n for n in meta["nodes"] if n.get("group") == "coworkers_react"]
    assert len(groups) == 3
    tid = meta["thread_id"]
    r = client.post(f"/api/sim/{tid}/choose", json={"choice_id": "a"}, headers=headers)
    evs = parse_sse(r.text)
    cw_nodes = {e["node"] for e in evs if e["type"] == "node" and str(e.get("node", "")).startswith("coworker:")}
    assert len(cw_nodes) == 3
    llm_src = {e.get("llm") for e in evs if e["type"] == "node" and e.get("llm")}
    assert llm_src <= {"mock", "cache", "openai"}


def test_adaptive_run_and_validation(sim_client):
    client, headers = sim_client
    r = client.post("/api/sim/start", json={"career_id": None}, headers=headers)
    assert r.status_code == 200
    tid = parse_sse(r.text)[0]["thread_id"]
    assert client.post(f"/api/sim/{tid}/choose", json={"choice_id": "zzz"}, headers=headers).status_code == 400
    assert client.post("/api/sim/start", json={"career_id": "astronaut"}, headers=headers).status_code == 400


def test_ownership_and_auth(sim_client, monkeypatch):
    client, headers = sim_client
    tid = parse_sse(client.post("/api/sim/start", json={"career_id": "welder"}, headers=headers).text)[0]["thread_id"]
    assert client.post("/api/sim/start", json={"career_id": "welder"}).status_code == 401
    from foothold import auth

    other, _ = auth.issue_token(auth.get_account_by_persona("dev"))
    r = client.get(f"/api/sim/{tid}/state", headers={"Authorization": f"Bearer {other}"})
    assert r.status_code == 404


def test_sample_event_public(sim_client):
    client, _ = sim_client
    r = client.get("/api/sim/sample-event")
    assert r.status_code == 200
    body = r.json()
    assert body["event"]["choices"] and body["traits"]


def test_blend_weights():
    from foothold.graphs import sim

    out = sim.blend({"initiative": 1.0}, {"initiative": 0.0, "empathy": 1.0})
    assert out["initiative"] == pytest.approx(0.7)
    assert out["empathy"] == pytest.approx(0.3)
