"""Graph routes: sample layout + recommendations (baseline when the trained recommender is absent)."""

from __future__ import annotations

from _slice_fixtures import app_client, slice_env, token  # noqa: F401

from foothold import consent


def test_sample_graph_has_positions_and_is_deterministic(app_client):
    from foothold.routes import graph

    graph._sample_cache.clear()
    a = app_client.get("/api/graph/sample").json()
    assert a["available"] is True and a["provenance"] == "SYNTHETIC"
    types = {n["type"] for n in a["nodes"]}
    assert {"learner", "neighborhood"} <= types
    ids = {n["id"] for n in a["nodes"]}
    assert all(link["source"] in ids and link["target"] in ids for link in a["links"])
    graph._sample_cache.clear()
    b = app_client.get("/api/graph/sample").json()
    assert [(n["id"], n["x"], n["y"]) for n in a["nodes"]] == [(n["id"], n["x"], n["y"]) for n in b["nodes"]]
    assert all("Test Person" not in str(n) for n in a["nodes"])


def test_recommend_me_and_demand_boost_labels(app_client):
    luis = token(app_client, "luis")
    assert app_client.get("/api/graph/recommend/me").status_code == 401
    emp = token(app_client, "tri_valley_freight")
    assert app_client.get("/api/graph/recommend/me", headers=emp).status_code == 403
    r = app_client.get("/api/graph/recommend/me?model=pop&k=5", headers=luis).json()
    assert r["learner_id"] == "luis" and r["model_requested"] == "pop"
    assert len(r["items"]) <= 5
    consent.write_skill_demand([{
        "skill_id": "osha_safety", "skill_name": "OSHA safety", "postings": 3, "required": 2, "demand_score": 0.8,
        "pool_size": 25, "pool_with_skill": 10, "coverage": 0.4, "gap": 0.6, "suppressed": False,
    }])
    r2 = app_client.get("/api/graph/recommend/maya?model=gnn&k=10").json()
    assert r2["demand"]["demand_skills"] == 1
    for it in r2["items"]:
        assert it["path"] and it["path"][0]["type"] == "learner"
        if it["demand_boost"]:
            assert it["score"] > it["base_score"] and "Employer demand" in it["demand_boost"]["label"]
    assert app_client.get("/api/graph/recommend/nobody_here").status_code == 404
    assert app_client.get("/api/graph/recommend/maya?model=bogus").status_code == 422
