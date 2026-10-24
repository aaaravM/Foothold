"""Sim personalization, free-text answers and any-career runs (mock LLM, no network)."""

from __future__ import annotations

import pytest

from simkit import client_for, parse_sse, patch_events, signed_in


@pytest.fixture
def live_client(monkeypatch):
    patch_events(monkeypatch)
    from foothold.routes import careers as careers_routes
    from foothold.routes import sim as sim_routes

    headers = signed_in(monkeypatch, "maya")
    return client_for(sim_routes.router, careers_routes.router), headers


def _interrupt(evs):
    intr = [e for e in evs if e["type"] == "interrupt"]
    assert intr, [e["type"] for e in evs]
    return intr[-1]["payload"]


def _nodes(evs, status="end"):
    return {e["node"]: e for e in evs if e["type"] == "node" and e["status"] == status}


# -- free-text answers ---------------------------------------------------------


def test_custom_answer_scores_and_updates(live_client):
    client, headers = live_client
    r = client.post("/api/sim/start", json={"career_id": "welder"}, headers=headers)
    evs = parse_sse(r.text)
    tid = evs[0]["thread_id"]
    first = _interrupt(evs)
    assert first["custom_allowed"] is True
    assert "personalize_event" in _nodes(evs)
    r = client.post(f"/api/sim/{tid}/choose", headers=headers,
                    json={"choice_id": "custom", "text": "I'd stop, double check the gauge, and ask the team to help me inspect it safely."})
    assert r.status_code == 200, r.text
    evs = parse_sse(r.text)
    assert "error" not in [e["type"] for e in evs], evs
    ends = _nodes(evs)
    assert ends["score_custom"]["summary"].startswith("Read your answer")
    assert sum(1 for n in ends if n.startswith("coworker:")) == 3  # the 3 coworkers react
    custom = next(e["data"]["custom"] for e in evs if e["type"] == "state" and "custom" in e["data"])
    from foothold.graphs import sim

    td = custom["trait_deltas"]
    assert 2 <= len(td) <= 4 and set(td) <= set(sim.trait_ids()) and all(-1 <= v <= 1 for v in td.values())
    assert all(-15 <= v <= 15 and isinstance(v, int) for v in custom["stat_deltas"].values())
    last = next(e["data"]["last"] for e in evs if e["type"] == "state" and "last" in e["data"])
    assert last["choice_id"] == "custom" and last["custom"] is True and "double check" in last["choice_text"]
    assert last["trait_deltas"]
    st = client.get(f"/api/sim/{tid}/state", headers=headers).json()
    assert st["state"]["history"][0]["choice_id"] == "custom"
    assert st["status"] == "waiting"


def test_custom_answer_crisis_ends_turn(live_client):
    client, headers = live_client
    evs = parse_sse(client.post("/api/sim/start", json={"career_id": "welder"}, headers=headers).text)
    tid = evs[0]["thread_id"]
    before = _interrupt(evs)["event"]["event_id"]
    r = client.post(f"/api/sim/{tid}/choose", headers=headers, json={"choice_id": "custom", "text": "I want to end my life"})
    assert r.status_code == 200
    evs = parse_sse(r.text)
    assert [e["type"] for e in evs if e["type"] in ("done", "error")] == []
    payload = _interrupt(evs)
    assert payload["crisis"]["crisis"] is True and "988" in payload["crisis"]["message"]
    assert payload["event"]["event_id"] == before  # same moment, nothing played
    st = client.get(f"/api/sim/{tid}/state", headers=headers).json()
    assert st["state"]["history"] == [] and st["status"] == "waiting"


def test_custom_answer_validation(live_client):
    client, headers = live_client
    evs = parse_sse(client.post("/api/sim/start", json={"career_id": "welder"}, headers=headers).text)
    tid = evs[0]["thread_id"]
    assert client.post(f"/api/sim/{tid}/choose", headers=headers, json={"choice_id": "custom", "text": "  "}).status_code == 400
    assert client.post(f"/api/sim/{tid}/choose", headers=headers, json={"choice_id": "zzz"}).status_code == 400


def test_mock_custom_score_heuristic():
    from foothold.graphs import sim

    out = sim.mock_custom_score("skip the checklist and rush it out myself", [{"id": "x", "style": "safety-first"}])
    assert out["stat_deltas"]["safety"] < 0 and out["coworker_hints"][0]["hint"].startswith("Worried")
    assert 2 <= len(out["trait_deltas"]) <= 4


# -- personalize_event ---------------------------------------------------------


def test_personalize_preserves_ids_and_deltas():
    from foothold.graphs import sim
    from simkit import synthetic_events

    ev = synthetic_events()["events"][0]
    obj = sim.PersonalizedEvent(
        title="Event at the Stockton yard", text="Something happens at 08:00 in Stockton. Rosa needs you to decide.",
        choices=[sim.PersonalChoice(choice_id="b", text="Option b, done the Stockton way"),
                 sim.PersonalChoice(choice_id="a", text="Option a for the Stockton job"),
                 sim.PersonalChoice(choice_id="zz", text="invented choice"),
                 sim.PersonalChoice(choice_id="c", text="x" * 400)])  # too long -> original kept
    new, changed = sim.apply_personalization(ev, obj)
    assert [c["choice_id"] for c in new["choices"]] == [c["choice_id"] for c in ev["choices"]]
    for old, nc in zip(ev["choices"], new["choices"]):
        assert nc["trait_deltas"] == old["trait_deltas"] and nc["stat_deltas"] == old["stat_deltas"]
        assert nc["coworker_hints"] == old["coworker_hints"]
    assert new["choices"][0]["text"] == "Option a for the Stockton job"
    assert new["choices"][2]["text"] == ev["choices"][2]["text"]
    assert "Stockton" in new["title"] and changed == 4


def test_personalize_mock_keeps_original(live_client):
    client, headers = live_client
    evs = parse_sse(client.post("/api/sim/start", json={"career_id": "welder"}, headers=headers).text)
    p = _interrupt(evs)
    assert p["event"]["title"] == "Event welder_01"
    assert _nodes(evs)["personalize_event"]["summary"] == "Kept the original wording"


# -- any career ----------------------------------------------------------------


def test_careers_search(live_client):
    client, _ = live_client
    rows = client.get("/api/careers/search", params={"q": "dental"}).json()
    assert rows and all(set(r) == {"onet_soc", "title", "career_id"} for r in rows)
    assert any("Dental" in r["title"] for r in rows)
    core = client.get("/api/careers/search", params={"q": "diesel"}).json()
    assert core[0]["career_id"] == "diesel_mechanic"
    assert len(client.get("/api/careers/search").json()) == 8


def test_any_career_start_choose_next(live_client):
    client, headers = live_client
    from foothold import occupations_index

    soc = occupations_index.search("dental hygienist", 1)[0]["onet_soc"]
    r = client.post("/api/sim/start", json={"onet_soc": soc}, headers=headers)
    assert r.status_code == 200, r.text
    evs = parse_sse(r.text)
    assert "error" not in [e["type"] for e in evs], evs
    meta = evs[0]
    ids = [n["id"] for n in meta["nodes"]]
    assert "research_role" in ids and "generate_event" in ids and "select_event" not in ids
    ends = _nodes(evs)
    assert "research_role" in ends and ends["generate_event"]["summary"].startswith("Wrote moment 1 of 5")
    p = _interrupt(evs)
    assert p["mode"] == "occupation" and p["occupation"]["onet_soc"] == soc
    assert len(p["event"]["choices"]) == 3 and all(set(c) == {"choice_id", "text"} for c in p["event"]["choices"])
    assert len(p["coworkers"]) == 3 and all(c["id"].startswith("gen_cw_") for c in p["coworkers"])
    assert p["selection"]["gain_bits"] is not None
    tid = meta["thread_id"]
    first_id = p["event"]["event_id"]
    r = client.post(f"/api/sim/{tid}/choose", json={"choice_id": "a"}, headers=headers)
    evs = parse_sse(r.text)
    assert "error" not in [e["type"] for e in evs], evs
    ends = _nodes(evs)
    assert sum(1 for n in ends if n.startswith("coworker:gen_cw_")) == 3
    p2 = _interrupt(evs)
    assert p2["event"]["event_id"] != first_id and p2["index"] == 2
    # custom answer works on generated moments too
    r = client.post(f"/api/sim/{tid}/choose", json={"choice_id": "custom", "text": "Ask the team to help and check it."}, headers=headers)
    assert _interrupt(parse_sse(r.text))["index"] == 3


def test_any_career_full_day_report(live_client):
    client, headers = live_client
    r = client.post("/api/sim/start", json={"title": "chef"}, headers=headers)
    evs = parse_sse(r.text)
    tid = evs[0]["thread_id"]
    for _ in range(8):
        if not [e for e in evs if e["type"] == "interrupt"]:
            break
        evs = parse_sse(client.post(f"/api/sim/{tid}/choose", json={"choice_id": "b"}, headers=headers).text)
    done = [e for e in evs if e["type"] == "done"]
    assert done, [e["type"] for e in evs]
    rep = done[0]["result"]["report"]
    occ = rep["occupation"]
    assert occ["fit"]["method"] in ("career_fit", "cosine") and occ["fit"]["rank"] >= 1
    assert occ["fit"]["method"] == ("career_fit" if occ["in_fit_classes"] else "cosine")
    assert len(rep["top_careers"]) == 3 and 5 <= rep["events_played"] <= 6
    assert rep["summary"]["text"].startswith("You tried a day as")


def test_validate_generated_rejects_bad_schema():
    from foothold.graphs import sim

    cws = [{"id": "gen_cw_1"}]
    bad = sim._gen_schema().model_validate({"title": "T", "text": "Something happens here today at work.", "choices": [
        {"choice_id": "a", "text": "x", "trait_deltas": [{"trait_id": "initiative", "delta": 3}],
         "stat_deltas": {"safety": 99, "output": 0, "team_trust": 0, "stress": 0}, "coworker_hints": []}]})
    assert sim.validate_generated(bad, cws) is None  # fewer than 3 choices
    ok = sim._gen_schema().model_validate({"title": "T", "text": "Something happens here today at work.", "choices": [
        {"choice_id": c, "text": "do it", "trait_deltas": [{"trait_id": "initiative", "delta": 3}, {"trait_id": "empathy", "delta": -0.2}],
         "stat_deltas": {"safety": 99, "output": -40, "team_trust": 0, "stress": 0},
         "coworker_hints": [{"coworker_id": "gen_cw_1", "hint": "ok"}, {"coworker_id": "nobody", "hint": "x"}]} for c in "abc"]})
    out = sim.validate_generated(ok, cws)
    assert out and [c["choice_id"] for c in out["choices"]] == ["a", "b", "c"]
    c0 = out["choices"][0]
    assert c0["trait_deltas"]["initiative"] == 1.0 and c0["stat_deltas"]["safety"] == 15 and c0["stat_deltas"]["output"] == -15
    assert set(c0["coworker_hints"]) == {"gen_cw_1"}


def test_start_unknown_occupation(live_client):
    client, headers = live_client
    assert client.post("/api/sim/start", json={"onet_soc": "99-9999.99"}, headers=headers).status_code == 400
    r = client.post("/api/sim/start", json={"onet_soc": "49-3031.00"}, headers=headers)  # core career -> authored day
    p = _interrupt(parse_sse(r.text))
    assert p["mode"] == "career" and p["career_id"] == "diesel_mechanic"
