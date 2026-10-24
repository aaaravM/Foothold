"""Availability parsing, recommender-backed ranking, public_config helpers."""

from __future__ import annotations

import httpx
import pytest

from foothold import consent, db


@pytest.mark.parametrize("text,hours", [
    ("weekdays after 2:30 pm; summers full-time", None),
    ("after school and Saturdays (about 10 h/week)", 10),
    ("part-time (20 h/week)", 20),
    ("15 hours", 15),
    ("12 hrs a week", 12),
    ("evenings 6-9 pm", None),
    ("8 hour shifts", None),
    ("full-time", None),
])
def test_parse_hours_per_week(text, hours):
    assert consent.parse_hours_per_week(text) == hours


def test_explicit_hours_field_wins():
    card = {"blind": {"availability": "weekdays after 2:30 pm", "availability_hours_per_week": 18}}
    assert consent._availability(card)["hours_per_week"] == 18
    assert consent._availability({"blind": {"availability": "weekdays after 2:30 pm"}})["hours_per_week"] is None


def test_luis_not_filtered_by_min_hours():
    luis = next((c for c in consent.pool() if c.get("persona_id") == "luis"), None)
    if luis is None:
        pytest.skip("talent pool not built")
    blind = consent.blind_card(luis)
    assert blind["availability"]["hours_per_week"] is None
    assert consent.passes_filters(blind, min_hours=20)


def test_public_config_upsert_and_delete(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_test")
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append((req.method, req.url.path, dict(req.url.params)))
        return httpx.Response(201 if req.method == "POST" else 200, json=[])

    ok, reason = db.set_public_config("api_url", "https://x.trycloudflare.com", transport=httpx.MockTransport(handler))
    assert ok and reason == "ok"
    assert seen[-1][:2] == ("POST", "/rest/v1/public_config") and seen[-1][2]["on_conflict"] == "key"
    ok, _ = db.delete_public_config("api_url", transport=httpx.MockTransport(handler))
    assert ok and seen[-1][0] == "DELETE"

    ok, reason = db.set_public_config("api_url", "https://x", transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    assert not ok and "schema.sql" in reason
