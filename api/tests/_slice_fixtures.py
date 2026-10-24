"""Shared fixtures for the employer / circle / graph route tests (FICTIONAL talent pool, private sqlite)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from foothold import auth, consent, data

LOGISTICS = ["forklift_safety", "inventory_systems", "shipping_receiving", "spreadsheets", "osha_safety"]
OTHER = ["python", "git", "sql", "mig_welding", "blueprint_reading"]


def fake_pool() -> list[dict[str, Any]]:
    """24 synthetic cards: 12 group A / 12 group B; luis owns card tp_luis."""
    cards: list[dict[str, Any]] = []
    for i in range(24):
        skills = LOGISTICS[: (i % 5) + 1] if i % 2 == 0 else OTHER[: (i % 4) + 1] + LOGISTICS[:1]
        cards.append({
            "id": f"tp_{i:03d}",
            "fictional": True,
            "group": "A" if i < 12 else "B",
            "demonstrated_skills": [{"id": s, "level": 0.7, "evidence": "sim"} for s in skills],
            "sim_bands": {"logistics_lead": "strong"},
            "pathway_progress": {"career_id": "logistics_lead", "steps_done": 2, "steps_total": 6},
            "availability": {"hours_per_week": 20 + (i % 3) * 10, "shifts": ["day"]},
            "region": {"label": "Stockton area", "radius_miles": 15},
            "neighborhood": ["Seaport", "Midtown", "Lathrop"][i % 3],
            "target_career": "logistics_lead",
            "hidden": {"name": f"Test Person {i}", "exact_location": "123 Fictional St", "contact": {"email": f"p{i}@example.com", "phone": "209-555-0100"}},
        })
    cards.append({
        "id": "tp_luis", "persona_id": "luis", "fictional": True, "group": "B",
        "demonstrated_skills": [{"id": s} for s in LOGISTICS],
        "availability": {"hours_per_week": 30}, "region": {"label": "Stockton area"},
        "target_career": "logistics_lead",
        "hidden": {"name": "Luis Navarro", "exact_location": "Fictional Ave, Stockton", "contact": {"email": "luis.navarro@example.com", "phone": "209-555-0123"}},
    })
    return cards


@pytest.fixture
def slice_env(monkeypatch, tmp_path):
    monkeypatch.setenv("FOOTHOLD_RUNTIME_DIR", str(tmp_path / "rt"))
    monkeypatch.setenv("AUTH_SECRET", "test-secret-for-slice-tests-0123456789")
    monkeypatch.setattr(auth, "SCRYPT_N", 2**10)
    monkeypatch.setattr(auth, "FAIL_BASE_DELAY_SECONDS", 0.01)
    pool = fake_pool()
    monkeypatch.setattr(data, "talent_pool", lambda: pool)
    data.clear_cache()
    auth.reset_state()
    consent.reset_state()
    auth._dummy_hash.cache_clear()
    yield pool
    auth.reset_state()
    consent.reset_state()


@pytest.fixture
def app_client(slice_env):
    from foothold.routes import auth as auth_routes
    from foothold.routes import circle, employer, graph

    app = FastAPI()
    for r in (auth_routes.router, employer.router, circle.router, graph.router):
        app.include_router(r)
    with TestClient(app) as c:
        yield c


IDENT = {d.persona_id: d for d in auth.DEMO_IDENTITIES}


def token(client: TestClient, persona_id: str) -> dict[str, str]:
    ident = IDENT[persona_id]
    r = client.post("/api/auth/login", json={"email": ident.email, "password": ident.password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def sse(text: str) -> list[dict[str, Any]]:
    out = []
    for block in text.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data: "):
                out.append(json.loads(line[6:]))
    return out
