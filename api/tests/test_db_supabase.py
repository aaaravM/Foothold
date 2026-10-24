"""Supabase mirror in foothold.db, against an in-memory fake PostgREST (httpx.MockTransport)."""

from __future__ import annotations

import json
from urllib.parse import parse_qs

import httpx
import pytest

from foothold import db

SECRET = "sb_secret_test_value_not_real"


class FakePostgrest:
    def __init__(self, tables=("consent_requests", "postings", "circle_posts", "progress_log", "kanban")):
        self.rows: dict[str, list[dict]] = {t: [] for t in tables}
        self.requests: list[httpx.Request] = []
        self.fail_writes = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert request.headers["apikey"] == SECRET
        assert request.headers["authorization"] == f"Bearer {SECRET}"
        table = request.url.path.rsplit("/", 1)[-1]
        if table not in self.rows:
            return httpx.Response(404, json={"code": "PGRST205", "message": "missing table"})
        q = {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}
        if request.method == "GET":
            return httpx.Response(200, json=self.rows[table][: int(q.get("limit", "1000"))])
        if self.fail_writes:
            return httpx.Response(500, json={"message": "boom"})
        body = json.loads(request.content)
        if request.method == "POST":
            key = q["on_conflict"]
            ignore = "ignore-duplicates" in request.headers.get("prefer", "")
            out = []
            for row in body if isinstance(body, list) else [body]:
                hit = next((r for r in self.rows[table] if r[key] == row[key]), None)
                if hit is None:
                    self.rows[table].append(dict(row))
                elif not ignore:
                    hit.update(row)
                out.append(row)
            return httpx.Response(201, json=out)
        if request.method == "PATCH":
            (col, cond), = [(k, v) for k, v in q.items()]
            value = cond.removeprefix("eq.")
            hits = [r for r in self.rows[table] if str(r.get(col)) == value]
            for r in hits:
                r.update(body)
            return httpx.Response(200, json=hits)
        return httpx.Response(405)


@pytest.fixture
def supa(monkeypatch, tmp_path):
    monkeypatch.setenv("FOOTHOLD_RUNTIME_DIR", str(tmp_path / "rt"))
    monkeypatch.setenv("SUPABASE_URL", "https://example-ref.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", SECRET)
    monkeypatch.setenv("DB_BACKEND", "auto")
    db.reset_remote()
    fake = FakePostgrest()
    yield fake
    db.reset_remote()


def test_mirrors_insert_update_upsert(supa):
    st = db.remote_startup(httpx.MockTransport(supa.handler), force=True)
    assert st["backend"] == "supabase" and st["reason"] == "ok"
    row = db.insert("consent_requests", {"employer_id": "e1", "candidate_id": "tc_1", "message": "hi"})
    db.update("consent_requests", row["id"], {"status": "accepted", "decided_at": db.now_iso()})
    db.upsert("kanban", {"learner_id": "maya", "items_json": [{"a": 1}], "updated_at": db.now_iso()}, key="learner_id")
    db.flush_remote()
    remote = supa.rows["consent_requests"][0]
    assert remote["id"] == row["id"] and remote["status"] == "accepted"
    assert json.loads(supa.rows["kanban"][0]["items_json"]) == [{"a": 1}]
    assert db.backend_status()["mirrored"] == 3
    # sqlite stays the read path
    assert db.query_one("SELECT status FROM consent_requests WHERE id = ?", (row["id"],))["status"] == "accepted"
    assert all(r.url.path.startswith("/rest/v1/") for r in supa.requests)


def test_startup_syncs_both_ways(supa):
    local = db.insert("postings", {"employer_id": "e1", "title": "local"})  # before Supabase is active
    supa.rows["progress_log"].append({"id": "pl_remote", "learner_id": "maya", "kind": "x",
                                      "payload_json": "{}", "created_at": "2026-01-01T00:00:00.000Z"})
    db.remote_startup(httpx.MockTransport(supa.handler), force=True)
    assert db.query_one("SELECT id FROM progress_log WHERE id = 'pl_remote'") is not None
    assert [r["id"] for r in supa.rows["postings"]] == [local["id"]]


def test_missing_tables_falls_back_to_sqlite(supa):
    fake = FakePostgrest(tables=("postings",))
    st = db.remote_startup(httpx.MockTransport(fake.handler), force=True)
    assert st["backend"] == "sqlite" and "404" in st["reason"]
    db.insert("kanban", {"learner_id": "x"})
    assert db.query_one("SELECT learner_id FROM kanban WHERE learner_id='x'")


def test_publishable_key_and_sqlite_mode_never_contact_supabase(supa, monkeypatch):
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_publishable_abc")
    assert db.remote_startup(httpx.MockTransport(supa.handler), force=True)["backend"] == "sqlite"
    monkeypatch.setenv("SUPABASE_SECRET_KEY", SECRET)
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    assert db.remote_startup(httpx.MockTransport(supa.handler), force=True)["reason"] == "DB_BACKEND=sqlite"
    assert supa.requests == []


def test_remote_write_failure_keeps_local_row(supa):
    db.remote_startup(httpx.MockTransport(supa.handler), force=True)
    supa.fail_writes = True
    row = db.insert("circle_posts", {"circle_id": "c1", "handle": "h", "text": "t"})
    db.flush_remote()
    assert db.query_one("SELECT id FROM circle_posts WHERE id = ?", (row["id"],))
    assert db.backend_status()["errors"] == 1


def test_status_never_contains_secret(supa):
    db.remote_startup(httpx.MockTransport(supa.handler), force=True)
    assert SECRET not in json.dumps(db.backend_status())
