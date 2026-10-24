"""Consent-gated employer <-> learner contact (CONTRACTS sections 1, 13) and employer aggregates.

Everything here is FICTIONAL demo data (synthetic talent pool, demo accounts).

Blind talent cards
  * :func:`blind_card` builds a card from a WHITELIST of blind fields only: demonstrated
    skills, sim performance bands, pathway progress, availability, commute-radius region.
    Hidden fields (name, photo / initials, exact location, contact) and the synthetic
    fairness ``group`` label are never copied into it.
  * Cards are addressed by an opaque public id (``cand_<10 hex>``, HMAC of the card id),
    so a card id that happens to contain a persona name never reaches an employer.
  * :func:`hidden_fields` (server side only) is released through :func:`reveal`, and only
    to the employer whose request the card's owner accepted.

Consent requests (db table ``consent_requests``; ``employer_id`` = employer persona id)
  * :func:`create_request`  employer identity comes from the token (an ``auth.Account``)
  * :func:`employer_requests` the employer's own requests (+ revealed fields once accepted)
  * :func:`learner_inbox`     requests addressed to the learner's own card, each with
                              exactly what acceptance would share
  * :func:`decide`            accept / decline (accepted can later be withdrawn)
  * :func:`reveal`            hidden fields or None

Skill demand table (``skill_demand``)
  Written by the employer graph's gap_report node (:func:`write_skill_demand`); learner
  recommendations read it with :func:`read_skill_demand` (aggregates only, min group 5).

Nothing here logs messages, names or contact details.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import threading
from typing import Any, Iterable, Literal

from . import auth, data, db, safety
from .auth import Account

log = logging.getLogger("foothold.consent")

MIN_GROUP_SIZE = 5
MAX_MESSAGE_CHARS = 600
Decision = Literal["accepted", "declined"]

BLIND_FIELDS = ("demonstrated_skills", "sim_bands", "pathway_progress", "availability", "region")
HIDDEN_FIELDS = ("name", "initials", "photo", "exact_location", "contact")
HIDDEN_LABELS = {
    "name": "Name",
    "initials": "Photo / initials",
    "photo": "Photo",
    "exact_location": "Exact location",
    "contact": "Contact details",
}
BLIND_LABELS = {
    "demonstrated_skills": "Demonstrated skills",
    "sim_bands": "Sim performance bands",
    "pathway_progress": "Pathway progress",
    "availability": "Availability",
    "region": "Commute-radius region",
}

_DECISION_ALIASES = {
    "accept": "accepted",
    "accepted": "accepted",
    "approve": "accepted",
    "yes": "accepted",
    "decline": "declined",
    "declined": "declined",
    "deny": "declined",
    "no": "declined",
    "withdraw": "declined",
}

# ---------------------------------------------------------------------------
# Extra tables (CREATE TABLE IF NOT EXISTS; the base tables live in foothold.db)
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS skill_demand (
    skill_id        TEXT PRIMARY KEY NOT NULL,
    skill_name      TEXT NOT NULL,
    postings        INTEGER NOT NULL,
    required        INTEGER NOT NULL,
    demand_score    REAL NOT NULL,
    pool_size       INTEGER NOT NULL,
    pool_with_skill INTEGER,
    coverage        REAL,
    gap             REAL,
    suppressed      INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT NOT NULL
);
"""

_schema_lock = threading.Lock()
_schema_ready: set[str] = set()


def ensure_schema() -> None:
    key = str(db.db_path())
    if key in _schema_ready:
        return
    with _schema_lock:
        if key in _schema_ready:
            return
        with db.connect() as conn:
            conn.executescript(SCHEMA)
        _schema_ready.add(key)


def reset_state() -> None:
    """Forget cached schema state (tests switch db files)."""
    with _schema_lock:
        _schema_ready.clear()


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

_EMPTY = (None, "", [], {})


def _clean(value: Any, limit: int = 80) -> str | None:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return None
    text = " ".join(str(value).split())
    return text[:limit] if text else None


def _pick(card: dict[str, Any], keys: Iterable[str], nests: Iterable[str]) -> Any:
    keys = tuple(keys)
    for key in keys:
        if card.get(key) not in _EMPTY:
            return card[key]
    for nest in nests:
        sub = card.get(nest)
        if isinstance(sub, dict):
            for key in keys:
                if sub.get(key) not in _EMPTY:
                    return sub[key]
    return None


_BLIND_NESTS = ("blind", "public", "profile", "card")
_HIDDEN_NESTS = ("hidden", "private", "identity", "contact_info", "pii")


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = re.search(r"-?\d+(?:\.\d+)?", value)
        return float(m.group(0)) if m else None
    return None


def _skill_names() -> dict[str, str]:
    return {s["id"]: s.get("name") or s["id"] for s in data.skills() if isinstance(s, dict) and s.get("id")}


def _career_titles() -> dict[str, str]:
    return {c["id"]: c.get("title") or c["id"] for c in data.careers() if isinstance(c, dict) and c.get("id")}


# ---------------------------------------------------------------------------
# Opaque public ids
# ---------------------------------------------------------------------------


def _id_key() -> bytes:
    secret = (os.environ.get("AUTH_SECRET") or "").strip() or "foothold-public-candidate-ids"
    return hashlib.sha256(f"{secret}|candidate-id|v1".encode("utf-8")).digest()


def public_id(card_id: str) -> str:
    digest = hmac.new(_id_key(), str(card_id).encode("utf-8"), hashlib.sha256).hexdigest()
    return f"cand_{digest[:10]}"


def pool() -> list[dict[str, Any]]:
    """Raw talent-pool cards that have an id (server side; never return these directly)."""
    return [c for c in auth.talent_pool() if isinstance(c, dict) and auth.card_id(c)]


def _index() -> dict[str, dict[str, Any]]:
    return {public_id(auth.card_id(c) or ""): c for c in pool()}


def card_by_public_id(pid: str) -> dict[str, Any] | None:
    if not isinstance(pid, str) or not pid:
        return None
    return _index().get(pid)


def card_by_id(card_id: str) -> dict[str, Any] | None:
    for card in pool():
        if auth.card_id(card) == card_id:
            return card
    return None


# ---------------------------------------------------------------------------
# Blind card normalization (whitelist)
# ---------------------------------------------------------------------------


def _skills(card: dict[str, Any]) -> list[dict[str, Any]]:
    raw = _pick(card, ("demonstrated_skills", "skills_demonstrated", "skills", "skill_ids", "verified_skills"), _BLIND_NESTS)
    names = _skill_names()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(sid: Any, level: Any = None, evidence: Any = None) -> None:
        if not isinstance(sid, str) or sid not in names or sid in seen:
            return
        seen.add(sid)
        item: dict[str, Any] = {"id": sid, "name": names[sid]}
        lvl = _num(level)
        if lvl is not None:
            item["level"] = round(lvl, 2)
        ev = _clean(evidence, 60)
        if ev:
            item["evidence"] = ev
        out.append(item)

    if isinstance(raw, dict):
        for sid, val in raw.items():
            if isinstance(val, dict):
                add(sid, val.get("level") or val.get("score"), val.get("evidence") or val.get("source"))
            else:
                add(sid, val)
    elif isinstance(raw, list):
        for x in raw:
            if isinstance(x, str):
                add(x)
            elif isinstance(x, dict):
                add(x.get("id") or x.get("skill_id") or x.get("skill"), x.get("level") or x.get("score"),
                    x.get("evidence") or x.get("source"))
    return out


def _bands(card: dict[str, Any]) -> list[dict[str, Any]]:
    raw = _pick(card, ("sim_bands", "sim_performance_bands", "sim_performance", "sim_results", "sim"), _BLIND_NESTS)
    titles = _career_titles()
    out: list[dict[str, Any]] = []

    def add(career: Any, band: Any, extra: dict[str, Any] | None = None) -> None:
        b = _clean(band, 24)
        if not b:
            return
        item: dict[str, Any] = {"band": b}
        if isinstance(career, str) and career:
            item["career_id"] = career
            item["career_title"] = titles.get(career, _clean(career.replace("_", " ").title(), 48))
        for key in ("metric", "stat"):
            m = _clean((extra or {}).get(key), 24)
            if m:
                item["metric"] = m
        out.append(item)

    if isinstance(raw, dict):
        for career, val in raw.items():
            if career in ("safety", "output", "team_trust", "stress") and not isinstance(val, dict):
                add(None, val, {"metric": career})
                continue
            if isinstance(val, dict):
                add(val.get("career_id") or career, val.get("band") or val.get("level") or val.get("label"), val)
            else:
                add(career, val)
    elif isinstance(raw, list):
        for x in raw:
            if isinstance(x, dict):
                add(x.get("career_id") or x.get("career"), x.get("band") or x.get("level") or x.get("label"), x)
            elif isinstance(x, str):
                add(None, x)
    elif isinstance(raw, str):
        add(None, raw)
    return out[:6]


def _progress(card: dict[str, Any]) -> dict[str, Any] | None:
    raw = _pick(card, ("pathway_progress", "pathway", "progress"), _BLIND_NESTS)
    if raw in _EMPTY:
        return None
    titles = _career_titles()
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        pct = float(raw)
        return {"pct": round(pct / 100 if pct > 1 else pct, 3)}
    if isinstance(raw, str):
        n = _num(raw)
        return {"label": _clean(raw, 60), **({"pct": round(n / 100 if n and n > 1 else (n or 0), 3)} if n is not None else {})}
    if not isinstance(raw, dict):
        return None
    out: dict[str, Any] = {}
    career = raw.get("career_id") or raw.get("career")
    if isinstance(career, str) and career:
        out["career_id"] = career
        out["career_title"] = titles.get(career, _clean(career.replace("_", " ").title(), 48))
    route = _clean(raw.get("route_type") or raw.get("route"), 24)
    if route:
        out["route_type"] = route
    done = _num(raw.get("steps_done", raw.get("completed_steps", raw.get("completed"))))
    total = _num(raw.get("steps_total", raw.get("total_steps", raw.get("total"))))
    if done is not None and total:
        out["steps_done"], out["steps_total"] = int(done), int(total)
    pct = _num(raw.get("pct", raw.get("percent", raw.get("fraction"))))
    if pct is None and done is not None and total:
        pct = done / total
    if pct is not None:
        out["pct"] = round(pct / 100 if pct > 1 else pct, 3)
    label = _clean(raw.get("label") or raw.get("stage") or raw.get("milestone"), 60)
    if label:
        out["label"] = label
    return out or None


# "10 h/week", "20 hours/week", "about 12 hrs a week", "15 hours". Clock times ("2:30 pm")
# and bare numbers are never read as hours.
_HOURS_RE = re.compile(
    r"(?<![\d:.])(\d{1,2}(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours)\b(?![-\s]*(?:shifts?|days?))(?:\s*(?:/|per|a|an|each)\s*(?:wk|week))?",
    re.IGNORECASE,
)
_AVAIL_HOURS_KEYS = ("availability_hours_per_week", "available_hours_per_week", "availability_hours", "hours_available")


def parse_hours_per_week(text: Any) -> int | None:
    """Hours per week from free text, only for explicit "N h/week" / "N hours" patterns; else None."""
    if not isinstance(text, str):
        return None
    m = _HOURS_RE.search(text)
    if not m:
        return None
    try:
        val = float(m.group(1))
    except ValueError:
        return None
    return int(round(val)) if 1 <= val <= 80 else None


def _explicit_hours(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if 1 <= value <= 80 else None
    return parse_hours_per_week(value) if isinstance(value, str) else None


def _availability(card: dict[str, Any]) -> dict[str, Any] | None:
    raw = _pick(card, ("availability", "available"), _BLIND_NESTS)
    explicit = _explicit_hours(_pick(card, _AVAIL_HOURS_KEYS, _BLIND_NESTS))
    if raw in _EMPTY:
        if explicit is None:
            return None
        return {"label": None, "hours_per_week": explicit, "shifts": [], "days": []}
    if isinstance(raw, str):
        hours = explicit if explicit is not None else parse_hours_per_week(raw)
        return {"label": _clean(raw, 60), "hours_per_week": hours, "shifts": [], "days": []}
    if not isinstance(raw, dict):
        return None
    hours = _explicit_hours(raw.get("hours_per_week", raw.get("hours")))
    if hours is None:
        hours = explicit
    shifts_raw = raw.get("shifts") or raw.get("shift") or []
    days_raw = raw.get("days") or []
    shifts = [s for s in (_clean(x, 16) for x in (shifts_raw if isinstance(shifts_raw, list) else [shifts_raw])) if s]
    days = [d for d in (_clean(x, 10) for x in (days_raw if isinstance(days_raw, list) else [days_raw])) if d]
    out = {
        "hours_per_week": hours,
        "shifts": shifts[:4],
        "days": days[:7],
        "start": _clean(raw.get("start") or raw.get("start_date") or raw.get("available_from"), 24),
        "label": _clean(raw.get("label") or raw.get("summary"), 60),
    }
    return out


def _region(card: dict[str, Any]) -> dict[str, Any] | None:
    raw = _pick(card, ("region", "commute_region", "commute_radius_region", "commute"), _BLIND_NESTS)
    if raw in _EMPTY:
        return None
    if isinstance(raw, str):
        return {"label": _clean(raw, 60)}
    if isinstance(raw, dict):
        label = _clean(raw.get("label") or raw.get("name") or raw.get("region") or raw.get("area"), 60)
        radius = _num(raw.get("radius_miles", raw.get("commute_miles", raw.get("radius"))))
        minutes = _num(raw.get("commute_minutes", raw.get("minutes")))
        out: dict[str, Any] = {"label": label}
        if radius is not None:
            out["radius_miles"] = int(radius)
        if minutes is not None:
            out["commute_minutes"] = int(minutes)
        return out if label or len(out) > 1 else None
    return None


def _target_career(card: dict[str, Any]) -> dict[str, Any] | None:
    cid = _pick(card, ("target_career", "career_id"), _BLIND_NESTS)
    if not isinstance(cid, str) or not cid:
        return None
    titles = _career_titles()
    return {"id": cid, "title": titles.get(cid, _clean(cid.replace("_", " ").title(), 48))} if cid in titles else None


def blind_card(card: dict[str, Any]) -> dict[str, Any]:
    """The employer-facing card: blind fields only (whitelist), opaque id, FICTIONAL."""
    cid = auth.card_id(card) or ""
    return {
        "candidate_id": public_id(cid),
        "fictional": True,
        "demonstrated_skills": _skills(card),
        "sim_bands": _bands(card),
        "target_career": _target_career(card),
        "pathway_progress": _progress(card),
        "availability": _availability(card),
        "region": _region(card),
        "hidden": list(HIDDEN_FIELDS),
    }


def group_label(card: dict[str, Any]) -> str | None:
    """Synthetic fairness group (server side, fairness audit only; never on a card)."""
    value = _pick(card, ("group", "synthetic_group", "fairness_group", "demographic_group"), ("synthetic", "audit", "fairness"))
    return _clean(value, 32)


def hidden_fields(card: dict[str, Any]) -> dict[str, Any]:
    """Name, photo/initials, exact location, contact (server side). Persona cards fall back to the account."""
    name = _clean(_pick(card, ("name", "full_name", "display_name"), _HIDDEN_NESTS), 80)
    persona = auth.persona_for_candidate(auth.card_id(card) or "")
    account = auth.get_account_by_persona(persona) if persona else None
    if not name and account is not None:
        name = account.display_name
    initials = _clean(_pick(card, ("initials", "photo_initials"), _HIDDEN_NESTS), 4) or (auth.make_initials(name) if name else None)
    photo = _clean(_pick(card, ("photo", "photo_url", "avatar", "avatar_url"), _HIDDEN_NESTS), 300)

    loc_raw = _pick(card, ("exact_location", "location", "address", "home_location"), _HIDDEN_NESTS)
    if isinstance(loc_raw, dict):
        parts = [loc_raw.get(k) for k in ("street", "address", "neighborhood", "city", "zip", "zip_code")]
        location = _clean(", ".join(str(p) for p in parts if p), 120)
    else:
        location = _clean(loc_raw, 120)

    contact_raw = _pick(card, ("contact",), _HIDDEN_NESTS)
    email = phone = None
    if isinstance(contact_raw, dict):
        email = _clean(contact_raw.get("email"), 120)
        phone = _clean(contact_raw.get("phone"), 40)
    elif isinstance(contact_raw, str):
        email = _clean(contact_raw, 120) if "@" in contact_raw else None
        phone = None if email else _clean(contact_raw, 40)
    email = email or _clean(_pick(card, ("email", "contact_email"), _HIDDEN_NESTS), 120)
    phone = phone or _clean(_pick(card, ("phone", "contact_phone"), _HIDDEN_NESTS), 40)
    if not email and account is not None:
        email = account.email
    return {
        "name": name,
        "initials": initials,
        "photo": photo,
        "exact_location": location,
        "contact": {"email": email, "phone": phone},
    }


# ---------------------------------------------------------------------------
# Matching (skill match + availability/region filters)
# ---------------------------------------------------------------------------


def profile_weights(profile: dict[str, Any] | None) -> dict[str, float]:
    """skill_id -> weight (required 1.0, preferred 0.5) from a posting profile."""
    out: dict[str, float] = {}
    for s in (profile or {}).get("skills") or []:
        if isinstance(s, dict) and isinstance(s.get("skill_id"), str):
            w = 1.0 if s.get("importance") == "required" else 0.5
            out[s["skill_id"]] = max(out.get(s["skill_id"], 0.0), w)
    return out


def skill_match(card: dict[str, Any], weights: dict[str, float]) -> dict[str, Any]:
    have = {s["id"] for s in card.get("demonstrated_skills") or []}
    total = sum(weights.values())
    matched = [sid for sid in weights if sid in have]
    missing = [sid for sid in weights if sid not in have]
    score = (sum(weights[s] for s in matched) / total) if total else 0.0
    return {"score": round(score, 4), "matched": matched, "missing": missing}


def passes_filters(card: dict[str, Any], *, min_hours: int | None = None, region: str | None = None) -> bool:
    if min_hours:
        hours = (card.get("availability") or {}).get("hours_per_week")
        if isinstance(hours, int) and hours < min_hours:
            return False
    if region:
        label = ((card.get("region") or {}).get("label") or "").lower()
        if region.lower() not in label:
            return False
    return True


# ---------------------------------------------------------------------------
# Consent requests
# ---------------------------------------------------------------------------


class ConsentError(Exception):
    """``status`` is the HTTP status the route should return."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def clean_message(message: str) -> str:
    """Employer free text shown to a learner: sanitized, length-limited; harassment rejected."""
    text = safety.sanitize_untrusted(message or "", "consent_message", max_chars=MAX_MESSAGE_CHARS)["text"]
    if not text:
        raise ConsentError(422, "Add a short message so the learner knows why you're reaching out.")
    if "harassment" in safety.moderate_post(text)["reasons"]:
        raise ConsentError(422, "Please rephrase the message; it reads as harassment.")
    return text


def _posting_title(posting_id: str | None, employer_id: str) -> str | None:
    if not posting_id:
        return None
    row = db.query_one("SELECT title FROM postings WHERE id = ? AND employer_id = ?", (posting_id, employer_id))
    return row["title"] if row else None


def _employer_public(employer_id: str) -> dict[str, Any]:
    account = auth.get_account_by_persona(employer_id)
    name = (account.org or account.display_name) if account else employer_id.replace("_", " ").title()
    return {"id": employer_id, "name": name, "fictional": True}


def create_request(employer: Account, candidate_public_id: str, message: str, posting_id: str | None = None) -> dict[str, Any]:
    """New pending request from ``employer`` (identity from the token). Idempotent per open request."""
    if employer.kind != "employer":
        raise ConsentError(403, "This needs an employer account")
    card = card_by_public_id(candidate_public_id)
    if card is None:
        raise ConsentError(404, "Candidate not found")
    text = clean_message(message)
    if posting_id and _posting_title(posting_id, employer.persona_id) is None:
        raise ConsentError(404, "Posting not found")
    card_id = auth.card_id(card) or ""
    existing = db.query_one(
        "SELECT * FROM consent_requests WHERE employer_id = ? AND candidate_id = ? AND status IN ('pending', 'accepted') "
        "ORDER BY created_at DESC LIMIT 1",
        (employer.persona_id, card_id),
    )
    if existing:
        out = _employer_view(existing)
        out["duplicate"] = True
        return out
    row = db.insert(
        "consent_requests",
        {"employer_id": employer.persona_id, "candidate_id": card_id, "posting_id": posting_id, "message": text},
    )
    log.info("consent request created (%s)", row["id"])
    return _employer_view(row)


def _employer_view(row: dict[str, Any]) -> dict[str, Any]:
    card = card_by_id(row["candidate_id"])
    out = {
        "id": row["id"],
        "candidate_id": public_id(row["candidate_id"]),
        "posting_id": row.get("posting_id"),
        "posting_title": _posting_title(row.get("posting_id"), row["employer_id"]),
        "message": row.get("message") or "",
        "status": row["status"],
        "created_at": row["created_at"],
        "decided_at": row.get("decided_at"),
        "card": blind_card(card) if card else None,
        "revealed": None,
    }
    if row["status"] == "accepted" and card is not None:
        out["revealed"] = hidden_fields(card)
    return out


def employer_requests(employer: Account) -> list[dict[str, Any]]:
    rows = db.query(
        "SELECT * FROM consent_requests WHERE employer_id = ? ORDER BY created_at DESC LIMIT 200", (employer.persona_id,)
    )
    return [_employer_view(r) for r in rows]


def request_status_by_candidate(employer: Account) -> dict[str, dict[str, Any]]:
    """public candidate id -> latest request {id, status} for this employer."""
    out: dict[str, dict[str, Any]] = {}
    for r in db.query(
        "SELECT id, candidate_id, status, created_at FROM consent_requests WHERE employer_id = ? ORDER BY created_at ASC",
        (employer.persona_id,),
    ):
        out[public_id(r["candidate_id"])] = {"id": r["id"], "status": r["status"]}
    return out


def shared_on_accept(card: dict[str, Any]) -> list[dict[str, Any]]:
    """Exactly what acceptance shares with that one employer (the learner's own values)."""
    hidden = hidden_fields(card)
    contact = hidden["contact"] or {}
    rows = [
        {"field": "name", "label": "Name", "value": hidden["name"]},
        {"field": "initials", "label": "Initials (shown instead of a photo)", "value": hidden["initials"]},
        {"field": "exact_location", "label": "Exact location", "value": hidden["exact_location"]},
        {"field": "email", "label": "Email", "value": contact.get("email")},
        {"field": "phone", "label": "Phone", "value": contact.get("phone")},
    ]
    if hidden.get("photo"):
        rows.insert(2, {"field": "photo", "label": "Photo", "value": "your profile photo"})
    return [r for r in rows if r["value"]]


def learner_inbox(learner: Account) -> dict[str, Any]:
    if learner.kind != "learner":
        raise ConsentError(403, "This needs a learner account")
    card_id = auth.candidate_id_for(learner)
    card = card_by_id(card_id) if card_id else None
    if card is None:
        return {"candidate_id": None, "card": None, "requests": [], "shared_on_accept": [], "always_visible": []}
    rows = db.query("SELECT * FROM consent_requests WHERE candidate_id = ? ORDER BY created_at DESC LIMIT 100", (card_id,))
    shared = shared_on_accept(card)
    requests = [
        {
            "id": r["id"],
            "employer": _employer_public(r["employer_id"]),
            "posting_id": r.get("posting_id"),
            "posting_title": _posting_title(r.get("posting_id"), r["employer_id"]),
            "message": r.get("message") or "",
            "status": r["status"],
            "created_at": r["created_at"],
            "decided_at": r.get("decided_at"),
        }
        for r in rows
    ]
    return {
        "candidate_id": public_id(card_id or ""),
        "card": blind_card(card),
        "requests": requests,
        "shared_on_accept": shared,
        "always_visible": [{"field": f, "label": BLIND_LABELS[f]} for f in BLIND_FIELDS],
    }


def normalize_decision(decision: str) -> Decision:
    value = _DECISION_ALIASES.get(str(decision or "").strip().lower())
    if value is None:
        raise ConsentError(422, "Decision must be accept or decline")
    return value  # type: ignore[return-value]


def decide(learner: Account, request_id: str, decision: str) -> dict[str, Any]:
    """Accept or decline a request addressed to the learner's own card (404 otherwise)."""
    if learner.kind != "learner":
        raise ConsentError(403, "This needs a learner account")
    status = normalize_decision(decision)
    card_id = auth.candidate_id_for(learner)
    row = db.query_one("SELECT * FROM consent_requests WHERE id = ?", (str(request_id),))
    if row is None or not card_id or row["candidate_id"] != card_id:
        raise ConsentError(404, "Request not found")  # same answer whether it exists or not
    if row["status"] != status:
        db.update("consent_requests", row["id"], {"status": status, "decided_at": db.now_iso()})
        log.info("consent request %s -> %s", row["id"], status)
    inbox = learner_inbox(learner)
    return next((r for r in inbox["requests"] if r["id"] == row["id"]), {"id": row["id"], "status": status})


def reveal(viewer: Account | None, candidate_public_id: str) -> dict[str, Any] | None:
    """Hidden fields only for the employer holding an ACCEPTED request from this card's owner."""
    if viewer is None or viewer.kind != "employer":
        return None
    card = card_by_public_id(candidate_public_id)
    if card is None:
        return None
    hit = db.query_one(
        "SELECT id FROM consent_requests WHERE employer_id = ? AND candidate_id = ? AND status = 'accepted' LIMIT 1",
        (viewer.persona_id, auth.card_id(card) or ""),
    )
    return hidden_fields(card) if hit else None


def candidate_view(viewer: Account | None, candidate_public_id: str) -> dict[str, Any]:
    card = card_by_public_id(candidate_public_id)
    if card is None:
        raise ConsentError(404, "Candidate not found")
    revealed = reveal(viewer, candidate_public_id)
    status = None
    if viewer is not None and viewer.kind == "employer":
        status = request_status_by_candidate(viewer).get(candidate_public_id)
    return {"card": blind_card(card), "consented": revealed is not None, "revealed": revealed, "request": status}


def counts(employer: Account) -> dict[str, Any]:
    rows = db.query(
        "SELECT status, COUNT(*) AS n FROM consent_requests WHERE employer_id = ? GROUP BY status", (employer.persona_id,)
    )
    by = {r["status"]: int(r["n"]) for r in rows}
    pending, accepted, declined = by.get("pending", 0), by.get("accepted", 0), by.get("declined", 0)
    decided = accepted + declined
    return {
        "pending": pending,
        "accepted": accepted,
        "declined": declined,
        "total": pending + accepted + declined,
        "acceptance_rate": round(accepted / decided, 4) if decided else None,
    }


# ---------------------------------------------------------------------------
# Skill demand table (gap report)
# ---------------------------------------------------------------------------


def write_skill_demand(rows: list[dict[str, Any]]) -> int:
    """Replace the demand table with ``rows`` (aggregates only). Returns the row count."""
    ensure_schema()
    now = db.now_iso()
    with db._write_lock, db.connect() as conn:  # one transaction: readers never see a half-written table
        conn.execute("DELETE FROM skill_demand")
        conn.executemany(
            "INSERT INTO skill_demand (skill_id, skill_name, postings, required, demand_score, pool_size, "
            "pool_with_skill, coverage, gap, suppressed, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    r["skill_id"], r["skill_name"], int(r["postings"]), int(r["required"]), float(r["demand_score"]),
                    int(r["pool_size"]), r.get("pool_with_skill"), r.get("coverage"), r.get("gap"),
                    1 if r.get("suppressed") else 0, now,
                )
                for r in rows
            ],
        )
    return len(rows)


def read_skill_demand() -> list[dict[str, Any]]:
    """Demand table for learner recommendations: one row per skill employers asked for.

    ``demand_score`` = share of postings asking for the skill (required 1.0, preferred 0.5);
    ``coverage``/``gap`` are None when fewer than MIN_GROUP_SIZE candidates hold the skill.
    """
    ensure_schema()
    rows = db.query("SELECT * FROM skill_demand ORDER BY demand_score DESC, skill_id")
    for r in rows:
        r["suppressed"] = bool(r["suppressed"])
    return rows
