"""Sign-up, profiles, places and location-aware planning / talent search."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from _slice_fixtures import slice_env, token  # noqa: F401
from foothold import places, profiles


@pytest.fixture
def client(slice_env):
    from foothold.routes import auth as auth_routes
    from foothold.routes import circle, employer, graph, meta, path

    profiles.reset_state()
    app = FastAPI()
    for r in (auth_routes.router, employer.router, circle.router, graph.router, meta.router, path.router):
        app.include_router(r)
    with TestClient(app) as c:
        yield c
    profiles.reset_state()


def _register(c, **kw):
    body = {"display_name": "Ana Reyes", "email": "ana.reyes@example.com", "password": "longenough1", "kind": "learner"}
    body.update(kw)
    return c.post("/api/auth/register", json=body)


def _h(r) -> dict[str, str]:
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_places_and_near(client):
    r = client.get("/api/meta/places").json()
    ids = {p["id"] for p in r["places"]}
    assert {"stockton", "modesto", "fresno", "bakersfield", "sacramento"} <= ids and len(ids) >= 14
    assert any(c["id"] == "delta" for c in r["campuses"])
    near = client.get("/api/places/near?place_id=modesto").json()
    assert near["providers"][0]["place_id"] == "modesto"
    assert near["providers"] == sorted(near["providers"], key=lambda x: x["distance_km"])
    assert all("drive_minutes" in p for p in near["programs"])
    assert client.get("/api/places/near").status_code == 400
    assert client.get("/api/places/near?lat=37.0&lon=-120.0").status_code == 200


def test_register_validation_and_duplicate(client):
    assert _register(client, email="nope").status_code == 422
    assert _register(client, password="short").status_code == 422
    assert _register(client, kind="admin").status_code == 422
    assert _register(client, place_id="atlantis").status_code == 422
    r = _register(client, place_id="modesto")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["account"]["kind"] == "learner" and body["account"]["persona_id"].startswith("u_")
    assert body["profile"]["place"]["name"] == "Modesto"
    assert _register(client, email="ANA.REYES@example.com").status_code == 409
    # login works with the new password; /me works with the token
    r2 = client.post("/api/auth/login", json={"email": "ana.reyes@example.com", "password": "longenough1"})
    assert r2.status_code == 200
    me = client.get("/api/auth/me", headers=_h(r2)).json()
    assert me["account"]["display_name"] == "Ana Reyes" and me["candidate_id"] is None


def test_profile_patch_and_path_commute(client):
    h = _h(_register(client))
    prof = client.patch("/api/auth/me/profile", json={"place_id": "modesto", "hours_per_week": 15}, headers=h).json()
    assert prof["place_id"] == "modesto" and prof["hours_per_week"] == 15
    assert client.patch("/api/auth/me/profile", json={"place_id": "nowhere"}, headers=h).status_code == 422
    assert client.get("/api/auth/me/profile", headers=h).json()["place"]["name"] == "Modesto"
    res = client.post("/api/path/solve", json={"career_id": "logistics_lead", "hours_per_week": 20}, headers=h).json()
    assert res["origin"]["place_id"] == "modesto"
    commutes = [r.get("commute") for r in res["routes"].values() if r.get("commute")]
    assert commutes and all(cm["minutes_one_way"] > 0 for cm in commutes)
    # explicit place in the body wins; anonymous solve without a place has no origin
    res2 = client.post("/api/path/solve", json={"career_id": "logistics_lead", "place_id": "stockton"}).json()
    assert res2["origin"]["place_id"] == "stockton"
    assert client.post("/api/path/solve", json={"career_id": "logistics_lead"}).json()["origin"] is None


def test_demo_persona_profile_and_no_auto_origin(client):
    maya = token(client, "maya")
    prof = client.get("/api/auth/me/profile", headers=maya).json()
    assert prof["place_id"] == "stockton" and prof["commute_minutes"] == 35
    res = client.post("/api/path/solve", json={"career_id": "logistics_lead"}, headers=maya).json()
    assert res["origin"] is None  # demo plans keep the persona commute until the user saves a place


def test_opt_in_card_reaches_employer_and_inbox(client):
    h = _h(_register(client, place_id="modesto"))
    client.patch("/api/auth/me/profile", json={"talent_opt_in": True, "hours_per_week": 20}, headers=h)
    me = client.get("/api/auth/me", headers=h).json()
    assert me["candidate_id"] and me["candidate_id"].startswith("cand_u_")
    inbox = client.get("/api/employer/inbox", headers=h).json()
    cand = inbox["candidate_id"]
    assert inbox["card"]["region"]["label"] == "Modesto area"
    emp = token(client, "tri_valley_freight")
    talent = client.get("/api/employer/talent?limit=100", headers=emp).json()
    card = next(c for c in talent["cards"] if c["candidate_id"] == cand)
    assert "Ana" not in str(card)
    r = client.post("/api/employer/consent-requests", json={"candidate_id": cand, "message": "Hi"}, headers=emp)
    assert r.status_code in (200, 201), r.text
    req = client.get("/api/employer/inbox", headers=h).json()["requests"][0]
    assert client.post(f"/api/employer/consent/{req['id']}", json={"decision": "accept"}, headers=h).status_code == 200
    view = client.get(f"/api/employer/candidates/{cand}", headers=emp).json()
    assert view["consented"] and view["revealed"]["name"] == "Ana Reyes"
    # fairness audit still runs on the labelled synthetic pool
    from foothold.graphs import employer as eg

    assert eg.fairness_audit([]).get("reason") != "talent pool has no synthetic group labels"
    # opting out removes the card
    client.patch("/api/auth/me/profile", json={"talent_opt_in": False}, headers=h)
    assert client.get("/api/auth/me", headers=h).json()["candidate_id"] is None


def test_employer_register_distance_filter(client):
    r = _register(client, email="hire@valleyparts.example.org", kind="employer", org_name="Valley Parts",
                  place_id="fresno", display_name="Valley Parts Hiring")
    assert r.status_code == 201
    assert r.json()["account"]["org"] == "Valley Parts"
    h = _h(r)
    talent = client.get("/api/employer/talent?limit=100&max_km=50", headers=h).json()
    assert talent["origin"]["place_id"] == "fresno"
    assert all(c.get("distance_km") is None or c["distance_km"] <= 50 for c in talent["cards"])
    assert client.get("/api/employer/talent?limit=100", headers=h).json()["eligible"] >= talent["eligible"]


def test_graph_me_for_new_learner(client):
    h = _h(_register(client))
    r = client.get("/api/graph/recommend/me", headers=h)
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["items"], list)


def test_drive_minutes_assumption():
    assert places.drive_minutes(0) == places.PARK_WALK_MIN
    assert 30 <= places.drive_minutes(30) <= 50
    assert places.place_from_text("Stockton (San Joaquin County)")["id"] == "stockton"
