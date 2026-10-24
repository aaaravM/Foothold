"""Lab endpoints for SHEET 06 (Model Lab) and SHEET 07 (About).

GET /api/lab/inventory
    A live inventory, computed on every request from files on disk, so the About and
    Lab sheets can state their limits with real counts instead of typed-in numbers:

    * ``datasets``: one row per data/processed file (rows, provenance label counts,
      events status, synthetic/fictional flags). Labels are normalized per CONTRACTS
      section 12: DERIVED -> REAL, NOT_READ / UNVERIFIED -> SAMPLE, "DRAFT ..." -> DRAFT.
    * ``models``: the six metrics.json keys with the script that writes each one,
      whether that script exists, whether metrics.json has the key, and its status,
      trained_at and reproduce fields.
    * ``artifacts``: files in ml/artifacts (name, bytes, modified, sha256 prefix).
    * ``privacy``: session and password-hashing parameters read from foothold.auth,
      and any minimum-group-size constants found in the employer/fairness modules.
    * ``verifier_tolerances``: the claim verifier's per-unit tolerances (verifier.py).

Read-only. Never writes files and never imports the ML modules (torch is slow to
import); constants in modules this file does not own are read with ``ast``, which
parses without executing anything. Missing files are normal while the data and ML
builders run in parallel: they show up as ``exists: false`` / zero rows.
"""

from __future__ import annotations

import ast
import hashlib
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from fastapi import APIRouter

from foothold import config, data

router = APIRouter(prefix="/api/lab", tags=["lab"])

PROVENANCE = ("REAL", "SAMPLE", "SYNTHETIC", "FICTIONAL")
_STATUS_ALIASES = {"DERIVED": "REAL", "NOT_READ": "SAMPLE", "UNVERIFIED": "SAMPLE"}

# metrics.json key -> the script that writes it (CONTRACTS sections 3 and 10).
MODEL_SCRIPTS: dict[str, str] = {
    "career_fit": "ml/train_career_fit.py",
    "selector": "ml/eval_selector.py",
    "recommender": "ml/train_recommender.py",
    "planner": "ml/eval_planner.py",
    "fairness": "ml/audit_fairness.py",
    "verifier": "ml/eval_verifier.py",
}

# Modules that may define a minimum group size for aggregate views (read with ast only).
_GROUP_SIZE_MODULES = (
    "api/foothold/fairness.py",
    "api/foothold/routes/employer.py",
    "api/foothold/graphs/employer.py",
    "api/foothold/employer.py",
    "api/foothold/routes/circle.py",
)
_GROUP_SIZE_NAME = re.compile(r"^(MIN|MINIMUM)_[A-Z0-9_]*(GROUP|CELL|COHORT|COUNT|SIZE|N)[A-Z0-9_]*$|^K_ANON[A-Z0-9_]*$")

_MAX_ARTIFACTS = 60
_HASH_LIMIT_BYTES = 64 * 1024 * 1024


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _iso_mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")
    except OSError:
        return None


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(config.ROOT).as_posix()
    except ValueError:
        return path.name


def normalize_status(value: Any) -> str | None:
    """Provenance label for display, or None when the value is not a provenance label."""
    if not isinstance(value, str):
        return None
    raw = value.strip().upper()
    if raw.startswith("DRAFT"):
        return "DRAFT"
    raw = _STATUS_ALIASES.get(raw, raw)
    return raw if raw in PROVENANCE else None


def _count(values: Iterable[Any]) -> dict[str, int]:
    c: Counter[str] = Counter()
    for v in values:
        label = normalize_status(v)
        if label:
            c[label] += 1
    return dict(sorted(c.items()))


def _dicts(items: Any) -> list[dict[str, Any]]:
    return [x for x in items if isinstance(x, dict)] if isinstance(items, list) else []


def _file_info(path: Path) -> dict[str, Any]:
    return {"file": _rel(path), "exists": path.exists(), "modified": _iso_mtime(path)}


def _source_status_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    """Provenance per item: its own ``status`` if present, else the status of its ``source_id`` in sources.json."""
    by_source = {s.get("id"): s.get("status") for s in _dicts(data.sources())}
    return _count(it.get("status") if it.get("status") is not None else by_source.get(it.get("source_id")) for it in items)


def _fictional_flag(raw: Any, items: list[dict[str, Any]]) -> bool | None:
    if isinstance(raw, dict) and isinstance(raw.get("fictional"), bool):
        return raw["fictional"]
    flags = [x.get("fictional") for x in items if isinstance(x.get("fictional"), bool)]
    if flags:
        return all(flags)
    return None


# ---------------------------------------------------------------------------
# datasets
# ---------------------------------------------------------------------------


def _dataset(dataset_id: str, label: str, path: Path, items: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    row = {"id": dataset_id, "label": label, **_file_info(path), "rows": len(items)}
    row.update(extra)
    return row


def _datasets() -> list[dict[str, Any]]:
    P = config.PROCESSED_DIR
    out: list[dict[str, Any]] = []

    traits = _dicts(data.traits())
    groups = sorted({str(t.get("group")) for t in traits if t.get("group")})
    out.append(_dataset("traits", "Work styles (O*NET 31.0)", P / "traits.json", traits,
                        status_counts=_source_status_counts(traits),
                        groups=groups, group_count=len(groups)))

    occ_raw = data.occupations()
    occ = _dicts(data.occupation_list())
    occ_status = None
    if isinstance(occ_raw, dict) and isinstance(occ_raw.get("provenance"), dict):
        occ_status = normalize_status(occ_raw["provenance"].get("status"))
    out.append(_dataset("occupations", "Occupations for the career-fit model", P / "occupations.json", occ,
                        status_counts={occ_status: len(occ)} if occ_status and occ else {},
                        linked_careers=sum(1 for o in occ if o.get("career_id"))))

    careers = _dicts(data.careers())
    wages = [c.get("wage") for c in careers]
    outlooks = [c.get("outlook") for c in careers]
    out.append(_dataset("careers", "Careers", P / "careers.json", careers,
                        wage_status_counts=_count(w.get("status") for w in wages if isinstance(w, dict)),
                        wages_missing=sum(1 for w in wages if not isinstance(w, dict)),
                        outlook_status_counts=_count(o.get("status") for o in outlooks if isinstance(o, dict)),
                        outlook_missing=sum(1 for o in outlooks if not isinstance(o, dict)),
                        fictional_coworkers=sum(len(_dicts(c.get("coworkers"))) for c in careers)))

    skills = _dicts(data.skills())
    by_source = Counter(str(s.get("source") or s.get("source_id") or "unknown") for s in skills)
    out.append(_dataset("skills", "Skills taxonomy", P / "skills.json", skills, by_source=dict(by_source),
                        status_counts=_source_status_counts(skills)))

    courses = _dicts(data.courses())
    out.append(_dataset("courses", "Courses and learning resources", P / "courses.json", courses,
                        status_counts=_count(c.get("status") for c in courses),
                        hours_status_counts=_count(c.get("hours_status") for c in courses),
                        cost_unknown=sum(1 for c in courses if "cost_usd" in c and c.get("cost_usd") is None)))

    jobs_path = P / "jobs.json"
    jobs = _dicts(data._as_list(data.load_json(jobs_path, []), "jobs"))  # noqa: SLF001 (shared helper)
    out.append(_dataset("jobs", "Job nodes for the skills graph", jobs_path, jobs,
                        status_counts=_count(j.get("status") for j in jobs)))

    programs = _dicts(data.programs())
    out.append(_dataset("programs", "Programs for the planner", P / "programs.json", programs,
                        status_counts=_count(p.get("status") for p in programs),
                        steps=sum(len(_dicts(p.get("steps"))) for p in programs)))

    ev_raw = data.events()
    events = _dicts(data.events_list())
    file_status = ev_raw.get("status") if isinstance(ev_raw, dict) else None
    out.append(_dataset("events", "Workday sim events", P / "events.json", events,
                        file_status=file_status if isinstance(file_status, str) else None,
                        status_counts=_count(e.get("status") for e in events),
                        draft=sum(1 for e in events if normalize_status(e.get("status")) == "DRAFT"),
                        crunch=sum(1 for e in events if e.get("crunch")),
                        careers_covered=len({c for e in events for c in (e.get("career_ids") or []) if isinstance(c, str)})))

    sources = _dicts(data.sources())
    out.append(_dataset("sources", "Source register", P / "sources.json", sources,
                        status_counts=_count(s.get("status") for s in sources)))

    personas_raw = data.personas()
    personas = _dicts(data.persona_list())
    out.append(_dataset("personas", "Demo personas", P / "personas.json", personas,
                        fictional=_fictional_flag(personas_raw, personas)))

    for dataset_id, label, loader, name in (
        ("learners", "Synthetic learners", data.learners, "learners.json"),
        ("talent_pool", "Blind talent cards", data.talent_pool, "talent_pool.json"),
        ("employers", "Synthetic employers", data.employers, "employers.json"),
        ("circles", "Support circles", data.circles, "circles.json"),
    ):
        path = P / "synthetic" / name
        items = _dicts(loader())
        raw = data.load_json(path, {})
        groups_seen = sorted({str(x.get("group")) for x in items if x.get("group") is not None})
        extra: dict[str, Any] = {"fictional": _fictional_flag(raw, items), "status_counts": _count(x.get("status") for x in items)}
        if dataset_id == "talent_pool":
            extra["synthetic_groups"] = len(groups_seen)
        out.append(_dataset(dataset_id, label, path, items, **extra))

    return out


# ---------------------------------------------------------------------------
# models and artifacts
# ---------------------------------------------------------------------------


def _models(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key, script in MODEL_SCRIPTS.items():
        block = metrics.get(key)
        block = block if isinstance(block, dict) else None
        rows.append({
            "key": key,
            "script": script,
            "script_exists": (config.ROOT / script).exists(),
            "in_metrics": block is not None,
            "status": block.get("status") if block else None,
            "trained_at": block.get("trained_at") if block else None,
            "reproduce": block.get("reproduce") if block else None,
            "provenance": block.get("provenance") if block else None,
        })
    return rows


def _sha256_prefix(path: Path) -> str | None:
    try:
        if path.stat().st_size > _HASH_LIMIT_BYTES:
            return None
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()[:12]
    except OSError:
        return None


def _artifacts() -> list[dict[str, Any]]:
    root = config.ARTIFACTS_DIR
    if not root.is_dir():
        return []
    files = sorted((p for p in root.rglob("*") if p.is_file() and not p.name.startswith(".")), key=lambda p: p.as_posix())
    out = []
    for p in files[:_MAX_ARTIFACTS]:
        try:
            size = p.stat().st_size
        except OSError:
            continue
        out.append({"name": p.relative_to(root).as_posix(), "bytes": size, "modified": _iso_mtime(p), "sha256": _sha256_prefix(p)})
    return out


# ---------------------------------------------------------------------------
# privacy parameters (read from code, never restated by hand)
# ---------------------------------------------------------------------------


def _module_int_constants(path: Path) -> list[dict[str, Any]]:
    """Module-level ``NAME = <int>`` assignments whose name looks like a minimum group size."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return []
    found = []
    for node in tree.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        if value is None or not isinstance(value, ast.Constant) or not isinstance(value.value, int) or isinstance(value.value, bool):
            continue
        for t in targets:
            if isinstance(t, ast.Name) and _GROUP_SIZE_NAME.match(t.id):
                found.append({"name": t.id, "value": int(value.value), "file": _rel(path)})
    return found


def _privacy() -> dict[str, Any]:
    out: dict[str, Any] = {"session": None, "password_hashing": None, "min_group_sizes": []}
    try:
        from foothold import auth

        out["session"] = {
            "token_ttl_hours": round(auth.TOKEN_TTL_SECONDS / 3600, 2),
            "signature": "HMAC-SHA256",
            "storage": "sessionStorage (one session per browser tab)",
            "logout_revokes_token": True,
        }
        out["password_hashing"] = {
            "algorithm": "scrypt",
            "n": auth.SCRYPT_N,
            "r": auth.SCRYPT_R,
            "p": auth.SCRYPT_P,
            "salt_bytes": auth.SALT_BYTES,
        }
    except Exception:  # auth module mid-edit or missing: report nothing rather than guess
        pass
    for rel in _GROUP_SIZE_MODULES:
        out["min_group_sizes"].extend(_module_int_constants(config.ROOT / rel))
    return out


def _verifier_tolerances() -> list[dict[str, Any]]:
    """``TOLERANCES`` from foothold/verifier.py (unit -> (abs, rel)), parsed with ast, not imported."""
    path = config.ROOT / "api" / "foothold" / "verifier.py"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return []
    for node in tree.body:
        target = node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 else getattr(node, "target", None)
        value = getattr(node, "value", None)
        if isinstance(target, ast.Name) and target.id == "TOLERANCES" and value is not None:
            try:
                table = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                return []
            if not isinstance(table, dict):
                return []
            out = []
            for unit, pair in table.items():
                if isinstance(unit, str) and isinstance(pair, (tuple, list)) and len(pair) == 2:
                    out.append({"unit": unit, "abs": float(pair[0]), "rel": float(pair[1])})
            return out
    return []


# ---------------------------------------------------------------------------
# route
# ---------------------------------------------------------------------------


@router.get("/inventory")
def inventory() -> dict[str, Any]:
    """Live provenance inventory for the Lab and About sheets (see module docstring)."""
    metrics = data.metrics()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "metrics_file": {**_file_info(config.metrics_path()), "keys": sorted(k for k, v in metrics.items() if isinstance(v, dict))},
        "datasets": _datasets(),
        "models": _models(metrics),
        "artifacts": _artifacts(),
        "privacy": _privacy(),
        "verifier_tolerances": _verifier_tolerances(),
    }
