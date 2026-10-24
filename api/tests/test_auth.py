"""Accounts, per-tab session tokens and auth dependencies (CONTRACTS section 13)."""

from __future__ import annotations

import json
import logging
import re
import time

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from foothold import auth, config, data, db

SHIPPED_SCRYPT_N = auth.SCRYPT_N  # captured before fixtures lower it for speed
TEST_SECRET = "test-secret-0123456789-abcdefghijkl"
IDENT = {d.persona_id: d for d in auth.DEMO_IDENTITIES}


@pytest.fixture
def auth_env(monkeypatch, tmp_path):
    """Private sqlite + processed dir (no personas.json yet), fixed secret, fast hashing."""
    monkeypatch.setenv("FOOTHOLD_RUNTIME_DIR", str(tmp_path / "rt"))
    processed = tmp_path / "processed"
    (processed / "synthetic").mkdir(parents=True)
    monkeypatch.setattr(config, "PROCESSED_DIR", processed)
    monkeypatch.setenv("AUTH_SECRET", TEST_SECRET)
    monkeypatch.setattr(auth, "SCRYPT_N", 2**10)  # verify_password reads N from each hash
    monkeypatch.setattr(auth, "FAIL_BASE_DELAY_SECONDS", 0.05)
    data.clear_cache()
    auth.reset_state()
    auth._dummy_hash.cache_clear()
    yield processed
    data.clear_cache()
    auth.reset_state()
    auth._dummy_hash.cache_clear()


@pytest.fixture
def client(auth_env):
    from foothold.routes import auth as auth_routes

    app = FastAPI()
    app.include_router(auth_routes.router)

    @app.get("/t/me")
    def t_me(account: auth.CurrentAccount):
        return {"id": account.id}

    @app.get("/t/learner")
    def t_learner(account: auth.LearnerAccount):
        return {"id": account.id}

    @app.get("/t/employer")
    def t_employer(account: auth.EmployerAccount):
        return {"id": account.id}

    @app.get("/t/explicit")
    def t_explicit(account: auth.Account = Depends(auth.require_kind("employer"))):
        return {"id": account.id}

    @app.get("/t/optional")
    def t_optional(account: auth.OptionalAccount):
        return {"id": account.id if account else None}

    with TestClient(app) as c:
        yield c


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login(client: TestClient, persona_id: str):
    ident = IDENT[persona_id]
    return client.post("/api/auth/login", json={"email": ident.email, "password": ident.password})


def login_token(client: TestClient, persona_id: str) -> str:
    r = login(client, persona_id)
    assert r.status_code == 200, r.text
    return r.json()["token"]


# ---------------------------------------------------------------------------
# Passwords and seeding
# ---------------------------------------------------------------------------


def test_password_hash_roundtrip_and_format(auth_env):
    assert SHIPPED_SCRYPT_N >= 2**15 and auth.SCRYPT_R == 8 and auth.SCRYPT_P == 1
    h1, h2 = auth.hash_password("orchard-lane"), auth.hash_password("orchard-lane")
    assert h1.startswith("scrypt$1024$8$1$") and h1 != h2  # random per-account salt
    assert "orchard-lane" not in h1
    assert auth.verify_password("orchard-lane", h1) and auth.verify_password("orchard-lane", h2)
    assert not auth.verify_password("orchard-lanE", h1)
    for bad in ("", "plain", "md5$abc", h1.replace("scrypt$", "bcrypt$"), "scrypt$1000$8$1$AAAA$AAAA",
                "scrypt$1048576$8$1$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAA", "scrypt$1024$8$1$***$***"):
        assert auth.verify_password("orchard-lane", bad) is False


def test_seed_defaults_are_fictional_and_idempotent(auth_env):
    auth.ensure_ready()
    by = {a.persona_id: a for a in auth.list_accounts()}
    assert set(by) == {"maya", "dev", "luis", "tri_valley_freight"}
    assert {by[p].kind for p in ("maya", "dev", "luis")} == {"learner"}
    employer = by["tri_valley_freight"]
    assert employer.kind == "employer" and employer.org == "Tri-Valley Freight" and employer.display_name == "Tri-Valley Freight"
    for a in by.values():
        assert re.fullmatch(r"[a-z0-9.]+@([a-z0-9-]+\.)*example\.(com|org)", a.email), a.email
        assert a.id == f"acct_{a.persona_id}" and a.initials.isupper() and a.display_name
    assert by["maya"].initials == "MO" and employer.initials == "TVF" and by["maya"].org is None

    hashes = {r["id"]: r["password_hash"] for r in db.query("SELECT id, password_hash FROM accounts")}
    for ident in auth.DEMO_IDENTITIES:
        assert hashes[ident.account_id].startswith("scrypt$") and ident.password not in hashes[ident.account_id]

    auth.reset_state()
    auth.ensure_ready()
    auth.seed_accounts()
    assert db.query_one("SELECT COUNT(*) AS n FROM accounts")["n"] == 4
    assert {r["id"]: r["password_hash"] for r in db.query("SELECT id, password_hash FROM accounts")} == hashes


def test_seed_takes_names_from_personas_json_but_keeps_credentials(auth_env, client):
    (auth_env / "personas.json").write_text(json.dumps({"personas": [
        {"id": "maya", "name": "Maya", "kind": "employer"},  # first name only, bogus kind
        {"id": "dev", "display_name": "Dev Kaler"},
        {"id": "tri_valley_freight", "name": "Tri-Valley Freight Co."},
        {"id": "someone_else", "name": "Extra Person"},
    ]}), encoding="utf-8")
    auth.ensure_ready()
    by = {a.persona_id: a for a in auth.list_accounts()}
    assert len(by) == 4 and "someone_else" not in by
    assert by["maya"].display_name == "Maya Ortiz" and by["maya"].kind == "learner"
    assert by["dev"].display_name == "Dev Kaler" and by["dev"].initials == "DK"
    assert by["dev"].email == IDENT["dev"].email
    assert by["tri_valley_freight"].display_name == "Tri-Valley Freight Co."
    assert login(client, "dev").json()["account"]["display_name"] == "Dev Kaler"

    # a rewritten personas.json is picked up without a restart
    (auth_env / "personas.json").write_text(json.dumps({"dev": {"full_name": "Dev Sandhu-Kaler"}}), encoding="utf-8")
    auth.ensure_ready()
    assert auth.get_account_by_persona("dev").display_name == "Dev Sandhu-Kaler"


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def test_login_ok_returns_signed_token_and_account(client):
    r = login(client, "maya")
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["token"].count(".") == 1
    assert body["account"] == {
        "id": "acct_maya",
        "kind": "learner",
        "display_name": "Maya Ortiz",
        "persona_id": "maya",
        "email": IDENT["maya"].email,
        "initials": "MO",
        "org": None,
    }
    claims = auth.decode_token(body["token"])
    assert claims.sub == "acct_maya" and claims.kind == "learner"
    assert claims.exp - claims.iat == 12 * 3600 and abs(claims.iat - time.time()) < 5
    assert body["expires_at"] == auth.iso_utc(claims.exp)

    employer = login(client, "tri_valley_freight").json()["account"]
    assert employer["kind"] == "employer" and employer["org"] == "Tri-Valley Freight"


def test_login_email_is_case_and_space_insensitive(client):
    ident = IDENT["luis"]
    r = client.post("/api/auth/login", json={"email": f"  {ident.email.upper()} ", "password": ident.password})
    assert r.status_code == 200 and r.json()["account"]["persona_id"] == "luis"
    assert client.post("/api/auth/login", json={"email": ident.email, "password": ident.password.upper()}).status_code == 401


def test_bad_password_and_unknown_email_get_the_same_401_after_a_pause(client):
    ident = IDENT["maya"]
    t0 = time.perf_counter()
    r1 = client.post("/api/auth/login", json={"email": ident.email, "password": "wrong-password"})
    t1 = time.perf_counter()
    r2 = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": ident.password})
    t2 = time.perf_counter()
    assert r1.status_code == r2.status_code == 401
    assert r1.json() == r2.json() == {"detail": "Email or password is incorrect."}
    assert r1.headers["www-authenticate"] == "Bearer"
    assert t1 - t0 >= 0.05  # base pause
    assert t2 - t1 >= 0.10  # same client failed twice: the pause doubles
    assert login(client, "maya").status_code == 200  # a success clears the counters
    t3 = time.perf_counter()
    client.post("/api/auth/login", json={"email": ident.email, "password": "wrong-again"})
    assert 0.05 <= time.perf_counter() - t3 < 0.5


def test_failed_login_pause_grows_caps_and_resets(auth_env, monkeypatch):
    monkeypatch.setattr(auth, "FAIL_BASE_DELAY_SECONDS", 0.4)
    assert [auth.failure_delay(n) for n in range(6)] == pytest.approx([0, 0.4, 0.8, 1.6, 3.0, 3.0])
    t = 1000.0
    assert auth.register_failed_login("email:a", "client:x", now=t) == pytest.approx(0.4)
    assert auth.register_failed_login("email:b", "client:x", now=t + 1) == pytest.approx(0.8)
    assert auth.register_failed_login("email:a", now=t + auth.FAIL_WINDOW_SECONDS + 5) == pytest.approx(0.4)
    auth.clear_failed_logins("email:a", "client:x")
    assert auth.register_failed_login("email:a", now=t + 1000) == pytest.approx(0.4)


def test_login_with_missing_fields_is_a_400(client):
    for payload in ({}, {"email": IDENT["maya"].email}, {"password": "x"}, {"email": "   ", "password": "x"}):
        r = client.post("/api/auth/login", json=payload)
        assert r.status_code == 400 and r.json() == {"detail": "Enter your email and password."}


# ---------------------------------------------------------------------------
# Tokens, /me, logout
# ---------------------------------------------------------------------------


def test_me_requires_a_valid_bearer_token(client):
    token = login_token(client, "maya")
    r = client.get("/api/auth/me", headers=bearer(token))
    assert r.status_code == 200
    body = r.json()
    assert body["account"]["id"] == "acct_maya" and body["candidate_id"] is None
    assert body["expires_at"] == auth.iso_utc(auth.decode_token(token).exp)

    for headers in ({}, {"Authorization": "Bearer"}, {"Authorization": f"Basic {token}"}, {"Authorization": token}):
        r = client.get("/api/auth/me", headers=headers)
        assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
        assert r.json() == {"detail": "Sign in required"}


def test_tampered_and_foreign_tokens_are_rejected(client, monkeypatch):
    token = login_token(client, "maya")
    body, sig = token.split(".")
    payload = json.loads(auth._b64d(body))
    payload.update(sub="acct_tri_valley_freight", kind="employer")
    forged = auth._b64e(json.dumps(payload).encode()) + "." + sig
    flipped_sig = body + "." + ("A" if sig[0] != "A" else "B") + sig[1:]
    for bad in (forged, flipped_sig, body + "x." + sig, token + ".x", token[:-1] + "!", "garbage", "a" * 3000):
        r = client.get("/api/auth/me", headers=bearer(bad))
        assert r.status_code == 401, bad[:40]
        assert r.json()["detail"] == "Invalid session"
    with pytest.raises(auth.TokenError) as exc:
        auth.decode_token(forged)
    assert exc.value.reason == "signature"

    monkeypatch.setenv("AUTH_SECRET", "a-different-secret-0123456789-xyz")
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401


def test_expired_and_overlong_tokens_are_rejected(client):
    account = auth.get_account("acct_maya")
    expired, _ = auth.issue_token(account, now=time.time() - auth.TOKEN_TTL_SECONDS - 5)
    r = client.get("/api/auth/me", headers=bearer(expired))
    assert r.status_code == 401 and r.json()["detail"] == "Session expired"
    with pytest.raises(auth.TokenError) as exc:
        auth.decode_token(expired)
    assert exc.value.reason == "expired"

    overlong, _ = auth.issue_token(account, ttl=auth.TOKEN_TTL_SECONDS * 10)
    assert client.get("/api/auth/me", headers=bearer(overlong)).status_code == 401

    almost, _ = auth.issue_token(account, now=time.time() - auth.TOKEN_TTL_SECONDS + 30)
    assert client.get("/api/auth/me", headers=bearer(almost)).status_code == 200


def test_tokens_for_deleted_accounts_stop_working(client):
    token = login_token(client, "luis")
    db.execute("DELETE FROM accounts WHERE id = ?", ("acct_luis",))
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401


def test_logout_revokes_only_that_tab(client):
    tab1, tab2 = login_token(client, "maya"), login_token(client, "maya")
    employer_tab = login_token(client, "tri_valley_freight")
    assert tab1 != tab2
    assert client.post("/api/auth/logout", headers=bearer(tab1)).json() == {"ok": True}
    assert client.get("/api/auth/me", headers=bearer(tab1)).status_code == 401
    assert client.get("/api/auth/me", headers=bearer(tab2)).json()["account"]["id"] == "acct_maya"
    assert client.get("/api/auth/me", headers=bearer(employer_tab)).json()["account"]["id"] == "acct_tri_valley_freight"
    # idempotent, and fine without (or with a broken) token
    assert client.post("/api/auth/logout", headers=bearer(tab1)).json() == {"ok": True}
    assert client.post("/api/auth/logout").json() == {"ok": True}
    assert client.post("/api/auth/logout", headers=bearer("garbage")).status_code == 200


# ---------------------------------------------------------------------------
# Dependencies for other route modules
# ---------------------------------------------------------------------------


def test_current_account_require_kind_and_optional_account(client):
    maya, employer = login_token(client, "maya"), login_token(client, "tri_valley_freight")
    assert client.get("/t/me", headers=bearer(maya)).json() == {"id": "acct_maya"}
    assert client.get("/t/learner", headers=bearer(maya)).json() == {"id": "acct_maya"}
    r = client.get("/t/employer", headers=bearer(maya))
    assert r.status_code == 403 and r.json() == {"detail": "This needs a employer account"}
    assert client.get("/t/employer", headers=bearer(employer)).json() == {"id": "acct_tri_valley_freight"}
    assert client.get("/t/explicit", headers=bearer(employer)).status_code == 200
    assert client.get("/t/learner", headers=bearer(employer)).status_code == 403
    for path in ("/t/me", "/t/learner", "/t/employer", "/t/explicit"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers=bearer("garbage")).status_code == 401

    assert client.get("/t/optional").json() == {"id": None}
    assert client.get("/t/optional", headers=bearer("garbage")).json() == {"id": None}
    assert client.get("/t/optional", headers=bearer(maya)).json() == {"id": "acct_maya"}

    assert auth.require_kind("learner") is auth.require_kind("learner")
    with pytest.raises(ValueError):
        auth.require_kind("admin")


def test_learner_accounts_map_to_their_talent_card(auth_env, client):
    (auth_env / "synthetic" / "talent_pool.json").write_text(json.dumps({"fictional": True, "talent_pool": [
        {"id": "tc_001", "fictional": True, "skills": ["forklift_operation"]},
        {"id": "tc_014", "fictional": True, "hidden": {"name": "Maya Ortiz", "persona_id": "maya"}},
        {"id": "tc_020", "fictional": True, "persona_id": "dev"},
    ]}), encoding="utf-8")
    assert auth.candidate_id_for(auth.get_account("acct_maya")) == "tc_014"
    assert auth.candidate_for_account(auth.get_account("acct_dev"))["id"] == "tc_020"
    assert auth.candidate_for_account(auth.get_account("acct_luis")) is None
    assert auth.candidate_for_account(auth.get_account("acct_tri_valley_freight")) is None
    assert auth.account_for_candidate("tc_014").id == "acct_maya"
    assert auth.account_for_candidate("tc_001") is None and auth.account_for_candidate("missing") is None
    me = client.get("/api/auth/me", headers=bearer(login_token(client, "maya"))).json()
    assert me["candidate_id"] == "tc_014"


# ---------------------------------------------------------------------------
# Secrets hygiene and wiring
# ---------------------------------------------------------------------------


def test_missing_auth_secret_uses_an_ephemeral_one_that_is_never_logged(client, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG, logger="foothold")
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    monkeypatch.setattr(auth, "_ephemeral_secret", None)
    token = login_token(client, "luis")
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 200
    assert "AUTH_SECRET is not set" in caplog.text
    assert auth._ephemeral_secret and auth._ephemeral_secret not in caplog.text


def test_logs_never_contain_passwords_tokens_or_emails(client, caplog):
    caplog.set_level(logging.DEBUG)
    ident = IDENT["maya"]
    client.post("/api/auth/login", json={"email": ident.email, "password": "hunter2-wrong"})
    token = login_token(client, "maya")
    client.get("/api/auth/me", headers=bearer(token))
    client.post("/api/auth/logout", headers=bearer(token))
    text = caplog.text
    for secret in (ident.password, "hunter2-wrong", token, token.split(".")[1], ident.email, TEST_SECRET):
        assert secret not in text
    assert "signed in: acct_maya" in text and "signed out: acct_maya" in text and "sign-in failed" in text


def test_main_app_includes_auth_routes_and_allows_the_header(auth_env):
    from main import create_app

    app = create_app()
    assert "auth" in app.state.routes_loaded, app.state.route_errors
    assert {"/api/auth/login", "/api/auth/me", "/api/auth/logout"} <= set(app.openapi()["paths"])
    with TestClient(app) as c:
        pre = c.options("/api/auth/me", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        })
        assert pre.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert "authorization" in pre.headers.get("access-control-allow-headers", "").lower()
        assert login(c, "dev").status_code == 200
