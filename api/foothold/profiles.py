"""Learner/employer profiles, sign-up and opt-in talent cards for real (self-registered) accounts.

* Profile JSON lives on ``accounts.profile_json`` (column added by ``auth.ensure_schema`` when
  missing). Demo personas without a stored profile fall back to their personas.json values.
* Opted-in learners get a blind talent card in ``user_talent_cards`` (region from their place,
  demonstrated skills from their latest sim report). :func:`user_cards` merges into the talent
  pool via ``auth.talent_pool()``; cards have no synthetic fairness group.
"""

from __future__ import annotations

import logging
import re
import secrets
import sqlite3
from typing import Any

from . import auth, data, db, places

log = logging.getLogger("foothold.profiles")

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[A-Za-z]{2,}$")
MIN_PASSWORD = 8

PROFILE_DEFAULTS: dict[str, Any] = {
    "place_id": None, "lat": None, "lon": None, "hours_per_week": 12, "budget_usd": 2000, "commute_minutes": 20,
    "current_credits": 0, "dependents": 0, "interests": [], "talent_opt_in": False,
}
_NUM_LIMITS = {"hours_per_week": (0, 80), "budget_usd": (0, 200000), "commute_minutes": (0, 240),
               "current_credits": (0, 300), "dependents": (0, 12)}

CARD_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_talent_cards (
    account_id  TEXT PRIMARY KEY NOT NULL,
    persona_id  TEXT NOT NULL UNIQUE,
    card_json   TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""
_card_ready: set[str] = set()


class ProfileError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _ensure_cards() -> None:
    key = str(db.db_path())
    if key in _card_ready:
        return
    with db.connect() as conn:
        conn.executescript(CARD_SCHEMA)
    _card_ready.add(key)


def reset_state() -> None:
    _card_ready.clear()


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


def persona_profile(persona_id: str) -> dict[str, Any]:
    """Defaults for a demo persona from personas.json (place from its region text)."""
    rec = data.get_persona(persona_id) or {}
    out: dict[str, Any] = {}
    src = rec.get("constraints") if isinstance(rec.get("constraints"), dict) else rec
    for k in _NUM_LIMITS:
        v = src.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = v
    if isinstance(rec.get("interests"), list):
        out["interests"] = [str(x)[:40] for x in rec["interests"]][:12]
    p = places.place_from_text(rec.get("region") or rec.get("location") or rec.get("city"))
    if p:
        out.update(place_id=p["id"], lat=p["lat"], lon=p["lon"])
    if auth.candidate_for_persona(persona_id) is not None:
        out["talent_opt_in"] = True
    return out


def _stored(account_id: str) -> dict[str, Any] | None:
    auth.ensure_ready()
    row = db.query_one("SELECT profile_json FROM accounts WHERE id = ?", (account_id,))
    if not row or not row.get("profile_json"):
        return None
    val = db.jloads(row["profile_json"], None)
    return val if isinstance(val, dict) else None


def get_profile(account: auth.Account) -> dict[str, Any]:
    stored = _stored(account.id)
    base = {**PROFILE_DEFAULTS}
    if stored is None:
        base.update(persona_profile(account.persona_id))
    else:
        base.update({k: v for k, v in stored.items() if k in PROFILE_DEFAULTS or k == "org_name"})
    p = places.place(base.get("place_id"))
    base["place"] = {"id": p["id"], "name": p["name"], "county": p["county"]} if p else None
    if account.kind == "employer":
        base["org_name"] = base.get("org_name") or account.org
    return base


def clean_patch(patch: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "place_id" in patch:
        pid = patch["place_id"]
        if pid in (None, ""):
            out["place_id"] = None
        else:
            p = places.place(pid)
            if p is None:
                raise ProfileError(422, "Unknown place. Pick one from the list.")
            out["place_id"] = p["id"]
            if "lat" not in patch and "lon" not in patch:
                out["lat"], out["lon"] = p["lat"], p["lon"]
    if "lat" in patch or "lon" in patch:
        lat, lon = patch.get("lat"), patch.get("lon")
        if lat is None and lon is None:
            out["lat"] = out["lon"] = None
        elif places.valid_latlon(lat, lon):
            out["lat"], out["lon"] = round(float(lat), 4), round(float(lon), 4)  # ~10 m, never more precise
        else:
            raise ProfileError(422, "Location must be a valid latitude and longitude.")
    for k, (lo, hi) in _NUM_LIMITS.items():
        if k in patch and patch[k] is not None:
            v = patch[k]
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ProfileError(422, f"{k} must be a number.")
            v = min(max(float(v), lo), hi)
            out[k] = int(v) if k == "dependents" else (int(v) if v.is_integer() else round(v, 2))
    if "interests" in patch and patch["interests"] is not None:
        if not isinstance(patch["interests"], list):
            raise ProfileError(422, "interests must be a list.")
        out["interests"] = [" ".join(str(x).split())[:40] for x in patch["interests"] if str(x).strip()][:12]
    if "talent_opt_in" in patch and patch["talent_opt_in"] is not None:
        out["talent_opt_in"] = bool(patch["talent_opt_in"])
    if "org_name" in patch and isinstance(patch["org_name"], str) and patch["org_name"].strip():
        out["org_name"] = " ".join(patch["org_name"].split())[:80]
    return out


def update_profile(account: auth.Account, patch: dict[str, Any]) -> dict[str, Any]:
    changes = clean_patch(patch)
    current = {k: v for k, v in get_profile(account).items() if k != "place"}
    merged = {**current, **changes}
    db.update("accounts", account.id, {"profile_json": merged})
    if account.kind == "employer" and changes.get("org_name"):
        db.update("accounts", account.id, {"org": changes["org_name"]})
    if account.kind == "learner":
        sync_card(account, merged)
    return get_profile(account)


def origin_for(account: auth.Account | None) -> dict[str, Any] | None:
    if account is None:
        return None
    prof = get_profile(account)
    return places.origin_from(prof.get("place_id"), prof.get("lat"), prof.get("lon"))


def saved_origin(account: auth.Account) -> dict[str, Any] | None:
    """Origin from a place the user saved themselves (demo personas without a saved profile: None,
    so their persona commute minutes keep driving the demo plans)."""
    stored = _stored(account.id)
    if not stored:
        return None
    return places.origin_from(stored.get("place_id"), stored.get("lat"), stored.get("lon"))


# ---------------------------------------------------------------------------
# Sign-up
# ---------------------------------------------------------------------------


def register(*, display_name: str, email: str, password: str, kind: str, org_name: str | None = None,
             place_id: str | None = None) -> auth.Account:
    auth.ensure_ready()
    name = " ".join(str(display_name or "").split())[:80]
    email_n = auth.normalize_email(email)
    if kind not in auth.KINDS:
        raise ProfileError(422, "Choose learner or employer.")
    if len(name) < 2:
        raise ProfileError(422, "Enter your name.")
    if not EMAIL_RE.fullmatch(email_n) or len(email_n) > auth.MAX_EMAIL_LENGTH:
        raise ProfileError(422, "Enter a valid email address.")
    if not isinstance(password, str) or len(password) < MIN_PASSWORD:
        raise ProfileError(422, f"Use at least {MIN_PASSWORD} characters for your password.")
    if len(password) > auth.MAX_PASSWORD_LENGTH:
        raise ProfileError(422, "That password is too long.")
    org = " ".join(str(org_name or "").split())[:80] or None
    if kind == "employer":
        org = org or name
    profile: dict[str, Any] = {}
    if place_id:
        p = places.place(place_id)
        if p is None:
            raise ProfileError(422, "Unknown place. Pick one from the list.")
        profile = {"place_id": p["id"], "lat": p["lat"], "lon": p["lon"]}
    if db.query_one("SELECT 1 AS hit FROM accounts WHERE email = ?", (email_n,)):
        raise ProfileError(409, "An account with this email already exists. Sign in instead.")
    persona_id = f"u_{secrets.token_hex(5)}"
    row_profile = {**PROFILE_DEFAULTS, **profile}
    if kind == "employer":
        row_profile["org_name"] = org
    try:
        db.execute(
            "INSERT INTO accounts (id, kind, display_name, persona_id, email, initials, org, password_hash, profile_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"acct_{persona_id}", kind, name, persona_id, email_n, auth.make_initials(name, kind)[:4],
             org if kind == "employer" else None, auth.hash_password(password), db._encode("profile_json", row_profile)),
        )
    except sqlite3.IntegrityError:
        raise ProfileError(409, "An account with this email already exists. Sign in instead.") from None
    account = auth.get_account(f"acct_{persona_id}")
    assert account is not None
    log.info("account registered: %s (%s)", account.id, kind)
    return account


# ---------------------------------------------------------------------------
# Opt-in talent cards (blind fields only are ever shown to employers)
# ---------------------------------------------------------------------------


def latest_sim_report(persona_id: str) -> dict[str, Any] | None:
    row = db.query_one(
        "SELECT payload_json FROM progress_log WHERE learner_id = ? AND kind = 'sim_report' ORDER BY created_at DESC LIMIT 1",
        (persona_id,),
    )
    val = db.jloads(row["payload_json"], None) if row else None
    return val if isinstance(val, dict) else None


def _career_skills(career_id: str | None, n: int = 4) -> list[str]:
    career = data.get_career(career_id) if career_id else None
    if not career:
        return []
    basis = career.get("skills_basis")
    skills = (basis.get("foothold") if isinstance(basis, dict) else None) or career.get("skills") or []
    return [s for s in skills if isinstance(s, str)][:n]


def _band(v: Any) -> str | None:
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return None
    v = float(v) / 100 if v > 1 else float(v)
    return "high" if v >= 0.67 else ("mid" if v >= 0.34 else "low")


def build_card(account: auth.Account, profile: dict[str, Any]) -> dict[str, Any]:
    rep = latest_sim_report(account.persona_id) or {}
    career = rep.get("career_id") or next((t.get("career_id") for t in rep.get("top_careers") or [] if isinstance(t, dict)), None)
    skills = _career_skills(career) if rep else []
    bands = {}
    for tid, val in list((rep.get("traits") or {}).items())[:3]:
        b = _band(val)
        if b:
            bands[str(tid)] = b
    p = places.place(profile.get("place_id"))
    hours = profile.get("hours_per_week")
    cid = f"cand_{account.persona_id}"
    return {
        "id": cid, "candidate_id": cid, "persona_id": account.persona_id, "opted_in": True, "user_account": True,
        "blind": {
            "candidate_id": cid,
            "target_career": career,
            "demonstrated_skills": skills,
            "sim_bands": bands,
            "availability": f"about {int(hours)} h/week" if isinstance(hours, (int, float)) and hours else None,
            "region": f"{p['name']} area" if p else None,
        },
        "hidden": {
            "name": account.display_name,
            "photo_initials": account.initials,
            "exact_location": f"{p['name']}, CA" if p else None,
            "contact_email": account.email,
        },
        "place_id": p["id"] if p else None,
    }


def sync_card(account: auth.Account, profile: dict[str, Any] | None = None) -> None:
    """Create/refresh the card when opted in; remove it when not (no-op for demo personas)."""
    if account.kind != "learner" or not account.persona_id.startswith("u_"):
        return
    _ensure_cards()
    profile = profile if profile is not None else get_profile(account)
    if profile.get("talent_opt_in"):
        db.upsert("user_talent_cards", {"account_id": account.id, "persona_id": account.persona_id,
                                        "card_json": build_card(account, profile), "updated_at": db.now_iso()},
                  key="account_id")
    else:
        db.execute("DELETE FROM user_talent_cards WHERE account_id = ?", (account.id,))


def user_cards() -> list[dict[str, Any]]:
    try:
        _ensure_cards()
        rows = db.query("SELECT card_json FROM user_talent_cards ORDER BY updated_at")
    except Exception as exc:  # noqa: BLE001  (the synthetic pool must keep working)
        log.warning("user talent cards unavailable (%s)", type(exc).__name__)
        return []
    out = []
    for r in rows:
        card = db.jloads(r["card_json"], None)
        if isinstance(card, dict) and card.get("id"):
            out.append(card)
    return out


__all__ = ["ProfileError", "build_card", "get_profile", "origin_for", "register", "sync_card", "update_profile",
           "user_cards"]
