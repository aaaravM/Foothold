"""Accounts and per-tab session tokens (CONTRACTS section 13).

All accounts are FICTIONAL demo accounts. Each browser tab signs in on its own and
keeps its token in sessionStorage, so the presenter can hold a learner tab and an
employer tab side by side.

* ``accounts`` table (created here with CREATE TABLE IF NOT EXISTS) seeded
  idempotently from the built-in demo identities below, enriched with names from
  ``data/processed/personas.json`` when it exists. Emails and demo passwords are
  canonical in code so the sign-in page's demo list always works.
* Passwords: stdlib scrypt with a per-account random salt, constant-time compare.
* Tokens: ``base64url(payload JSON) + "." + base64url(HMAC-SHA256)`` signed with a key
  derived from ``AUTH_SECRET`` (repo ``.env``; an ephemeral secret is generated, with
  a warning, when it is missing). Payload ``{sub, kind, iat, exp, jti}``; 12 h expiry.
  Logout revokes the token's ``jti``.
* Never logs passwords, tokens, emails or the secret.

Use in other route modules (identity comes from the token, never from the body)::

    from foothold.auth import Account, CurrentAccount, EmployerAccount, LearnerAccount, OptionalAccount

    @router.post("/consent-requests")
    def create_request(body: ConsentIn, employer: EmployerAccount): ...   # 401 / 403 handled
    employer.persona_id  # "tri_valley_freight"

    @router.get("/inbox")
    def inbox(learner: LearnerAccount):
        card_id = auth.candidate_id_for(learner)                       # talent-pool card or None

Equivalent explicit forms: ``Depends(auth.current_account)``,
``Depends(auth.require_kind("employer"))``, ``Depends(auth.optional_account)``.
"""

from __future__ import annotations

import base64
import binascii
import functools
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Any, Callable, Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from . import config, data, db

log = logging.getLogger("foothold.auth")

AccountKind = Literal["learner", "employer"]
KINDS: tuple[str, ...] = ("learner", "employer")

TOKEN_TTL_SECONDS = 12 * 3600
CLOCK_SKEW_SECONDS = 60
MAX_TOKEN_LENGTH = 2048
MAX_EMAIL_LENGTH = 254
MAX_PASSWORD_LENGTH = 1024

# scrypt cost: N=2^15, r=8, p=1 (32 MiB, ~80 ms on the demo laptop).
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SALT_BYTES = 16

# Failed-login slowdown (per email and per client): base * 2^(failures-1), capped.
FAIL_WINDOW_SECONDS = 300
FAIL_BASE_DELAY_SECONDS = 0.4
FAIL_MAX_DELAY_SECONDS = 3.0

_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
_B64URL_RE = re.compile(r"^[A-Za-z0-9_-]*$")
_SIGNING_LABEL = b"foothold.session.v1"

# ---------------------------------------------------------------------------
# Account model and demo identities
# ---------------------------------------------------------------------------


class Account(BaseModel):
    """Public account shape (CONTRACTS section 13). Never carries the password hash."""

    model_config = ConfigDict(frozen=True)

    id: str
    kind: AccountKind
    display_name: str
    persona_id: str
    email: str
    initials: str
    org: str | None = None


@dataclass(frozen=True)
class DemoIdentity:
    persona_id: str
    kind: str
    display_name: str
    email: str
    password: str
    initials: str
    org: str | None = None

    @property
    def account_id(self) -> str:
        return f"acct_{self.persona_id}"


# FICTIONAL people and employer. Reserved example domains only (RFC 2606).
# The web mirrors these in web/src/lib/auth.ts (DEMO_ACCOUNTS) for the sign-in helper.
DEMO_IDENTITIES: tuple[DemoIdentity, ...] = (
    DemoIdentity("maya", "learner", "Maya Ortiz", "maya.ortiz@example.com", "valley-maya-01", "MO"),
    DemoIdentity("dev", "learner", "Dev Sandhu", "dev.sandhu@example.com", "valley-dev-02", "DS"),
    DemoIdentity("luis", "learner", "Luis Navarro", "luis.navarro@example.com", "valley-luis-03", "LN"),
    DemoIdentity(
        "tri_valley_freight",
        "employer",
        "Tri-Valley Freight",
        "hiring@trivalleyfreight.example.org",
        "valley-freight-04",
        "TVF",
        org="Tri-Valley Freight",
    ),
)
_IDENTITY_BY_PERSONA = {d.persona_id: d for d in DEMO_IDENTITIES}

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_NOW = "(strftime('%Y-%m-%dT%H:%M:%fZ','now'))"

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS accounts (
    id            TEXT PRIMARY KEY NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN ('learner', 'employer')),
    display_name  TEXT NOT NULL,
    persona_id    TEXT NOT NULL UNIQUE,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    initials      TEXT NOT NULL,
    org           TEXT,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT {_NOW}
);
CREATE TABLE IF NOT EXISTS auth_revoked_tokens (
    jti        TEXT PRIMARY KEY NOT NULL,
    expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_auth_revoked_exp ON auth_revoked_tokens (expires_at);
"""

_ACCOUNT_COLUMNS = "id, kind, display_name, persona_id, email, initials, org"

_state_lock = threading.Lock()
_schema_ready: set[str] = set()
_seeded_for: dict[str, Any] = {}
_MISSING = object()


def _db_key() -> str:
    return str(config.db_path())


def ensure_schema() -> None:
    key = _db_key()
    if key in _schema_ready:
        return
    with db.connect() as conn:
        conn.executescript(SCHEMA)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(accounts)").fetchall()}
        if "profile_json" not in cols:  # safe additive migration (profiles + sign-up)
            conn.execute("ALTER TABLE accounts ADD COLUMN profile_json TEXT")
    _schema_ready.add(key)


def _personas_fingerprint() -> tuple[int, int] | None:
    try:
        st = (config.PROCESSED_DIR / "personas.json").stat()
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def ensure_ready() -> None:
    """Create the tables and seed the demo accounts (idempotent; re-seeds when personas.json changes)."""
    key = _db_key()
    fingerprint = _personas_fingerprint()
    if _seeded_for.get(key, _MISSING) == fingerprint:
        return
    with _state_lock:
        if _seeded_for.get(key, _MISSING) == fingerprint:
            return
        ensure_schema()
        seed_accounts()
        _seeded_for[key] = fingerprint


def reset_state() -> None:
    """Forget cached schema/seed state and login failures (tests)."""
    with _state_lock:
        _schema_ready.clear()
        _seeded_for.clear()
    with _fail_lock:
        _failures.clear()


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


def make_initials(name: str, kind: str = "learner") -> str:
    words = [w for w in re.split(r"[\s\-]+", name.strip()) if w and w[0].isalnum()]
    if not words:
        return "?"
    if kind == "employer":
        letters = [w[0] for w in words[:3]]
    else:
        letters = [words[0][0]] + ([words[-1][0]] if len(words) > 1 else [])
    return "".join(letters).upper()


def _persona_records() -> dict[str, dict[str, Any]]:
    """personas.json records keyed by persona id (any of the shapes data.py accepts)."""
    out: dict[str, dict[str, Any]] = {}
    for rec in data.persona_list():
        if isinstance(rec, dict):
            pid = rec.get("id") or rec.get("persona_id")
            if isinstance(pid, str) and pid:
                out[pid] = rec
    raw = data.personas()
    if not out and isinstance(raw, dict):
        for pid, rec in raw.items():
            if pid in _IDENTITY_BY_PERSONA and isinstance(rec, dict):
                out[pid] = {"id": pid, **rec}
    return out


def _clean_str(value: Any, limit: int = 80) -> str | None:
    if isinstance(value, str):
        value = " ".join(value.split())
        if value:
            return value[:limit]
    return None


def _account_spec(identity: DemoIdentity, rec: dict[str, Any] | None) -> dict[str, Any]:
    """Row values for one demo identity, enriched with personas.json names when present."""
    rec = rec or {}
    kind = identity.kind  # fixed by the contract (personas.json cannot flip it)

    display = _clean_str(rec.get("display_name")) or _clean_str(rec.get("full_name"))
    name = _clean_str(rec.get("name"))
    if not display and name and (kind == "employer" or " " in name):
        display = name  # a full name, not just "Maya"
    display = display or identity.display_name

    org = None
    if kind == "employer":
        org = (
            _clean_str(rec.get("org"))
            or _clean_str(rec.get("organization"))
            or _clean_str(rec.get("company"))
            or identity.org
            or display
        )
    initials = identity.initials if display == identity.display_name else make_initials(display, kind)
    return {
        "id": identity.account_id,
        "kind": kind,
        "display_name": display,
        "persona_id": identity.persona_id,
        "email": identity.email.lower(),
        "initials": initials,
        "org": org,
    }


def seed_accounts(*, reset_passwords: bool = False) -> list[Account]:
    """Insert missing demo accounts and refresh their public fields. Existing password
    hashes are kept unless ``reset_passwords`` (hashing only happens for new rows)."""
    records = _persona_records()
    extra = sorted(set(records) - set(_IDENTITY_BY_PERSONA))
    if extra:
        log.info("personas.json has %d persona(s) without a demo account; skipped", len(extra))
    for identity in DEMO_IDENTITIES:
        spec = _account_spec(identity, records.get(identity.persona_id))
        try:
            existing = db.query_one("SELECT id FROM accounts WHERE id = ?", (spec["id"],))
            if existing is None:
                db.execute(
                    "INSERT INTO accounts (id, kind, display_name, persona_id, email, initials, org, password_hash) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING",
                    (
                        spec["id"],
                        spec["kind"],
                        spec["display_name"],
                        spec["persona_id"],
                        spec["email"],
                        spec["initials"],
                        spec["org"],
                        hash_password(identity.password),
                    ),
                )
            else:
                fields = {k: v for k, v in spec.items() if k != "id"}
                if reset_passwords:
                    fields["password_hash"] = hash_password(identity.password)
                db.update("accounts", spec["id"], fields)
        except sqlite3.IntegrityError:
            log.warning("demo account %s conflicts with an existing row; left unchanged", spec["id"])
    return list_accounts()


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    if not isinstance(text, str) or not _B64URL_RE.fullmatch(text):
        raise ValueError("not base64url")
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (binascii.Error, ValueError) as exc:
        raise ValueError("not base64url") from exc


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=dklen, maxmem=2 * 128 * r * n + 1024 * 1024
    )


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """``scrypt$N$r$p$<salt>$<hash>`` (base64url parts)."""
    salt = salt if salt is not None else secrets.token_bytes(SALT_BYTES)
    derived = _scrypt(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P, SCRYPT_DKLEN)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64e(salt)}${_b64e(derived)}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time check of ``password`` against an encoded scrypt hash. Never raises."""
    try:
        algo, n_s, r_s, p_s, salt_s, hash_s = str(encoded).split("$")
        n, r, p = int(n_s), int(r_s), int(p_s)
        if algo != "scrypt" or n < 2 or n & (n - 1) or not (2**10 <= n <= 2**17 and 1 <= r <= 16 and 1 <= p <= 4):
            return False
        expected = _b64d(hash_s)
        if not 16 <= len(expected) <= 64:
            return False
        derived = _scrypt(password, _b64d(salt_s), n, r, p, len(expected))
    except (ValueError, TypeError, MemoryError):
        return False
    return hmac.compare_digest(derived, expected)


@functools.lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """A real hash of a random secret: verifying against it costs what a real check costs."""
    return hash_password(secrets.token_urlsafe(16))


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


class TokenError(Exception):
    """Invalid session token. ``reason``: malformed | signature | expired | revoked | unknown_account."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class TokenClaims:
    sub: str
    kind: str
    iat: int
    exp: int
    jti: str

    @property
    def expires_at(self) -> str:
        return iso_utc(self.exp)


@dataclass(frozen=True)
class Session:
    account: Account
    claims: TokenClaims


_ephemeral_lock = threading.Lock()
_ephemeral_secret: str | None = None
_warned_short_secret = False


def _secret() -> str:
    global _ephemeral_secret, _warned_short_secret
    value = (os.environ.get("AUTH_SECRET") or "").strip()
    if value:
        if len(value) < 16 and not _warned_short_secret:
            _warned_short_secret = True
            log.warning("AUTH_SECRET is shorter than 16 characters; use a long random value")
        return value
    with _ephemeral_lock:
        if _ephemeral_secret is None:
            _ephemeral_secret = secrets.token_urlsafe(32)
            log.warning("AUTH_SECRET is not set; using an ephemeral secret (sessions end when the API restarts)")
        return _ephemeral_secret


def _signing_key() -> bytes:
    return hmac.new(_secret().encode("utf-8"), _SIGNING_LABEL, hashlib.sha256).digest()


def _sign(body: str) -> bytes:
    return hmac.new(_signing_key(), body.encode("ascii"), hashlib.sha256).digest()


def iso_utc(ts: int | float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def issue_token(account: Account, *, now: float | None = None, ttl: int = TOKEN_TTL_SECONDS) -> tuple[str, TokenClaims]:
    """Signed session token for ``account`` plus its claims."""
    iat = int(time.time() if now is None else now)
    claims = TokenClaims(sub=account.id, kind=account.kind, iat=iat, exp=iat + int(ttl), jti=secrets.token_urlsafe(12))
    payload = {"sub": claims.sub, "kind": claims.kind, "iat": claims.iat, "exp": claims.exp, "jti": claims.jti}
    body = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return f"{body}.{_b64e(_sign(body))}", claims


def decode_token(token: str, *, now: float | None = None) -> TokenClaims:
    """Verify signature, shape and expiry. Raises :class:`TokenError` (does not check revocation)."""
    if not isinstance(token, str) or len(token) > MAX_TOKEN_LENGTH or not _TOKEN_RE.fullmatch(token):
        raise TokenError("malformed")
    body, sig = token.split(".")
    try:
        given = _b64d(sig)
    except ValueError:
        raise TokenError("malformed") from None
    if not hmac.compare_digest(_sign(body), given):
        raise TokenError("signature")
    try:
        payload = json.loads(_b64d(body).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise TokenError("malformed") from None
    if not isinstance(payload, dict):
        raise TokenError("malformed")
    sub, kind, iat, exp, jti = (payload.get(k) for k in ("sub", "kind", "iat", "exp", "jti"))
    if not (
        isinstance(sub, str)
        and sub
        and kind in KINDS
        and type(iat) is int
        and type(exp) is int
        and isinstance(jti, str)
        and jti
    ):
        raise TokenError("malformed")
    t = time.time() if now is None else now
    if exp <= t:
        raise TokenError("expired")
    if iat > t + CLOCK_SKEW_SECONDS or exp - iat > TOKEN_TTL_SECONDS + CLOCK_SKEW_SECONDS:
        raise TokenError("malformed")
    return TokenClaims(sub=sub, kind=str(kind), iat=iat, exp=exp, jti=jti)


def revoke(claims: TokenClaims) -> None:
    ensure_ready()
    db.execute("INSERT OR IGNORE INTO auth_revoked_tokens (jti, expires_at) VALUES (?, ?)", (claims.jti, claims.exp))
    db.execute("DELETE FROM auth_revoked_tokens WHERE expires_at < ?", (int(time.time()),))


def is_revoked(jti: str) -> bool:
    return db.query_one("SELECT 1 AS hit FROM auth_revoked_tokens WHERE jti = ?", (jti,)) is not None


def session_from_token(token: str) -> Session:
    """Decode + revocation + account lookup. Raises :class:`TokenError`."""
    claims = decode_token(token)
    ensure_ready()
    if is_revoked(claims.jti):
        raise TokenError("revoked")
    account = get_account(claims.sub)
    if account is None or account.kind != claims.kind:
        raise TokenError("unknown_account")
    return Session(account=account, claims=claims)


def account_from_token(token: str) -> Account:
    return session_from_token(token).account


# ---------------------------------------------------------------------------
# Account lookups
# ---------------------------------------------------------------------------


def _to_account(row: dict[str, Any]) -> Account:
    return Account(
        id=row["id"],
        kind=row["kind"],
        display_name=row["display_name"],
        persona_id=row["persona_id"],
        email=row["email"],
        initials=row["initials"],
        org=row.get("org"),
    )


def get_account(account_id: str) -> Account | None:
    ensure_ready()
    row = db.query_one(f"SELECT {_ACCOUNT_COLUMNS} FROM accounts WHERE id = ?", (account_id,))
    return _to_account(row) if row else None


def get_account_by_persona(persona_id: str) -> Account | None:
    ensure_ready()
    row = db.query_one(f"SELECT {_ACCOUNT_COLUMNS} FROM accounts WHERE persona_id = ?", (persona_id,))
    return _to_account(row) if row else None


def list_accounts() -> list[Account]:
    ensure_schema()
    rows = db.query(f"SELECT {_ACCOUNT_COLUMNS} FROM accounts ORDER BY kind DESC, id")
    return [_to_account(r) for r in rows]


def normalize_email(email: str) -> str:
    return " ".join(str(email or "").split()).lower()


def authenticate(email: str, password: str) -> Account | None:
    """Account for valid credentials, else None. Unknown emails cost the same as wrong passwords."""
    ensure_ready()
    email = normalize_email(email)
    if not email or not password or len(email) > MAX_EMAIL_LENGTH or len(password) > MAX_PASSWORD_LENGTH:
        verify_password("x", _dummy_hash())
        return None
    row = db.query_one(f"SELECT {_ACCOUNT_COLUMNS}, password_hash FROM accounts WHERE email = ?", (email,))
    if row is None:
        verify_password(password, _dummy_hash())
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return _to_account(row)


# ---------------------------------------------------------------------------
# Failed-login slowdown (in-memory, per process)
# ---------------------------------------------------------------------------

_fail_lock = threading.Lock()
_failures: dict[str, tuple[int, float]] = {}


def failure_delay(count: int) -> float:
    if count <= 0:
        return 0.0
    return min(FAIL_BASE_DELAY_SECONDS * (2 ** (count - 1)), FAIL_MAX_DELAY_SECONDS)


def register_failed_login(*keys: str, now: float | None = None) -> float:
    """Record a failure for each key (e.g. email, client address); returns the pause in seconds."""
    t = time.time() if now is None else now
    worst = 0
    with _fail_lock:
        if len(_failures) > 2048:
            for k in [k for k, (_, first) in _failures.items() if t - first > FAIL_WINDOW_SECONDS]:
                _failures.pop(k, None)
        for key in keys:
            if not key:
                continue
            count, first = _failures.get(key, (0, t))
            if t - first > FAIL_WINDOW_SECONDS:
                count, first = 0, t
            count += 1
            _failures[key] = (count, first)
            worst = max(worst, count)
    return failure_delay(worst)


def clear_failed_logins(*keys: str) -> None:
    with _fail_lock:
        for key in keys:
            _failures.pop(key, None)


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="FootholdSession",
    description="Per-tab session token from POST /api/auth/login (Authorization: Bearer <token>).",
)


def unauthorized(detail: str = "Sign in required") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def current_session(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> Session:
    if credentials is None or not credentials.credentials:
        raise unauthorized("Sign in required")
    try:
        return session_from_token(credentials.credentials)
    except TokenError as exc:
        raise unauthorized("Session expired" if exc.reason == "expired" else "Invalid session") from None


def current_account(session: Session = Depends(current_session)) -> Account:
    """The signed-in account (401 if the request has no valid session)."""
    return session.account


def optional_account(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> Account | None:
    """The signed-in account, or None for anonymous requests or invalid/expired tokens (public endpoints)."""
    if credentials is None or not credentials.credentials:
        return None
    try:
        return account_from_token(credentials.credentials)
    except TokenError:
        return None


@functools.lru_cache(maxsize=None)
def require_kind(kind: str) -> Callable[..., Account]:
    """Dependency factory: the signed-in account if it is a ``kind`` account (401 signed out, 403 wrong kind)."""
    if kind not in KINDS:
        raise ValueError(f"unknown account kind: {kind!r}")

    def dependency(account: Account = Depends(current_account)) -> Account:
        if account.kind != kind:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"This needs a {kind} account")
        return account

    dependency.__name__ = f"require_{kind}"
    return dependency


CurrentAccount = Annotated[Account, Depends(current_account)]
OptionalAccount = Annotated[Account | None, Depends(optional_account)]
LearnerAccount = Annotated[Account, Depends(require_kind("learner"))]
EmployerAccount = Annotated[Account, Depends(require_kind("employer"))]

# ---------------------------------------------------------------------------
# Talent-pool mapping (learner account <-> blind talent card)
# ---------------------------------------------------------------------------

_PERSONA_KEYS = ("persona_id", "persona", "learner_persona_id")
_NESTED_KEYS = ("hidden", "private", "identity", "contact")
_CARD_ID_KEYS = ("id", "candidate_id", "card_id")


def _card_persona(card: dict[str, Any]) -> str | None:
    for key in _PERSONA_KEYS:
        value = card.get(key)
        if isinstance(value, str) and value:
            return value
    for nest in _NESTED_KEYS:
        sub = card.get(nest)
        if isinstance(sub, dict):
            for key in _PERSONA_KEYS:
                value = sub.get(key)
                if isinstance(value, str) and value:
                    return value
    return None


def card_id(card: dict[str, Any]) -> str | None:
    for key in _CARD_ID_KEYS:
        value = card.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def talent_pool() -> list[dict[str, Any]]:
    """Synthetic talent pool plus opted-in cards of self-registered learners."""
    from . import profiles  # lazy: profiles imports auth

    return list(data.talent_pool()) + profiles.user_cards()


def candidate_for_persona(persona_id: str) -> dict[str, Any] | None:
    """The talent-pool card whose persona_id matches (synthetic pool or a registered learner's card), else None."""
    for card in talent_pool():
        if isinstance(card, dict) and _card_persona(card) == persona_id:
            return card
    return None


def candidate_for_account(account: Account) -> dict[str, Any] | None:
    """Learners only: the account's own talent card (treat as read-only)."""
    if account.kind != "learner":
        return None
    return candidate_for_persona(account.persona_id)


def candidate_id_for(account: Account) -> str | None:
    card = candidate_for_account(account)
    return card_id(card) if card else None


def persona_for_candidate(candidate_id: str) -> str | None:
    for card in talent_pool():
        if isinstance(card, dict) and card_id(card) == candidate_id:
            return _card_persona(card)
    return None


def account_for_candidate(candidate_id: str) -> Account | None:
    """The learner account that owns a talent card (None for synthetic-only cards)."""
    persona_id = persona_for_candidate(candidate_id)
    return get_account_by_persona(persona_id) if persona_id else None


__all__ = [
    "Account",
    "AccountKind",
    "CurrentAccount",
    "DEMO_IDENTITIES",
    "EmployerAccount",
    "LearnerAccount",
    "OptionalAccount",
    "Session",
    "TokenClaims",
    "TokenError",
    "account_for_candidate",
    "account_from_token",
    "authenticate",
    "bearer_scheme",
    "candidate_for_account",
    "candidate_for_persona",
    "candidate_id_for",
    "current_account",
    "current_session",
    "decode_token",
    "ensure_ready",
    "get_account",
    "get_account_by_persona",
    "hash_password",
    "issue_token",
    "list_accounts",
    "optional_account",
    "persona_for_candidate",
    "require_kind",
    "revoke",
    "seed_accounts",
    "talent_pool",
    "verify_password",
]
