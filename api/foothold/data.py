"""Cached loaders for data/processed/*.json (CONTRACTS §5) and ml/artifacts/metrics.json.

* Results are ``lru_cache``-d per (path, mtime, size): a file rewritten by the data
  builders is picked up on the next call without restarting the server.
* Missing or unreadable file -> empty list/dict and ONE warning per file (data is
  built in parallel; the API must keep working).
* Returned objects are shared: treat them as read-only (copy before mutating).
* List helpers accept either the contract shape (a list) or a wrapper dict such as
  ``{"provenance": ..., "occupations": [...]}`` or a dict keyed by id.
"""

from __future__ import annotations

import json
import logging
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import config

log = logging.getLogger("foothold.data")

_warned: set[str] = set()
_warn_lock = threading.Lock()


def _warn_once(key: str, msg: str, *args: Any, level: int = logging.WARNING) -> None:
    with _warn_lock:
        if key in _warned:
            return
        _warned.add(key)
    log.log(level, msg, *args)


@lru_cache(maxsize=64)
def _read_json(path: str, mtime_ns: int, size: int) -> Any:  # mtime/size are cache keys
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_json(path: Path, default: Any, *, missing_level: int = logging.WARNING) -> Any:
    """Parsed JSON at ``path`` (cached until the file changes) or a fresh copy of ``default``."""
    try:
        st = path.stat()
    except OSError:
        _warn_once(f"missing:{path}", "data file not found (using empty): %s", _rel(path), level=missing_level)
        return _fresh(default)
    try:
        return _read_json(str(path), st.st_mtime_ns, st.st_size)
    except (OSError, ValueError) as exc:  # ValueError covers JSONDecodeError / UnicodeDecodeError
        _warn_once(f"bad:{path}:{st.st_mtime_ns}", "data file unreadable (%s), using empty: %s", type(exc).__name__, _rel(path))
        return _fresh(default)


def _fresh(default: Any) -> Any:
    return type(default)() if isinstance(default, (list, dict)) else default


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(config.ROOT).as_posix()
    except ValueError:
        return path.name


def _processed(name: str, default: Any) -> Any:
    return load_json(config.PROCESSED_DIR / name, default)


def _as_list(obj: Any, *keys: str) -> list[Any]:
    """Contract list, or the list under one of ``keys``/"items"/"data", or dict-of-dicts -> list."""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for key in (*keys, "items", "data"):
            if isinstance(obj.get(key), list):
                return obj[key]
        if obj and all(isinstance(v, dict) for v in obj.values()):
            return [{"id": k, **v} if "id" not in v else v for k, v in obj.items()]
    return []


def _by_id(items: list[Any], item_id: str, key: str = "id") -> dict[str, Any] | None:
    for item in items:
        if isinstance(item, dict) and item.get(key) == item_id:
            return item
    return None


def clear_cache() -> None:
    _read_json.cache_clear()
    with _warn_lock:
        _warned.clear()


# ---- raw files -------------------------------------------------------------


def traits() -> list[dict[str, Any]]:
    return _as_list(_processed("traits.json", []), "traits")


def careers() -> list[dict[str, Any]]:
    return _as_list(_processed("careers.json", []), "careers")


def occupations() -> Any:
    """Raw occupations.json (list or ``{provenance, occupations}``); see :func:`occupation_list`."""
    return _processed("occupations.json", {})


def occupation_list() -> list[dict[str, Any]]:
    return _as_list(occupations(), "occupations")


def skills() -> list[dict[str, Any]]:
    return _as_list(_processed("skills.json", []), "skills")


def courses() -> list[dict[str, Any]]:
    return _as_list(_processed("courses.json", []), "courses")


def programs() -> list[dict[str, Any]]:
    return _as_list(_processed("programs.json", []), "programs")


def events() -> dict[str, Any]:
    """Raw events.json ``{schema_version, status, events: [...]}``; see :func:`events_list`."""
    raw = _processed("events.json", {})
    return raw if isinstance(raw, dict) else {"events": raw if isinstance(raw, list) else []}


def events_list() -> list[dict[str, Any]]:
    return _as_list(events(), "events")


def sources() -> list[dict[str, Any]]:
    return _as_list(_processed("sources.json", []), "sources")


def personas() -> Any:
    """Raw personas.json (served as-is by /api/meta/personas)."""
    return _processed("personas.json", {})


def persona_list() -> list[dict[str, Any]]:
    return _as_list(personas(), "personas")


def learners() -> list[dict[str, Any]]:
    return _as_list(_processed("synthetic/learners.json", {}), "learners")


def employers() -> list[dict[str, Any]]:
    return _as_list(_processed("synthetic/employers.json", {}), "employers")


def circles() -> list[dict[str, Any]]:
    return _as_list(_processed("synthetic/circles.json", {}), "circles")


def talent_pool() -> list[dict[str, Any]]:
    return _as_list(_processed("synthetic/talent_pool.json", {}), "talent_pool", "talent", "candidates", "cards")


def metrics() -> dict[str, Any]:
    """ml/artifacts/metrics.json or {} (missing is normal before training)."""
    raw = load_json(config.metrics_path(), {}, missing_level=logging.INFO)
    return raw if isinstance(raw, dict) else {}


# ---- helpers ----------------------------------------------------------------


def traits_order() -> list[str]:
    """Trait ids in file order (the canonical vector order; never hardcode)."""
    return [t["id"] for t in traits() if isinstance(t, dict) and "id" in t]


def career_ids() -> list[str]:
    return [c["id"] for c in careers() if isinstance(c, dict) and "id" in c]


def get_career(career_id: str) -> dict[str, Any] | None:
    return _by_id(careers(), career_id)


def skill_ids() -> set[str]:
    return {s["id"] for s in skills() if isinstance(s, dict) and "id" in s}


def get_skill(skill_id: str) -> dict[str, Any] | None:
    return _by_id(skills(), skill_id)


def get_course(course_id: str) -> dict[str, Any] | None:
    return _by_id(courses(), course_id)


def get_program(program_id: str) -> dict[str, Any] | None:
    return _by_id(programs(), program_id)


def programs_for(career_id: str, route_type: str | None = None) -> list[dict[str, Any]]:
    return [
        p
        for p in programs()
        if isinstance(p, dict) and p.get("career_id") == career_id and (route_type is None or p.get("route_type") == route_type)
    ]


def events_for(career_id: str | None = None, *, include_crunch: bool = True) -> list[dict[str, Any]]:
    out = []
    for ev in events_list():
        if not isinstance(ev, dict):
            continue
        if ev.get("crunch") and not include_crunch:
            continue
        if career_id is None or career_id in (ev.get("career_ids") or []) or (ev.get("crunch") and include_crunch):
            out.append(ev)
    return out


def get_event(event_id: str) -> dict[str, Any] | None:
    return _by_id(events_list(), event_id, key="event_id")


def get_source(source_id: str) -> dict[str, Any] | None:
    return _by_id(sources(), source_id)


def get_persona(persona_id: str) -> dict[str, Any] | None:
    raw = personas()
    if isinstance(raw, dict) and isinstance(raw.get(persona_id), dict):
        return {"id": persona_id, **raw[persona_id]} if "id" not in raw[persona_id] else raw[persona_id]
    return _by_id(persona_list(), persona_id)


def get_learner(learner_id: str) -> dict[str, Any] | None:
    return _by_id(learners(), learner_id)


def get_employer(employer_id: str) -> dict[str, Any] | None:
    return _by_id(employers(), employer_id)


def get_circle(circle_id: str) -> dict[str, Any] | None:
    return _by_id(circles(), circle_id)
