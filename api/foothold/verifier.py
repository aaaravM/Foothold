"""Claim verification against structured data (CONTRACTS section 1; brief 6.6).

Every factual number Foothold shows in generated prose (a wage, a cost, a duration,
a requirement, an outlook figure) is first expressed as a structured claim and
checked here against ``data/processed/*.json``. Mismatches are dropped (never
shown); claims that cannot be checked are flagged (never shown as fact).

Claim shape (``Claim``)::

    {kind: "wage" | "cost" | "duration" | "requirement" | "outlook",
     value: number | str, unit: str, entity_id: str, source_id: str | None,
     field: str | None}   # optional: which statistic, e.g. "p75_annual"

``outlook`` (growth_pct / annual_openings) extends the four brief kinds so that
every number in the sim report goes through the same check.

Entity resolution
  wage / outlook  -> careers.json by career id, O*NET-SOC code or wage SOC code
  cost / duration -> programs.json program id, a program step id
                     ("<program_id>/<step_id>" or a unique step id), or courses.json id
  requirement     -> programs.json program or careers.json career

Units and tolerances (a claim passes when |claim - expected| <= max(abs, rel x |expected|)):

  ==================  =========  ========  ==============================================
  unit                abs        rel       why
  ==================  =========  ========  ==============================================
  usd_per_hour        $0.05      1%        prose rounds to cents or to the dollar
  usd_per_year        $50        1%        "$76k" for $75,589 passes; "$70k" fails
  usd                 $1         1%        program / course costs
  percent             0.05 pt    0         growth % is published to one decimal
  openings_per_year   0.5        0         annual average openings (integer)
  weeks / months      0.5        0         month = weeks / 4.345
  hours               1 h        5%        course hours are estimates
  units               0.01       0         semester units
  ==================  =========  ========  ==============================================

  Cross-unit wage claims (hourly vs annual) are converted with the OEWS 2,080
  hours/year convention and a 2% relative tolerance. A stated ``source_id`` must
  match the record's ``source_id`` (or the career's wage/outlook source). A
  requirement passes on a normalized exact match with an id/name, or a whole-word
  phrase match inside the credential / step titles.

Nothing here calls an LLM or logs claim text.
"""

from __future__ import annotations

import math
import re
from typing import Any, Iterable, Literal

from pydantic import BaseModel

from . import data

ClaimKind = Literal["wage", "cost", "duration", "requirement", "outlook"]
CLAIM_KINDS: tuple[str, ...] = ("wage", "cost", "duration", "requirement", "outlook")
Status = Literal["verified", "mismatch", "unverifiable"]

HOURS_PER_YEAR = 2080.0  # OEWS annualization convention
WEEKS_PER_MONTH = 4.345

TOLERANCES: dict[str, tuple[float, float]] = {
    "usd_per_hour": (0.05, 0.01),
    "usd_per_year": (50.0, 0.01),
    "usd": (1.0, 0.01),
    "percent": (0.05, 0.0),
    "openings_per_year": (0.5, 0.0),
    "weeks": (0.5, 0.0),
    "months": (0.5, 0.0),
    "hours": (1.0, 0.05),
    "units": (0.01, 0.0),
}
CROSS_UNIT_REL = 0.02

_UNIT_ALIASES = {
    "usd/hr": "usd_per_hour", "usd_hour": "usd_per_hour", "hourly": "usd_per_hour", "per_hour": "usd_per_hour",
    "usd/yr": "usd_per_year", "usd_year": "usd_per_year", "annual": "usd_per_year", "per_year": "usd_per_year",
    "dollars": "usd", "$": "usd", "pct": "percent", "%": "percent", "week": "weeks", "month": "months",
    "hour": "hours", "hrs": "hours", "unit": "units", "openings": "openings_per_year",
}


class Claim(BaseModel):
    kind: ClaimKind
    value: float | int | str
    unit: str
    entity_id: str
    source_id: str | None = None
    field: str | None = None


class ClaimResult(BaseModel):
    claim: Claim
    status: Status
    expected: float | str | None = None
    field: str | None = None
    tolerance: float | None = None
    source_id: str | None = None
    provenance: str | None = None
    reason: str


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) and math.isfinite(float(v)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace(",", "").replace("$", "")
        try:
            f = float(s)
        except ValueError:
            return None
        return f if math.isfinite(f) else None
    return None


def normalize_unit(unit: str) -> str:
    u = (unit or "").strip().lower().replace(" ", "_")
    return _UNIT_ALIASES.get(u, u)


def tolerance_for(unit: str, expected: float) -> float:
    abs_tol, rel_tol = TOLERANCES.get(unit, (0.0, 0.01))
    return max(abs_tol, rel_tol * abs(expected))


def within(value: float, expected: float, unit: str) -> bool:
    return abs(value - expected) <= tolerance_for(unit, expected) + 1e-9


def _norm_text(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def _career_for(entity_id: str) -> dict[str, Any] | None:
    career = data.get_career(entity_id)
    if career is not None:
        return career
    eid = entity_id.strip()
    for c in data.careers():
        if not isinstance(c, dict):
            continue
        socs = {str(c.get("onet_soc") or "")}
        for block in ("wage", "outlook"):
            b = c.get(block)
            if isinstance(b, dict):
                socs.add(str(b.get("soc") or b.get("soc_code") or ""))
        socs |= {s.split(".")[0] for s in socs if s}
        if eid in socs:
            return c
    return None


def _program_steps(program: dict[str, Any]) -> list[dict[str, Any]]:
    steps = program.get("steps")
    return [s for s in steps if isinstance(s, dict)] if isinstance(steps, list) else []


def _find_step(entity_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if "/" in entity_id:
        pid, sid = entity_id.split("/", 1)
        prog = data.get_program(pid)
        if prog:
            for s in _program_steps(prog):
                if s.get("id") == sid:
                    return prog, s
        return None, None
    hits = [(p, s) for p in data.programs() if isinstance(p, dict) for s in _program_steps(p) if s.get("id") == entity_id]
    return hits[0] if len(hits) == 1 else (None, None)


def program_total_cost(program: dict[str, Any]) -> float | None:
    for key in ("total_cost_usd", "cost_usd"):
        v = _num(program.get(key))
        if v is not None:
            return v
    steps = _program_steps(program)
    costs = [_num(s.get("cost_usd")) for s in steps]
    if not steps or any(c is None for c in costs):
        return None
    return float(sum(c for c in costs if c is not None))


def program_duration_weeks(program: dict[str, Any]) -> float | None:
    """Explicit ``duration_weeks`` / ``duration_months``, else the prerequisite critical path (weeks)."""
    v = _num(program.get("duration_weeks"))
    if v is not None:
        return v
    m = _num(program.get("duration_months"))
    if m is not None:
        return m * WEEKS_PER_MONTH
    steps = _program_steps(program)
    if not steps:
        return None
    by_id = {s.get("id"): s for s in steps}
    memo: dict[str, float] = {}

    def finish(sid: str, depth: int = 0) -> float:
        if sid in memo:
            return memo[sid]
        s = by_id.get(sid) or {}
        weeks = _num(s.get("weeks")) or 0.0
        pre = [p for p in (s.get("prereqs") or []) if p in by_id and depth < 64]
        memo[sid] = weeks + (max(finish(p, depth + 1) for p in pre) if pre else 0.0)
        return memo[sid]

    return max(finish(str(s.get("id"))) for s in steps)


def _status_of(rec: dict[str, Any] | None, default: str | None = None) -> str | None:
    if isinstance(rec, dict):
        st = rec.get("status")
        if isinstance(st, str) and st:
            return st.split()[0].upper() if st.split()[0].upper() in {"REAL", "SAMPLE", "SYNTHETIC", "FICTIONAL"} else st
    return default


def _result(claim: Claim, status: Status, reason: str, **kw: Any) -> ClaimResult:
    return ClaimResult(claim=claim, status=status, reason=reason, **kw)


def _check_source(claim: Claim, record_source: str | None) -> str | None:
    """Reason string when the claim cites a different source than the record."""
    if claim.source_id and record_source and claim.source_id != record_source:
        return f"cites {claim.source_id} but the record's source is {record_source}"
    return None


# ---------------------------------------------------------------------------
# per-kind checks
# ---------------------------------------------------------------------------

_WAGE_FIELDS = {
    "usd_per_hour": ("median_hourly", "p25_hourly", "p75_hourly", "mean_hourly"),
    "usd_per_year": ("median_annual", "p25_annual", "p75_annual", "mean_annual"),
}
_HOURLY_TO_ANNUAL = {"median_hourly": "median_annual", "p25_hourly": "p25_annual", "p75_hourly": "p75_annual", "mean_hourly": "mean_annual"}
_ANNUAL_TO_HOURLY = {v: k for k, v in _HOURLY_TO_ANNUAL.items()}


def _check_wage(claim: Claim, unit: str, value: float) -> ClaimResult:
    career = _career_for(claim.entity_id)
    if career is None:
        return _result(claim, "unverifiable", "unknown career / occupation")
    wage = career.get("wage")
    if not isinstance(wage, dict):
        return _result(claim, "unverifiable", "no wage data for this career yet")
    if unit not in _WAGE_FIELDS:
        return _result(claim, "unverifiable", f"unsupported wage unit {unit}")
    field = claim.field or _WAGE_FIELDS[unit][0]
    src = wage.get("source_id")
    expected = _num(wage.get(field))
    tol_unit = unit
    cross = False
    if expected is None:
        # cross-unit: hourly claim vs annual record (or the reverse), OEWS 2,080 h/yr
        other = _HOURLY_TO_ANNUAL.get(field) if unit == "usd_per_hour" else _ANNUAL_TO_HOURLY.get(field)
        base = _num(wage.get(other)) if other else None
        if base is not None:
            expected = base / HOURS_PER_YEAR if unit == "usd_per_hour" else base * HOURS_PER_YEAR
            cross = True
    if expected is None:
        return _result(claim, "unverifiable", f"wage field {field} not published", field=field, source_id=src)
    bad_src = _check_source(claim, src)
    tol = max(tolerance_for(tol_unit, expected), CROSS_UNIT_REL * abs(expected)) if cross else tolerance_for(tol_unit, expected)
    meta = dict(expected=round(expected, 2), field=field, tolerance=round(tol, 4), source_id=src, provenance=_status_of(wage))
    if bad_src:
        return _result(claim, "mismatch", bad_src, **meta)
    if abs(value - expected) <= tol + 1e-9:
        return _result(claim, "verified", "matches " + field + (" (converted at 2,080 h/yr)" if cross else ""), **meta)
    return _result(claim, "mismatch", f"{field} is {expected:,.2f}, claim says {value:,.2f}", **meta)


_OUTLOOK_FIELDS = {"percent": "growth_pct", "openings_per_year": "annual_openings"}


def _check_outlook(claim: Claim, unit: str, value: float) -> ClaimResult:
    career = _career_for(claim.entity_id)
    if career is None:
        return _result(claim, "unverifiable", "unknown career / occupation")
    outlook = career.get("outlook")
    if not isinstance(outlook, dict):
        return _result(claim, "unverifiable", "no outlook data for this career yet")
    field = claim.field or _OUTLOOK_FIELDS.get(unit)
    if not field:
        return _result(claim, "unverifiable", f"unsupported outlook unit {unit}")
    expected = _num(outlook.get(field))
    src = outlook.get("source_id")
    if expected is None:
        return _result(claim, "unverifiable", f"outlook field {field} not published", field=field, source_id=src)
    tol = tolerance_for(unit, expected)
    meta = dict(expected=expected, field=field, tolerance=tol, source_id=src, provenance=_status_of(outlook))
    bad_src = _check_source(claim, src)
    if bad_src:
        return _result(claim, "mismatch", bad_src, **meta)
    if abs(value - expected) <= tol + 1e-9:
        return _result(claim, "verified", f"matches {field}", **meta)
    return _result(claim, "mismatch", f"{field} is {expected:g}, claim says {value:g}", **meta)


def _cost_or_duration_target(claim: Claim) -> tuple[str, dict[str, Any], dict[str, Any] | None] | None:
    """('program'|'step'|'course', record, parent_program)."""
    prog = data.get_program(claim.entity_id)
    if prog:
        return "program", prog, None
    parent, step = _find_step(claim.entity_id)
    if step is not None:
        return "step", step, parent
    course = data.get_course(claim.entity_id)
    if course:
        return "course", course, None
    return None


def _check_cost(claim: Claim, unit: str, value: float) -> ClaimResult:
    if unit != "usd":
        return _result(claim, "unverifiable", f"unsupported cost unit {unit}")
    target = _cost_or_duration_target(claim)
    if target is None:
        return _result(claim, "unverifiable", "unknown program / step / course")
    what, rec, parent = target
    expected = program_total_cost(rec) if what == "program" else _num(rec.get("cost_usd"))
    src = rec.get("source_id") or (parent or {}).get("source_id")
    field = "total_cost_usd" if what == "program" else "cost_usd"
    if expected is None:
        return _result(claim, "unverifiable", f"no cost on this {what}", field=field, source_id=src)
    tol = tolerance_for(unit, expected)
    meta = dict(expected=expected, field=field, tolerance=tol, source_id=src, provenance=_status_of(rec, _status_of(parent)))
    bad_src = _check_source(claim, src)
    if bad_src:
        return _result(claim, "mismatch", bad_src, **meta)
    if abs(value - expected) <= tol + 1e-9:
        return _result(claim, "verified", f"matches {what} {field}", **meta)
    return _result(claim, "mismatch", f"{what} {field} is {expected:,.2f}, claim says {value:,.2f}", **meta)


def _check_duration(claim: Claim, unit: str, value: float) -> ClaimResult:
    target = _cost_or_duration_target(claim)
    if target is None:
        return _result(claim, "unverifiable", "unknown program / step / course")
    what, rec, parent = target
    src = rec.get("source_id") or (parent or {}).get("source_id")
    prov = _status_of(rec, _status_of(parent))
    expected: float | None
    if unit == "hours":
        if what != "course":
            return _result(claim, "unverifiable", "hour durations are only published for courses")
        expected, field = _num(rec.get("hours")), "hours"
    elif unit in ("weeks", "months"):
        weeks = program_duration_weeks(rec) if what == "program" else _num(rec.get("weeks"))
        field = "duration_weeks" if what == "program" else "weeks"
        expected = None if weeks is None else (weeks if unit == "weeks" else weeks / WEEKS_PER_MONTH)
    elif unit == "units":
        expected, field = (_num(rec.get("units")) if what != "course" else None), "units"
    else:
        return _result(claim, "unverifiable", f"unsupported duration unit {unit}")
    if expected is None:
        return _result(claim, "unverifiable", f"no {unit} on this {what}", source_id=src)
    tol = tolerance_for(unit, expected)
    meta = dict(expected=round(expected, 2), field=field, tolerance=tol, source_id=src, provenance=prov)
    bad_src = _check_source(claim, src)
    if bad_src:
        return _result(claim, "mismatch", bad_src, **meta)
    if abs(value - expected) <= tol + 1e-9:
        return _result(claim, "verified", f"matches {what} {field}", **meta)
    return _result(claim, "mismatch", f"{what} {field} is {expected:g}, claim says {value:g}", **meta)


def _requirement_candidates(entity_id: str) -> tuple[str, list[str], str | None, str | None] | None:
    prog = data.get_program(entity_id)
    if prog:
        cands = [prog.get("credential"), prog.get("name"), prog.get("route_type")]
        for s in _program_steps(prog):
            cands += [s.get("id"), s.get("title")]
        for key in ("requirements", "prerequisites", "admission_requirements"):
            v = prog.get(key)
            if isinstance(v, list):
                cands += [x if isinstance(x, str) else (x or {}).get("name") for x in v]
        return "program", [c for c in cands if isinstance(c, str) and c], prog.get("source_id"), _status_of(prog)
    career = data.get_career(entity_id)
    if career:
        skill_names = {s.get("id"): s.get("name") for s in data.skills() if isinstance(s, dict)}
        cands = list(career.get("path_types") or [])
        for sid in career.get("skills") or []:
            cands += [sid, skill_names.get(sid)]
        return "career", [c for c in cands if isinstance(c, str) and c], None, None
    return None


def _check_requirement(claim: Claim) -> ClaimResult:
    target = _requirement_candidates(claim.entity_id)
    if target is None:
        return _result(claim, "unverifiable", "unknown program / career")
    what, cands, src, prov = target
    want = _norm_text(claim.value)
    if not want:
        return _result(claim, "unverifiable", "empty requirement")
    bad_src = _check_source(claim, src)
    if bad_src:
        return _result(claim, "mismatch", bad_src, source_id=src, provenance=prov)
    normed = [_norm_text(c) for c in cands]
    if want in normed:
        return _result(claim, "verified", f"listed on the {what}", expected=claim.value if isinstance(claim.value, str) else None,
                       source_id=src, provenance=prov)
    pattern = re.compile(rf"(?:^| ){re.escape(want)}(?: |$)")
    if len(want) >= 4 and any(pattern.search(c) for c in normed):
        return _result(claim, "verified", f"named in the {what}'s credential or steps", source_id=src, provenance=prov)
    return _result(claim, "mismatch", f"not listed on the {what}", source_id=src, provenance=prov)


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def verify_claim(claim: Claim | dict[str, Any]) -> ClaimResult:
    """Check one claim. Never raises on bad input (returns ``unverifiable``)."""
    try:
        c = claim if isinstance(claim, Claim) else Claim.model_validate(claim)
    except Exception:
        stub = Claim(kind="requirement", value="", unit="", entity_id="?")
        return _result(stub, "unverifiable", "malformed claim")
    if c.kind == "requirement":
        return _check_requirement(c)
    unit = normalize_unit(c.unit)
    value = _num(c.value)
    if value is None:
        return _result(c, "unverifiable", "claim value is not a number")
    if c.kind == "wage":
        return _check_wage(c, unit, value)
    if c.kind == "outlook":
        return _check_outlook(c, unit, value)
    if c.kind == "cost":
        return _check_cost(c, unit, value)
    return _check_duration(c, unit, value)


def verify_claims(claims: Iterable[Claim | dict[str, Any]]) -> dict[str, Any]:
    """``{verified, dropped (mismatch), flagged (unverifiable), counts}`` (results as dicts)."""
    verified: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    flagged: list[dict[str, Any]] = []
    for claim in claims:
        r = verify_claim(claim).model_dump(mode="json")
        {"verified": verified, "mismatch": dropped, "unverifiable": flagged}[r["status"]].append(r)
    return {
        "verified": verified,
        "dropped": dropped,
        "flagged": flagged,
        "counts": {"checked": len(verified) + len(dropped) + len(flagged), "verified": len(verified),
                   "dropped": len(dropped), "flagged": len(flagged)},
    }


# ---------------------------------------------------------------------------
# prose with numbers only from verified claims
# ---------------------------------------------------------------------------

_PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]{0,40})\}")
_NUMBER = re.compile(r"(?<![A-Za-z_])\$?\d[\d,]*(?:\.\d+)?%?")


def placeholder_problems(template: str, allowed: Iterable[str]) -> list[str]:
    """Reasons a generated template is unsafe: digits written outside placeholders, or unknown placeholders."""
    allowed_set = set(allowed)
    problems = [f"unknown placeholder {{{name}}}" for name in _PLACEHOLDER.findall(template) if name not in allowed_set]
    stripped = _PLACEHOLDER.sub("", template)
    if re.search(r"\d", stripped):
        problems.append("digits outside placeholders")
    return problems


def fill_template(template: str, values: dict[str, str]) -> str:
    """Substitute ``{name}`` placeholders (unknown names are left out entirely)."""
    return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), ""), template)


def numbers_in(text: str) -> list[str]:
    return _NUMBER.findall(text or "")


def unbacked_numbers(text: str, allowed_strings: Iterable[str]) -> list[str]:
    """Numbers in ``text`` that do not appear verbatim among the formatted verified values."""
    allowed_norm = {a.replace(",", "") for a in allowed_strings}
    allowed_tokens = {t.replace(",", "") for a in allowed_strings for t in numbers_in(a)}
    out = []
    for tok in numbers_in(text):
        t = tok.replace(",", "")
        if t not in allowed_norm and t not in allowed_tokens:
            out.append(tok)
    return out


__all__ = [
    "CLAIM_KINDS", "Claim", "ClaimResult", "TOLERANCES", "fill_template", "normalize_unit", "numbers_in",
    "placeholder_problems", "program_duration_weeks", "program_total_cost", "tolerance_for", "unbacked_numbers",
    "verify_claim", "verify_claims", "within",
]
