"""Shared helpers for sim/path tests: synthetic events + programs, a signed-in client, SSE parsing."""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

TEST_SECRET = "test-secret-0123456789-abcdefghijkl"

TRAITS_A = {"attention_to_detail": 0.8, "cautiousness": 0.5, "stress_tolerance": -0.2}
TRAITS_B = {"initiative": 0.7, "adaptability": 0.4, "cautiousness": -0.3}
TRAITS_C = {"cooperation": 0.7, "empathy": 0.5, "leadership_orientation": 0.2}


def _event(eid: str, careers: list[str], clock: str, coworkers: list[str], *, crunch: bool = False) -> dict[str, Any]:
    def choice(cid: str, traits: dict[str, float], stats: dict[str, int], hint: str) -> dict[str, Any]:
        return {"choice_id": cid, "text": f"Option {cid} for {eid}", "trait_deltas": traits, "stat_deltas": stats,
                "coworker_hints": {cw: hint for cw in coworkers}}

    return {
        "event_id": eid, "career_ids": careers, "clock": clock, "title": f"Event {eid}",
        "text": f"Something happens at {clock}. You need to decide.", "crunch": crunch,
        "status": "DRAFT — needs human review",
        "choices": [
            choice("a", TRAITS_A, {"safety": 6, "output": -3, "team_trust": 2, "stress": 12}, "appreciates the care"),
            choice("b", TRAITS_B, {"safety": -4, "output": 8, "team_trust": -2, "stress": 14}, "frustrated by the shortcut"),
            choice("c", TRAITS_C, {"safety": 0, "output": 2, "team_trust": 6, "stress": 10}, "relieved you asked"),
        ],
    }


def synthetic_events() -> dict[str, Any]:
    from foothold import data

    evs: list[dict[str, Any]] = []
    for career in data.careers():
        cid = career["id"]
        cws = [c["id"] for c in career.get("coworkers") or []]
        for i, clock in enumerate(["08:00", "09:30", "11:00", "13:30", "15:00"]):
            evs.append(_event(f"{cid}_{i + 1:02d}", [cid], clock, cws))
        evs.append(_event(f"{cid}_crunch", [cid], "14:00", cws, crunch=True))
    return {"schema_version": 1, "status": "DRAFT — needs human review", "events": evs}


def patch_events(monkeypatch) -> dict[str, Any]:
    from foothold import data

    payload = synthetic_events()
    monkeypatch.setattr(data, "events", lambda: payload)
    monkeypatch.setattr(data, "events_list", lambda: payload["events"])
    return payload


def signed_in(monkeypatch, persona: str = "maya") -> dict[str, str]:
    from foothold import auth

    monkeypatch.setenv("AUTH_SECRET", TEST_SECRET)
    monkeypatch.setattr(auth, "SCRYPT_N", 2**10)
    auth.reset_state()
    auth.ensure_ready()
    acct = auth.get_account_by_persona(persona)
    token, _ = auth.issue_token(acct)
    return {"Authorization": f"Bearer {token}"}


def client_for(*routers: Any) -> TestClient:
    app = FastAPI()
    for r in routers:
        app.include_router(r)
    return TestClient(app)


def parse_sse(text: str) -> list[dict[str, Any]]:
    out = []
    for block in text.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data:"):
                out.append(json.loads(line[5:].strip()))
    return out


def _sec(sid: str, days: list[str], start: str, end: str, modality: str = "in_person") -> dict[str, Any]:
    return {"id": sid, "days": days, "start": start, "end": end, "modality": modality, "campus": "Main"}


def synthetic_programs() -> list[dict[str, Any]]:
    """Small fictional programs (SAMPLE) for planner + verifier tests."""
    return [
        {"id": "t_weld_cert", "career_id": "welder", "route_type": "certificate", "name": "Welding Certificate (test)",
         "provider": "Test College", "credential": "Certificate of Achievement in Welding", "url": "https://example.org",
         "status": "SAMPLE", "source_id": "src_test",
         "steps": [
             {"id": "weld1", "title": "Intro Welding", "kind": "course", "units": 3, "hours_per_week": 6, "weeks": 18,
              "cost_usd": 138, "prereqs": [], "sections": [_sec("w1a", ["Mon", "Wed"], "08:00", "10:50"),
                                                          _sec("w1b", ["Tue", "Thu"], "18:00", "20:50")]},
             {"id": "weld2", "title": "Arc Welding", "kind": "course", "units": 3, "hours_per_week": 6, "weeks": 18,
              "cost_usd": 138, "prereqs": ["weld1"], "sections": [_sec("w2a", ["Mon", "Wed"], "08:00", "10:50"),
                                                                 _sec("w2b", ["Tue", "Thu"], "18:00", "20:50")]},
             {"id": "blue", "title": "Blueprint Reading", "kind": "course", "units": 2, "hours_per_week": 4, "weeks": 18,
              "cost_usd": 92, "prereqs": [], "sections": [_sec("b1", ["Fri"], "09:00", "11:50"),
                                                         _sec("b2", ["Sat"], "09:00", "11:50", "online")]},
         ]},
        {"id": "t_weld_job", "career_id": "welder", "route_type": "direct_to_work", "name": "Welder helper job (test)",
         "provider": "Fictional Fab Shop", "credential": "On-the-job training", "url": None, "status": "SAMPLE",
         "source_id": "src_test",
         "steps": [{"id": "helper", "title": "Welder helper", "kind": "job", "hours_per_week": 40, "weeks": 26,
                    "cost_usd": 0, "prereqs": [], "sections": [], "paid_wage_hourly": 18.5}]},
    ]


def patch_programs(monkeypatch) -> list[dict[str, Any]]:
    from foothold import data

    progs = synthetic_programs()
    monkeypatch.setattr(data, "programs", lambda: progs)
    return progs
