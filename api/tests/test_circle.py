"""Circle routes: posts + moderation visibility, coach SSE (crisis first), EQ feedback (offline mock)."""

from __future__ import annotations

from _slice_fixtures import app_client, slice_env, sse, token  # noqa: F401


def test_circles_and_posts_visibility(app_client):
    circles = app_client.get("/api/circle/circles").json()["circles"]
    assert circles
    cid = circles[0]["id"]
    luis = token(app_client, "luis")
    maya = token(app_client, "maya")
    assert app_client.post(f"/api/circle/{cid}/posts", json={"text": "hi"}).status_code == 401
    ok = app_client.post(f"/api/circle/{cid}/posts", json={"text": "Anyone balancing night shift and a welding class?"}, headers=luis).json()
    assert ok["moderation"]["status"] == "approved" and ok["post"]["handle"] == "Luis N."
    held = app_client.post(f"/api/circle/{cid}/posts", json={"text": "text me at 209-555-0199"}, headers=luis).json()
    assert held["moderation"]["status"] == "held"
    mine = app_client.get(f"/api/circle/{cid}/posts", headers=luis).json()["posts"]
    theirs = app_client.get(f"/api/circle/{cid}/posts", headers=maya).json()["posts"]
    anon = app_client.get(f"/api/circle/{cid}/posts").json()["posts"]
    assert any(p["id"] == held["post"]["id"] for p in mine)
    assert not any(p["id"] == held["post"]["id"] for p in theirs + anon)
    assert any(p["id"] == ok["post"]["id"] for p in theirs)
    assert app_client.get("/api/circle/nope/posts").status_code == 404


def test_crisis_post_is_held_and_returns_988(app_client):
    cid = app_client.get("/api/circle/circles").json()["circles"][0]["id"]
    luis = token(app_client, "luis")
    r = app_client.post(f"/api/circle/{cid}/posts", json={"text": "I want to end my life"}, headers=luis).json()
    assert r["crisis"] is True and r["moderation"]["status"] == "held"
    assert "988" in r["crisis_payload"]["message"]


def test_coach_crisis_routes_to_988_and_stops(app_client):
    luis = token(app_client, "luis")
    r = app_client.post("/api/circle/coach", json={"session_id": "t1", "text": "I want to kill myself", "mode": "listening"}, headers=luis)
    events = sse(r.text)
    ran = {e["node"] for e in events if e["type"] == "node"}
    assert ran == {"safety_check"}
    done = [e for e in events if e["type"] == "done"][0]["result"]
    assert done["crisis"] is True and "988" in done["message"]
    assert "?" not in done["message"]


def test_coach_listening_redacts_and_remembers_with_opt_in(app_client):
    luis = token(app_client, "luis")
    body = {"session_id": "t2", "text": "My lead yelled at me. Email me at luis@example.com", "mode": "listening", "memory_opt_in": True}
    done = [e for e in sse(app_client.post("/api/circle/coach", json=body, headers=luis).text) if e["type"] == "done"][0]["result"]
    assert done["crisis"] is False and done["reply"]
    assert "email" in done["redactions"] and done["memory"]["saved"] is True
    body2 = {**body, "text": "It keeps happening."}
    done2 = [e for e in sse(app_client.post("/api/circle/coach", json=body2, headers=luis).text) if e["type"] == "done"][0]["result"]
    assert done2["memory"]["turns_used"] == 1
    assert app_client.post("/api/circle/coach/forget", json={"session_id": "t2"}, headers=luis).json()["forgotten"] is True
    assert app_client.post("/api/circle/coach", json=body).status_code == 401


def test_eq_scenarios_and_feedback_rubric(app_client):
    sc = app_client.get("/api/circle/eq/scenarios").json()
    assert sc["scenarios"] and [d["id"] for d in sc["rubric"]] == ["listening", "empathy", "assertiveness", "repair"]
    sid = sc["scenarios"][0]["id"]
    good = app_client.post("/api/circle/eq/feedback", json={
        "scenario_id": sid,
        "response": "It sounds like this has been stressful, and that makes sense. I need a heads-up before swaps. "
                    "Could we agree on a text by noon? I'm sorry I snapped last time; next time I'll ask first. Does that work?",
    }).json()
    bad = app_client.post("/api/circle/eq/feedback", json={"scenario_id": sid, "response": "whatever, not my problem"}).json()
    for k in ("listening", "empathy", "assertiveness", "repair"):
        assert 1 <= good["scores"][k] <= 4
    assert sum(good["scores"].values()) > sum(bad["scores"].values())
    assert good["llm"] == "mock" and good["feedback"]
    crisis = app_client.post("/api/circle/eq/feedback", json={"scenario_id": sid, "response": "I want to die"}).json()
    assert crisis["crisis"] is True
    assert app_client.post("/api/circle/eq/feedback", json={"scenario_id": "nope", "response": "hello there"}).status_code == 404
