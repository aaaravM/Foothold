"""Pathway planner: OR-Tools CP-SAT schedule optimizer + greedy baseline (CONTRACTS §5, §9, §10).

Shared by the API (``routes/path.py``, ``graphs/pathway.py``) and ``ml/eval_planner.py``.

Input: one program from ``data/processed/programs.json`` (contract shape)::

    {id, career_id, route_type, name, provider, credential, url, status, source_id,
     steps: [{id, title, kind: course|block|job, units?, hours_per_week, weeks, cost_usd,
              prereqs: [step_id], sections: [{id, days: ["Mon", ...], start: "18:00", end: "20:50",
              modality: in_person|online|hybrid, campus?}], paid_wage_hourly?}]}

Optional fields honoured when present: step ``coreqs`` (same start term), step/section
``terms_offered`` (seasons), step ``continuous`` (runs through summers), step
``study_hours_per_week`` / ``class_hours_per_week``, program ``per_term_fee_usd``, program
``rules`` / ``transfer_rules`` (``{type: "before", step, before}``, ``{type:
"min_units_before", units, before}``) for transfer articulation.

Model (one CP-SAT model per program):

* Time grid = academic terms from the next term start after ``today`` (generic semester
  pattern: Spring Jan-May, Summer Jun-Jul, Fall Aug-Dec; an assumption shown to users).
* Booleans ``x[step, start_term, section]`` (exactly one per step). Course/block steps
  cover consecutive regular terms (18 instructional weeks each, summers skipped; summer
  only for steps of <= 8 weeks). Paid job / apprenticeship steps run continuously in months.
* Hard constraints: prerequisites (start after the prereq's last term), co-requisites,
  weekly hours per term (step hours + class time, plus round-trip commute counted once per
  distinct campus day), no overlapping meeting times (clique constraint at every section
  start point), section filters from the learner's rules (earliest start / latest end,
  days off, online-only, in-person-only, campus-day cap), budget (whole plan) and optional
  per-term cost cap, max courses per term, no summer, earliest start, finish-by month,
  transfer articulation rules.
* Objective (integer, "dollar-equivalent" weights): ``3000 * months + cost + W_s * patterns``
  where ``patterns`` = distinct weekly meeting patterns (schedule changes = patterns - 1) and
  ``W_s = 400 * (1 + 0.5 * dependents)``; a tiny tie-break prefers earlier starts.

Greedy baseline: steps in prerequisite order, each placed in the earliest term and first
section that fits the remaining hours, meeting times, caps and budget (no look-ahead).

Every plan is re-checked by :func:`verify_plan`, which recomputes hours, conflicts, costs
and rules from the raw program data (independent of the solver's internal model).
Nothing here logs user text.
"""

from __future__ import annotations

import logging
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Callable, Iterable, Mapping, Sequence

from ortools.sat.python import cp_model

from . import data as fdata

log = logging.getLogger("foothold.planner")

# ---------------------------------------------------------------------------
# Vocabularies and model constants
# ---------------------------------------------------------------------------

DAYS: tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
ROUTE_TYPES: tuple[str, ...] = ("cc_transfer", "certificate", "apprenticeship", "direct_to_work")
ROUTE_LABELS: dict[str, str] = {
    "cc_transfer": "Community college, then transfer",
    "certificate": "Certificate",
    "apprenticeship": "Apprenticeship",
    "direct_to_work": "Straight to work",
}
SEASONS: tuple[str, ...] = ("spring", "summer", "fall")
SEASON_START_MONTH = {"spring": 1, "summer": 6, "fall": 8}  # calendar month the term starts
SEASON_MONTHS = {"spring": 5, "summer": 2, "fall": 5}  # calendar length (sums to 12)
REGULAR_TERM_WEEKS = 18  # instructional weeks a Spring/Fall term holds (assumption)
SUMMER_TERM_WEEKS = 8  # longest step that fits a summer session (assumption)
DAYS_PER_MONTH = 30.4375

MODALITIES = ("in_person", "online", "hybrid")

RULE_TYPES: tuple[str, ...] = (
    "no_class_before",  # time: no class meeting starts before HH:MM
    "no_class_after",  # time: no class meeting ends after HH:MM
    "day_off",  # day: no class meetings that day
    "online_only",
    "in_person_only",
    "max_hours_per_week",  # number (hours, class + study + commute)
    "max_budget",  # number (USD, whole plan)
    "max_cost_per_term",  # number (USD per term)
    "max_campus_days",  # number (days per week on campus)
    "max_courses_per_term",  # number
    "no_summer",
    "earliest_start",  # season (+ optional year in number)
    "max_months",  # number (finish within N months of the plan start)
    "avoid_route",  # route_type
)

DEFAULT_WEIGHTS = {"months": 3000.0, "cost": 1.0, "patterns": 400.0}
OBJ_SCALE = 1000  # keeps the earlier-start tie-break below one dollar-equivalent
MAX_START_TERMS = 36  # hard cap on the planning horizon (12 years)
MAX_CANDIDATES_PER_ROUTE = 3

DEFAULT_TIME_LIMIT_S = 0.8
DEFAULT_WORKERS = 4

ASSUMPTIONS_BASE: tuple[str, ...] = (
    "Terms follow a generic semester pattern (Spring Jan-May, Summer Jun-Jul, Fall Aug-Dec). "
    "Check your college's academic calendar.",
    "Weekly hours = each step's listed hours per week (class and study) plus round-trip commute "
    "time for each distinct day on campus.",
    "Paid on-the-job hours (apprenticeship or job steps) replace work hours, so they are not counted "
    "against your study hours.",
    "Schedule changes = distinct weekly class patterns in the plan, minus one.",
)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_DAY_ALIASES = {
    "m": "Mon", "mo": "Mon", "mon": "Mon", "monday": "Mon", "mondays": "Mon",
    "t": "Tue", "tu": "Tue", "tue": "Tue", "tues": "Tue", "tuesday": "Tue", "tuesdays": "Tue",
    "w": "Wed", "we": "Wed", "wed": "Wed", "wednesday": "Wed", "wednesdays": "Wed",
    "th": "Thu", "r": "Thu", "thu": "Thu", "thur": "Thu", "thurs": "Thu", "thursday": "Thu", "thursdays": "Thu",
    "f": "Fri", "fr": "Fri", "fri": "Fri", "friday": "Fri", "fridays": "Fri",
    "sa": "Sat", "sat": "Sat", "saturday": "Sat", "saturdays": "Sat",
    "su": "Sun", "sun": "Sun", "sunday": "Sun", "sundays": "Sun",
}
_TIME_RE = re.compile(r"^\s*(\d{1,2})(?::?(\d{2}))?\s*([ap]\.?m\.?)?\s*$", re.I)


def parse_day(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return _DAY_ALIASES.get(value.strip().lower().rstrip("."))


def parse_days(value: Any) -> tuple[str, ...]:
    """["Mon","Wed"], "MW", "TTh", "Mon/Wed", "Tue, Thu" -> ordered unique day codes."""
    found: set[str] = set()
    items: list[Any]
    if isinstance(value, str):
        parts = [p for p in re.split(r"[\s,/;&+]+", value) if p]
        items = []
        for p in parts:
            if parse_day(p):
                items.append(p)
            else:  # compact form like "MW" or "TTh"
                items.extend(re.findall(r"Th|Tu|Sa|Su|M|T|W|R|F", p))
    elif isinstance(value, (list, tuple)):
        items = list(value)
    else:
        items = []
    for it in items:
        d = parse_day(it)
        if d:
            found.add(d)
    return tuple(d for d in DAYS if d in found)


def parse_time(value: Any) -> int | None:
    """"18:00" / "6:00 PM" / "6pm" / "1800" -> minutes after midnight (None if unparseable)."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        v = int(value)
        return v if 0 <= v <= 24 * 60 else None
    s = str(value).strip().lower()
    if s in {"noon", "12 noon"}:
        return 12 * 60
    if s == "midnight":
        return 0
    m = re.match(r"^(\d{3,4})$", s)
    if m:  # "1800" / "930"
        v = int(m.group(1))
        h, mi = divmod(v, 100)
        return h * 60 + mi if h <= 24 and mi < 60 else None
    m = _TIME_RE.match(s)
    if not m:
        return None
    h = int(m.group(1))
    mi = int(m.group(2) or 0)
    ampm = (m.group(3) or "").replace(".", "")
    if ampm:
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if ampm.startswith("p") else 0)
    if h > 24 or mi >= 60 or (h == 24 and mi):
        return None
    return h * 60 + mi


def fmt_time(minutes: int | None) -> str | None:
    if minutes is None:
        return None
    h, m = divmod(int(minutes), 60)
    return f"{h:02d}:{m:02d}"


def _num(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else default
    if isinstance(value, str):
        try:
            v = float(value.replace(",", "").replace("$", "").strip())
            return v if math.isfinite(v) else default
        except ValueError:
            return default
    return default


def _seasons(value: Any) -> frozenset[str] | None:
    if not value:
        return None
    items = [value] if isinstance(value, str) else list(value) if isinstance(value, (list, tuple, set)) else []
    out = set()
    for it in items:
        s = str(it).strip().lower()
        for season in SEASONS:
            if s.startswith(season[:3]) or (season == "fall" and s.startswith("autumn")):
                out.add(season)
    return frozenset(out) or None


def display_status(status: Any) -> str:
    """Research statuses -> UI provenance (CONTRACTS §12: DERIVED shows as REAL, unverified as SAMPLE)."""
    s = str(status or "").upper()
    if s in {"REAL", "SAMPLE", "SYNTHETIC", "FICTIONAL"}:
        return s
    if s == "DERIVED":
        return "REAL"
    return "SAMPLE"


# ---------------------------------------------------------------------------
# Normalized program data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Section:
    id: str
    days: tuple[str, ...]
    start: int | None
    end: int | None
    modality: str
    campus: str | None = None
    seasons: frozenset[str] | None = None
    cost_usd: float = 0.0
    flexible: bool = False  # synthesized for steps without listed sections

    @property
    def timed(self) -> bool:
        return self.start is not None and self.end is not None and self.end > self.start and bool(self.days)

    @property
    def on_campus(self) -> bool:
        return self.modality in ("in_person", "hybrid") and bool(self.days) and not self.flexible

    @property
    def class_minutes(self) -> int:
        return len(self.days) * (self.end - self.start) if self.timed else 0  # type: ignore[operator]

    @property
    def pattern(self) -> tuple[tuple[str, ...], int, int] | None:
        return (self.days, self.start, self.end) if self.timed else None  # type: ignore[return-value]

    def public(self) -> dict[str, Any]:
        return {
            "section": self.id,
            "days": list(self.days),
            "start": fmt_time(self.start),
            "end": fmt_time(self.end),
            "modality": self.modality,
            "campus": self.campus,
            "flexible": self.flexible,
        }


@dataclass(frozen=True)
class Step:
    id: str
    title: str
    kind: str
    units: float | None
    hours_per_week: float
    weeks: float
    cost_usd: float
    prereqs: tuple[str, ...]
    coreqs: tuple[str, ...]
    sections: tuple[Section, ...]
    paid_wage_hourly: float | None
    continuous: bool
    seasons: frozenset[str] | None
    study_hours_per_week: float
    class_hours_per_week: float | None
    status: str | None
    hours_estimated: bool = False

    @property
    def paid(self) -> bool:
        return self.kind == "job" or (self.paid_wage_hourly is not None and self.paid_wage_hourly > 0)

    @property
    def academic(self) -> bool:
        return not self.continuous


@dataclass(frozen=True)
class Program:
    id: str
    career_id: str
    route_type: str
    name: str
    provider: str
    credential: str
    url: str | None
    status: str
    source_id: str | None
    steps: tuple[Step, ...]
    per_term_fee_usd: float
    rules: tuple[dict[str, Any], ...]
    notes: tuple[str, ...]
    raw: Mapping[str, Any] = field(repr=False, compare=False, hash=False, default_factory=dict)

    def step(self, step_id: str) -> Step | None:
        for s in self.steps:
            if s.id == step_id:
                return s
        return None


def _parse_section(raw: Mapping[str, Any], idx: int, step_id: str) -> Section | None:
    if not isinstance(raw, Mapping):
        return None
    modality = str(raw.get("modality") or "in_person").strip().lower().replace("-", "_").replace(" ", "_")
    if modality in {"inperson", "face_to_face", "f2f", "on_campus", "campus"}:
        modality = "in_person"
    if modality not in MODALITIES:
        modality = "online" if "online" in modality else "in_person"
    start, end = parse_time(raw.get("start")), parse_time(raw.get("end"))
    if start is not None and end is not None and end <= start:
        start = end = None
    return Section(
        id=str(raw.get("id") or f"{step_id}-s{idx + 1}"),
        days=parse_days(raw.get("days")),
        start=start,
        end=end,
        modality=modality,
        campus=str(raw["campus"]) if raw.get("campus") else None,
        seasons=_seasons(raw.get("terms_offered") or raw.get("terms") or raw.get("seasons")),
        cost_usd=max(0.0, _num(raw.get("cost_usd"), 0.0) or 0.0),
    )


def parse_program(raw: Mapping[str, Any]) -> Program:
    """Normalize one programs.json record (tolerant of missing optional fields)."""
    route_type = str(raw.get("route_type") or "")
    steps: list[Step] = []
    notes: list[str] = []
    for i, st in enumerate(raw.get("steps") or []):
        if not isinstance(st, Mapping):
            continue
        sid = str(st.get("id") or f"step{i + 1}")
        kind = str(st.get("kind") or "course").strip().lower()
        if kind not in {"course", "block", "job"}:
            kind = "course"
        units = _num(st.get("units"))
        hours = _num(st.get("hours_per_week"))
        estimated = False
        if hours is None:
            # Contract requires hours_per_week; fall back to 3 h per unit (class + study) and say so.
            hours = 3.0 * units if units else 0.0
            estimated = bool(units)
        weeks = _num(st.get("weeks"), None)
        if weeks is None or weeks <= 0:
            weeks = float(REGULAR_TERM_WEEKS) if kind != "job" else 52.0
        paid = _num(st.get("paid_wage_hourly"))
        cont_flag = st.get("continuous")
        continuous = (
            bool(cont_flag)
            if isinstance(cont_flag, bool)
            else (kind == "job" or (paid is not None and paid > 0) or route_type in ("apprenticeship", "direct_to_work"))
        )
        secs = [s for j, s in enumerate(st.get("sections") or []) if (s := _parse_section(s, j, sid)) is not None]
        if not secs:
            secs = [Section(id=f"{sid}-flex", days=(), start=None, end=None,
                            modality="online" if kind != "job" else "in_person", flexible=True)]
        steps.append(
            Step(
                id=sid,
                title=str(st.get("title") or sid),
                kind=kind,
                units=units,
                hours_per_week=max(0.0, hours),
                weeks=float(weeks),
                cost_usd=max(0.0, _num(st.get("cost_usd"), 0.0) or 0.0),
                prereqs=tuple(str(p) for p in (st.get("prereqs") or []) if p),
                coreqs=tuple(str(p) for p in (st.get("coreqs") or []) if p),
                sections=tuple(secs),
                paid_wage_hourly=paid,
                continuous=continuous,
                seasons=_seasons(st.get("terms_offered") or st.get("terms") or st.get("seasons")),
                study_hours_per_week=max(0.0, _num(st.get("study_hours_per_week"), 0.0) or 0.0),
                class_hours_per_week=_num(st.get("class_hours_per_week")),
                status=str(st["status"]) if st.get("status") else None,
                hours_estimated=estimated,
            )
        )
    if any(s.hours_estimated for s in steps):
        notes.append("Some steps list units but no weekly hours; Foothold estimated 3 hours per unit (class and study).")
    rules = tuple(r for r in [*(raw.get("rules") or []), *(raw.get("transfer_rules") or [])] if isinstance(r, Mapping))
    return Program(
        id=str(raw.get("id") or "program"),
        career_id=str(raw.get("career_id") or ""),
        route_type=route_type,
        name=str(raw.get("name") or raw.get("id") or "Program"),
        provider=str(raw.get("provider") or ""),
        credential=str(raw.get("credential") or ""),
        url=str(raw["url"]) if raw.get("url") else None,
        status=str(raw.get("status") or "SAMPLE"),
        source_id=str(raw["source_id"]) if raw.get("source_id") else None,
        steps=tuple(steps),
        per_term_fee_usd=max(0.0, _num(raw.get("per_term_fee_usd") or raw.get("term_fee_usd"), 0.0) or 0.0),
        rules=rules,
        notes=tuple(notes),
        raw=raw,
    )


# ---------------------------------------------------------------------------
# Learner constraints
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Constraints:
    hours_per_week: float = 10.0
    budget_usd: float = 2000.0
    commute_minutes: float = 20.0  # one way
    dependents: int = 0
    current_credits: float = 0.0
    no_class_before: int | None = None
    no_class_after: int | None = None
    days_off: frozenset[str] = frozenset()
    online_only: bool = False
    in_person_only: bool = False
    max_cost_per_term: float | None = None
    max_campus_days: int | None = None
    max_courses_per_term: int | None = None
    no_summer: bool = False
    earliest_start: str | None = None
    earliest_start_year: int | None = None
    max_months: int | None = None
    avoid_routes: frozenset[str] = frozenset()

    @property
    def cap_minutes(self) -> int:
        return max(0, int(round(self.hours_per_week * 60)))

    @property
    def commute_round_trip_minutes(self) -> int:
        return max(0, int(round(2 * self.commute_minutes)))

    def key(self) -> tuple:
        return (
            round(self.hours_per_week, 2), round(self.budget_usd, 2), round(self.commute_minutes, 2), self.dependents,
            round(self.current_credits, 2), self.no_class_before, self.no_class_after, tuple(sorted(self.days_off)),
            self.online_only, self.in_person_only, self.max_cost_per_term, self.max_campus_days,
            self.max_courses_per_term, self.no_summer, self.earliest_start, self.earliest_start_year,
            self.max_months, tuple(sorted(self.avoid_routes)),
        )

    def summary(self) -> dict[str, Any]:
        """Normalized, UI-friendly view (numbers are the learner's own inputs)."""
        return {
            "hours_per_week": self.hours_per_week,
            "budget_usd": self.budget_usd,
            "commute_minutes": self.commute_minutes,
            "dependents": self.dependents,
            "current_credits": self.current_credits,
            "no_class_before": fmt_time(self.no_class_before),
            "no_class_after": fmt_time(self.no_class_after),
            "days_off": [d for d in DAYS if d in self.days_off],
            "online_only": self.online_only,
            "in_person_only": self.in_person_only,
            "max_cost_per_term": self.max_cost_per_term,
            "max_campus_days": self.max_campus_days,
            "max_courses_per_term": self.max_courses_per_term,
            "no_summer": self.no_summer,
            "earliest_start": self.earliest_start,
            "earliest_start_year": self.earliest_start_year,
            "max_months": self.max_months,
            "avoid_routes": sorted(self.avoid_routes),
        }


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def validate_rule(rule: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return a clean rule dict ``{type, day?, time?, number?, season?, route_type?}`` or None if invalid.

    Used for LLM output, regex mock output, API input and UI-confirmed chips alike.
    """
    if not isinstance(rule, Mapping):
        return None
    rtype = str(rule.get("type") or "").strip().lower()
    if rtype not in RULE_TYPES:
        return None
    out: dict[str, Any] = {"type": rtype}
    if rtype in ("no_class_before", "no_class_after"):
        t = parse_time(rule.get("time"))
        if t is None or not (5 * 60 <= t <= 23 * 60 + 59):
            return None
        out["time"] = fmt_time(t)
    elif rtype == "day_off":
        d = parse_day(rule.get("day"))
        if not d:
            return None
        out["day"] = d
    elif rtype in ("max_hours_per_week", "max_budget", "max_cost_per_term", "max_campus_days", "max_courses_per_term", "max_months"):
        n = _num(rule.get("number"))
        bounds = {
            "max_hours_per_week": (1, 80), "max_budget": (0, 200_000), "max_cost_per_term": (0, 50_000),
            "max_campus_days": (0, 7), "max_courses_per_term": (1, 8), "max_months": (1, 144),
        }[rtype]
        if n is None or not (bounds[0] <= n <= bounds[1]):
            return None
        out["number"] = int(n) if rtype in ("max_campus_days", "max_courses_per_term", "max_months") else round(n, 2)
    elif rtype == "earliest_start":
        season = str(rule.get("season") or "").strip().lower()
        if season not in SEASONS:
            return None
        out["season"] = season
        yr = _num(rule.get("number"))
        if yr is not None and 2020 <= yr <= 2100:
            out["number"] = int(yr)
    elif rtype == "avoid_route":
        rt = str(rule.get("route_type") or "").strip().lower()
        if rt not in ROUTE_TYPES:
            return None
        out["route_type"] = rt
    return out


def rule_key(rule: Mapping[str, Any]) -> tuple:
    return (rule.get("type"), rule.get("day"), rule.get("time"), rule.get("number"), rule.get("season"), rule.get("route_type"))


def dedupe_rules(rules: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple] = set()
    out: list[dict[str, Any]] = []
    for r in rules:
        v = validate_rule(r)
        if v is None:
            continue
        k = rule_key(v)
        if k in seen:
            continue
        seen.add(k)
        out.append(v)
    return out


def describe_rule(rule: Mapping[str, Any]) -> str:
    """Short plain-English chip label for a validated rule."""
    t = rule.get("type")
    n = rule.get("number")
    if t == "no_class_before":
        return f"No class before {rule.get('time')}"
    if t == "no_class_after":
        return f"No class after {rule.get('time')}"
    if t == "day_off":
        return f"{rule.get('day')} off"
    if t == "online_only":
        return "Online only"
    if t == "in_person_only":
        return "In person only"
    if t == "max_hours_per_week":
        return f"At most {n:g} h/week"
    if t == "max_budget":
        return f"Budget at most ${n:,.0f}"
    if t == "max_cost_per_term":
        return f"At most ${n:,.0f} per term"
    if t == "max_campus_days":
        return f"At most {n} campus day{'s' if n != 1 else ''} a week"
    if t == "max_courses_per_term":
        return f"At most {n} class{'es' if n != 1 else ''} per term"
    if t == "no_summer":
        return "No summer classes"
    if t == "earliest_start":
        return f"Start {rule.get('season', '').title()} {n} or later" if n else f"Start in {rule.get('season', '').title()} or later"
    if t == "max_months":
        return f"Finish within {n} months"
    if t == "avoid_route":
        return f"Not the {ROUTE_LABELS.get(str(rule.get('route_type')), str(rule.get('route_type'))).lower()} route"
    return str(t)


def _shorthand_rules(extra: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Accept ``{"no_class_before": "17:00", "days_off": ["Fri"], "online_only": true, ...}``."""
    out: list[dict[str, Any]] = []
    for k, v in extra.items():
        if k in ("constraints", "rules"):
            continue
        if k in ("no_class_before", "no_class_after") and v:
            out.append({"type": k, "time": v})
        elif k in ("days_off", "day_off"):
            for d in v if isinstance(v, (list, tuple)) else [v]:
                out.append({"type": "day_off", "day": d})
        elif k in ("online_only", "in_person_only", "no_summer") and v is True:
            out.append({"type": k})
        elif k in ("max_hours_per_week", "max_budget", "max_cost_per_term", "max_campus_days", "max_courses_per_term", "max_months"):
            out.append({"type": k, "number": v})
        elif k == "earliest_start" and v:
            if isinstance(v, Mapping):
                out.append({"type": k, "season": v.get("season"), "number": v.get("year") or v.get("number")})
            else:
                out.append({"type": k, "season": v})
        elif k in ("avoid_route", "avoid_routes"):
            for r in v if isinstance(v, (list, tuple)) else [v]:
                out.append({"type": "avoid_route", "route_type": r})
    return out


def rules_from_extra(extra: Any) -> list[dict[str, Any]]:
    """``extra_constraints`` may be a list of rule objects, ``{constraints: [...]}`` or shorthand keys."""
    raw: list[Any] = []
    if isinstance(extra, (list, tuple)):
        raw = list(extra)
    elif isinstance(extra, Mapping):
        for key in ("constraints", "rules"):
            if isinstance(extra.get(key), (list, tuple)):
                raw.extend(extra[key])
        raw.extend(_shorthand_rules(extra))
    return dedupe_rules(raw)


def make_constraints(
    *,
    hours_per_week: float | None = None,
    budget_usd: float | None = None,
    commute_minutes: float | None = None,
    dependents: int | None = None,
    current_credits: float | None = None,
    rules: Sequence[Mapping[str, Any]] = (),
) -> Constraints:
    """Base inputs + rules (rules only tighten: caps take the minimum, windows the stricter bound)."""
    c = Constraints(
        hours_per_week=_clamp(_num(hours_per_week, 10.0) or 0.0, 0.0, 80.0),
        budget_usd=_clamp(_num(budget_usd, 2000.0) or 0.0, 0.0, 200_000.0),
        commute_minutes=_clamp(_num(commute_minutes, 20.0) or 0.0, 0.0, 240.0),
        dependents=int(_clamp(_num(dependents, 0.0) or 0.0, 0, 12)),
        current_credits=_clamp(_num(current_credits, 0.0) or 0.0, 0.0, 200.0),
    )
    return apply_rules(c, rules)


def apply_rules(c: Constraints, rules: Sequence[Mapping[str, Any]]) -> Constraints:
    days_off = set(c.days_off)
    avoid = set(c.avoid_routes)
    upd: dict[str, Any] = {}

    def tighter_min(name: str, value: float) -> None:
        cur = upd.get(name, getattr(c, name))
        upd[name] = value if cur is None else min(cur, value)

    for raw in rules:
        r = validate_rule(raw)
        if r is None:
            continue
        t = r["type"]
        if t == "no_class_before":
            v = parse_time(r["time"])
            cur = upd.get("no_class_before", c.no_class_before)
            upd["no_class_before"] = v if cur is None else max(cur, v)  # type: ignore[type-var]
        elif t == "no_class_after":
            v = parse_time(r["time"])
            cur = upd.get("no_class_after", c.no_class_after)
            upd["no_class_after"] = v if cur is None else min(cur, v)  # type: ignore[type-var]
        elif t == "day_off":
            days_off.add(r["day"])
        elif t == "online_only":
            upd["online_only"] = True
        elif t == "in_person_only":
            upd["in_person_only"] = True
        elif t == "max_hours_per_week":
            tighter_min("hours_per_week", float(r["number"]))
        elif t == "max_budget":
            tighter_min("budget_usd", float(r["number"]))
        elif t == "max_cost_per_term":
            tighter_min("max_cost_per_term", float(r["number"]))
        elif t == "max_campus_days":
            tighter_min("max_campus_days", int(r["number"]))
        elif t == "max_courses_per_term":
            tighter_min("max_courses_per_term", int(r["number"]))
        elif t == "no_summer":
            upd["no_summer"] = True
        elif t == "earliest_start":
            upd["earliest_start"] = r["season"]
            upd["earliest_start_year"] = r.get("number")
        elif t == "max_months":
            tighter_min("max_months", int(r["number"]))
        elif t == "avoid_route":
            avoid.add(r["route_type"])
    return replace(c, days_off=frozenset(days_off), avoid_routes=frozenset(avoid), **upd)


# ---------------------------------------------------------------------------
# Term calendar
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Term:
    index: int
    season: str
    year: int
    start_month: int  # months after the plan start (term 0 starts at 0)
    end_month: int

    @property
    def label(self) -> str:
        return f"{self.season.title()} {self.year}"

    def public(self) -> dict[str, Any]:
        return {"index": self.index, "term": self.label, "season": self.season, "year": self.year,
                "start_month": self.start_month, "end_month": self.end_month}


def first_term_after(today: date) -> tuple[str, int]:
    """Season and year of the first term that starts after ``today``."""
    for year in (today.year, today.year + 1):
        for season in SEASONS:
            if date(year, SEASON_START_MONTH[season], 1) > today:
                return season, year
    return "spring", today.year + 1  # unreachable


def build_terms(today: date, n: int) -> list[Term]:
    season, year = first_term_after(today)
    idx = SEASONS.index(season)
    out: list[Term] = []
    month = 0
    for i in range(max(1, n)):
        s = SEASONS[idx]
        out.append(Term(i, s, year, month, month + SEASON_MONTHS[s]))
        month += SEASON_MONTHS[s]
        idx += 1
        if idx == len(SEASONS):
            idx = 0
            year += 1
    return out


# ---------------------------------------------------------------------------
# Preparation shared by CP-SAT, greedy and the hint probes
# ---------------------------------------------------------------------------


@dataclass
class _Option:
    t: int
    cover: tuple[int, ...]
    end_month: int


@dataclass
class _Prep:
    program: Program
    c: Constraints
    terms: list[Term]
    steps: list[Step]  # scheduled steps (waived removed), topological order
    waived: list[Step]
    sections: dict[str, list[Section]]  # allowed sections per step
    load: dict[tuple[str, str], int]  # (step, section) -> minutes/week (without commute)
    options: dict[str, list[_Option]]  # allowed start options per step
    prereqs: dict[str, tuple[str, ...]]
    coreqs: list[tuple[str, str]]
    before_rules: list[tuple[str, str]]  # (a, b): a must end before b starts
    min_units_rules: list[tuple[float, str]]  # (units, b): units completed before b starts
    fixed_cost: int
    fee: int
    reason: str | None = None
    reason_code: str | None = None
    excluded: dict[str, dict[str, int]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _topo_order(steps: Sequence[Step], prereqs: Mapping[str, Sequence[str]]) -> list[Step] | None:
    order: list[Step] = []
    placed: set[str] = set()
    remaining = list(steps)
    while remaining:
        progress = False
        for s in list(remaining):
            if all(p in placed for p in prereqs.get(s.id, ())):
                order.append(s)
                placed.add(s.id)
                remaining.remove(s)
                progress = True
        if not progress:
            return None  # cycle
    return order


def _waive_steps(program: Program, c: Constraints) -> list[Step]:
    """Existing credits cover course steps that nothing depends on and that need no prereqs (GE-like),
    in program order, while their units fit. Shown to the learner as an assumption to confirm."""
    if c.current_credits <= 0 or program.route_type not in ("cc_transfer", "certificate"):
        return []
    depended = {p for s in program.steps for p in (*s.prereqs, *s.coreqs)}
    budget = c.current_credits
    waived = []
    for s in program.steps:
        if s.kind != "course" or s.paid or not s.units or s.prereqs or s.coreqs or s.id in depended:
            continue
        if s.units <= budget + 1e-9:
            waived.append(s)
            budget -= s.units
    return waived


def section_exclusion(sec: Section, c: Constraints) -> str | None:
    """Why a section is excluded by the learner's constraints (None = allowed)."""
    if sec.flexible:
        return None
    if c.online_only and sec.modality != "online":
        return "online_only"
    if c.in_person_only and sec.modality == "online":
        return "in_person_only"
    if sec.days and c.days_off.intersection(sec.days):
        return "day_off"
    if sec.timed:
        if c.no_class_before is not None and sec.start < c.no_class_before:  # type: ignore[operator]
            return "no_class_before"
        if c.no_class_after is not None and sec.end > c.no_class_after:  # type: ignore[operator]
            return "no_class_after"
    if c.max_campus_days is not None and sec.on_campus and len(sec.days) > c.max_campus_days:
        return "max_campus_days"
    return None


_EXCLUSION_TEXT = {
    "online_only": "is not offered online",
    "in_person_only": "is only offered online",
    "day_off": "only meets on a day you have off",
    "no_class_before": "only meets earlier than your earliest class time",
    "no_class_after": "only meets later than your latest class time",
    "max_campus_days": "needs more campus days a week than you allowed",
}


def step_load_minutes(step: Step, sec: Section) -> int:
    """Weekly minutes a step adds to the learner's study load (commute excluded)."""
    if step.paid:
        extra = (step.class_hours_per_week or 0.0) + step.study_hours_per_week
        return int(round(max(extra, 0.0) * 60))
    class_h = sec.class_minutes / 60.0
    total = max(step.hours_per_week, class_h) + step.study_hours_per_week
    return int(round(total * 60))


def _cover(step: Step, t: int, terms: Sequence[Term]) -> _Option | None:
    term = terms[t]
    if step.continuous:
        dur = max(1, math.ceil(step.weeks * 7 / DAYS_PER_MONTH))
        end = term.start_month + dur
        cov = []
        u = t
        while u < len(terms) and terms[u].start_month < end:
            cov.append(u)
            u += 1
        if not cov or terms[cov[-1]].end_month < end:
            return None  # beyond the generated calendar
        return _Option(t, tuple(cov), end)
    if term.season == "summer":
        if step.weeks > SUMMER_TERM_WEEKS and not (step.seasons and "summer" in step.seasons):
            return None
        return _Option(t, (t,), term.end_month)
    cov = []
    remaining = step.weeks
    u = t
    while remaining > 1e-9:
        if u >= len(terms):
            return None
        if terms[u].season != "summer":
            cov.append(u)
            remaining -= REGULAR_TERM_WEEKS
        u += 1
    return _Option(t, tuple(cov), terms[cov[-1]].end_month)


def _earliest_start_index(c: Constraints, terms: Sequence[Term]) -> int:
    if not c.earliest_start:
        return 0
    order = SEASONS.index(c.earliest_start)
    for term in terms:
        if c.earliest_start_year is not None:
            if (term.year, SEASONS.index(term.season)) >= (c.earliest_start_year, order):
                return term.index
        elif term.season == c.earliest_start:
            return term.index
    return len(terms)


def _season_ok(step: Step, sec: Section, term: Term, c: Constraints) -> bool:
    if step.academic and c.no_summer and term.season == "summer":
        return False
    if step.seasons and term.season not in step.seasons and step.academic:
        return False
    if sec.seasons and term.season not in sec.seasons:
        return False
    return True


def _rules_from_program(program: Program, ids: set[str]) -> tuple[list[tuple[str, str]], list[tuple[float, str]]]:
    before: list[tuple[str, str]] = []
    min_units: list[tuple[float, str]] = []
    for r in program.rules:
        rtype = str(r.get("type") or "").lower()
        if rtype in ("before", "complete_before", "precedes"):
            b = str(r.get("before") or r.get("then") or "")
            for a in r.get("steps") or ([r.get("step")] if r.get("step") else []):
                if str(a) in ids and b in ids and str(a) != b:
                    before.append((str(a), b))
        elif rtype in ("min_units_before", "units_before"):
            b = str(r.get("before") or "")
            u = _num(r.get("units"))
            if b in ids and u and u > 0:
                min_units.append((float(u), b))
    return before, min_units


def prepare(program: Program, c: Constraints, today: date) -> _Prep:
    waived = _waive_steps(program, c)
    waived_ids = {s.id for s in waived}
    sched = [s for s in program.steps if s.id not in waived_ids]
    ids = {s.id for s in sched}
    prereqs = {s.id: tuple(p for p in s.prereqs if p in ids) for s in sched}
    coreqs = sorted({tuple(sorted((s.id, q))) for s in sched for q in s.coreqs if q in ids and q != s.id})  # type: ignore[misc]
    before_rules, min_units_rules = _rules_from_program(program, ids)
    fee = int(round(program.per_term_fee_usd))
    prep = _Prep(
        program=program, c=c, terms=[], steps=[], waived=waived, sections={}, load={}, options={},
        prereqs=prereqs, coreqs=[(a, b) for a, b in coreqs], before_rules=before_rules,
        min_units_rules=min_units_rules, fixed_cost=int(round(sum(s.cost_usd for s in sched))), fee=fee,
        warnings=list(program.notes),
    )
    if not program.steps:
        prep.reason, prep.reason_code = "This program lists no steps yet.", "no_steps"
        return prep
    # prerequisite edges + articulation "before" rules form the precedence graph
    prec: dict[str, list[str]] = {sid: list(ps) for sid, ps in prereqs.items()}
    for a, b in before_rules:
        prec.setdefault(b, []).append(a)
    order = _topo_order(sched, prec)
    if order is None:
        prep.reason, prep.reason_code = "The program's prerequisites form a loop, so no order works.", "cycle"
        return prep
    prep.steps = order

    cap = c.cap_minutes
    commute = c.commute_round_trip_minutes
    min_section_extra = 0.0
    for s in order:
        allowed: list[Section] = []
        counts: dict[str, int] = {}
        for sec in s.sections:
            why = section_exclusion(sec, c)
            if why:
                counts[why] = counts.get(why, 0) + 1
            else:
                allowed.append(sec)
        prep.excluded[s.id] = counts
        if not allowed:
            top = max(counts, key=lambda k: counts[k]) if counts else "online_only"
            prep.reason = f"No section of {s.title} fits: every section {_EXCLUSION_TEXT.get(top, 'is excluded')}."
            prep.reason_code = f"no_section:{top}"
            return prep
        prep.sections[s.id] = allowed
        best_alone = None
        for sec in allowed:
            ld = step_load_minutes(s, sec)
            prep.load[(s.id, sec.id)] = ld
            alone = ld + (commute * len(sec.days) if sec.on_campus else 0)
            best_alone = alone if best_alone is None else min(best_alone, alone)
        if best_alone is not None and best_alone > cap:
            prep.reason = (
                f"{s.title} alone needs about {best_alone / 60:.1f} h a week (class, study and commute); "
                f"your limit is {c.hours_per_week:g} h."
            )
            prep.reason_code = "hours"
            return prep
        min_section_extra += min(sec.cost_usd for sec in allowed)
        if c.max_cost_per_term is not None and s.academic:
            if s.cost_usd > c.max_cost_per_term + 1e-6 and s.weeks <= REGULAR_TERM_WEEKS:
                prep.reason = f"{s.title} costs ${s.cost_usd:,.0f} in one term; your per-term limit is ${c.max_cost_per_term:,.0f}."
                prep.reason_code = "cost_per_term"
                return prep
    if prep.fixed_cost + min_section_extra > c.budget_usd + 1e-6:
        prep.reason = (
            f"The program costs at least ${prep.fixed_cost + min_section_extra:,.0f}; your budget is ${c.budget_usd:,.0f}."
        )
        prep.reason_code = "budget"
        return prep

    # Horizon: a fully sequential schedule (every step alone fits, checked above) bounds the search.
    probe_terms = build_terms(today, MAX_START_TERMS + 160)
    first_ok = _earliest_start_index(c, probe_terms)
    t_next = first_ok
    last_term: dict[str, int] = {}
    for s in order:
        lo = max([t_next] + [last_term[p] + 1 for p in prec.get(s.id, ()) if p in last_term])
        placed = None
        for t in range(lo, MAX_START_TERMS):
            opt = _cover(s, t, probe_terms)
            if opt is None:
                continue
            if any(_season_ok(s, sec, probe_terms[t], c) for sec in prep.sections[s.id]):
                placed = opt
                break
        if placed is None:
            prep.reason = f"{s.title} cannot be scheduled within {MAX_START_TERMS} terms under your rules."
            prep.reason_code = "horizon"
            return prep
        last_term[s.id] = placed.cover[-1]
        t_next = placed.cover[-1] + 1
    horizon = min(MAX_START_TERMS, t_next + 1)
    terms = probe_terms[: horizon + 160]
    prep.terms = terms

    # Start options per step within [earliest, latest] windows (forward/backward passes).
    est: dict[str, int] = {}
    for s in order:
        lo = max([first_ok] + [_first_end(prep, p, est) + 1 for p in prec.get(s.id, ())])
        est[s.id] = lo
    succ: dict[str, list[str]] = {s.id: [] for s in order}
    for b, ps in prec.items():
        for a in ps:
            if a in succ:
                succ[a].append(b)
    lst_last: dict[str, int] = {}  # latest allowed last-covered term per step
    for s in reversed(order):
        bound = horizon - 1
        for q in succ[s.id]:
            bound = min(bound, lst_start(prep, q, lst_last) - 1)
        lst_last[s.id] = bound
    for s in order:
        opts = []
        for t in range(est[s.id], horizon):
            opt = _cover(s, t, terms)
            if opt is None or opt.cover[-1] > lst_last[s.id]:
                continue
            if c.max_months is not None and opt.end_month > c.max_months:
                continue
            if not any(_season_ok(s, sec, terms[t], c) for sec in prep.sections[s.id]):
                continue
            opts.append(opt)
        if not opts:
            if c.max_months is not None:
                prep.reason = f"{s.title} cannot finish within {c.max_months} months under your rules."
                prep.reason_code = "max_months"
            else:
                prep.reason = f"{s.title} has no term that fits your rules."
                prep.reason_code = "no_term"
            return prep
        prep.options[s.id] = opts
    return prep


def _first_end(prep: _Prep, step_id: str, est: Mapping[str, int]) -> int:
    """Last covered term if ``step_id`` starts at its earliest start (lower bound for successors)."""
    s = next(x for x in prep.steps if x.id == step_id)
    terms = build_terms(date.today(), 1) if not prep.terms else prep.terms
    probe = terms if len(terms) > est.get(step_id, 0) + 40 else build_terms(date.today(), est.get(step_id, 0) + 200)
    for t in range(est.get(step_id, 0), est.get(step_id, 0) + 40):
        opt = _cover(s, t, probe)
        if opt is not None:
            return opt.cover[-1]
    return est.get(step_id, 0)


def lst_start(prep: _Prep, step_id: str, lst_last: Mapping[str, int]) -> int:
    """Latest start term index of ``step_id`` compatible with its latest last-covered term."""
    s = next(x for x in prep.steps if x.id == step_id)
    bound = lst_last.get(step_id, MAX_START_TERMS)
    best = 0
    terms = prep.terms
    for t in range(0, min(len(terms), MAX_START_TERMS + 1)):
        opt = _cover(s, t, terms)
        if opt is not None and opt.cover[-1] <= bound:
            best = t
    return best


# ---------------------------------------------------------------------------
# Plan assembly (shared by CP-SAT and greedy, so both report identical metrics)
# ---------------------------------------------------------------------------


def _assemble(prep: _Prep, assign: Mapping[str, tuple[int, str]]) -> dict[str, Any]:
    """assign: step_id -> (start term index, section id)."""
    c = prep.c
    terms = prep.terms
    by_id = {s.id: s for s in prep.steps}
    sec_by = {(sid, sec.id): sec for sid, secs in prep.sections.items() for sec in secs}
    term_rows: dict[int, dict[str, Any]] = {}
    end_months: list[int] = []
    patterns: set[tuple] = set()
    section_extra = 0.0
    enrolled: set[int] = set()
    for sid, (t, sec_id) in assign.items():
        s = by_id[sid]
        sec = sec_by[(sid, sec_id)]
        opt = _cover(s, t, terms)
        assert opt is not None
        end_months.append(opt.end_month)
        if sec.pattern:
            patterns.add(sec.pattern)
        section_extra += sec.cost_usd
        for k, u in enumerate(opt.cover):
            row = term_rows.setdefault(u, {"load": 0, "days": set(), "steps": [], "cost": 0.0})
            row["load"] += prep.load[(sid, sec_id)]
            if sec.on_campus:
                row["days"].update(sec.days)
            if s.academic:
                enrolled.add(u)
            row["cost"] += s.cost_usd / len(opt.cover)
            row["steps"].append(
                {
                    "step": s.id,
                    "title": s.title,
                    "kind": s.kind,
                    "units": s.units,
                    "continues": k > 0,
                    "paid": s.paid,
                    "paid_wage_hourly": s.paid_wage_hourly,
                    "hours_per_week": round(prep.load[(sid, sec_id)] / 60, 1),
                    **sec.public(),
                }
            )
    fee_total = prep.fee * len(enrolled)
    out_terms = []
    commute = c.commute_round_trip_minutes
    for u in sorted(term_rows):
        row = term_rows[u]
        days = [d for d in DAYS if d in row["days"]]
        hours = (row["load"] + commute * len(days)) / 60
        row["steps"].sort(key=lambda r: (r["start"] or "99:99", r["step"]))
        out_terms.append(
            {
                **terms[u].public(),
                "hours_per_week": round(hours, 1),
                "commute_hours_per_week": round(commute * len(days) / 60, 1),
                "campus_days": days,
                "cost_usd": round(row["cost"] + (prep.fee if u in enrolled else 0)),
                "steps": row["steps"],
            }
        )
    months = max(end_months) if end_months else 0
    cost = prep.fixed_cost + section_extra + fee_total
    first = terms[min(t for t, _ in assign.values())].label if assign else None
    return {
        "months": int(months),
        "cost_usd": int(round(cost)),
        "cost_breakdown": {"steps_usd": prep.fixed_cost, "section_fees_usd": int(round(section_extra)),
                           "term_fees_usd": int(fee_total)},
        "schedule_patterns": len(patterns),
        "schedule_changes": max(0, len(patterns) - 1),
        "peak_hours_per_week": max((t["hours_per_week"] for t in out_terms), default=0.0),
        "start_term": first,
        "finish_term": terms[max(_cover(by_id[s], t, terms).cover[-1] for s, (t, _) in assign.items())].label if assign else None,  # type: ignore[union-attr]
        "terms": out_terms,
        "assignment": {sid: {"term_index": t, "section": sec} for sid, (t, sec) in assign.items()},
    }


def objective_value(plan: Mapping[str, Any], c: Constraints, weights: Mapping[str, float] | None = None) -> float:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    w_pat = w["patterns"] * (1 + 0.5 * c.dependents)
    return w["months"] * plan["months"] + w["cost"] * plan["cost_usd"] + w_pat * plan["schedule_patterns"]


# ---------------------------------------------------------------------------
# CP-SAT
# ---------------------------------------------------------------------------


@dataclass
class _Built:
    model: cp_model.CpModel
    x: dict[tuple[str, int, str], Any]
    months: Any
    load_exprs: dict[int, Any]
    max_load: Any | None


def _build(prep: _Prep, *, mode: str = "optimize", weights: Mapping[str, float] | None = None,
           drop_max_months: bool = False) -> _Built:
    """mode: "optimize" (full model) or "min_hours" (no hours cap; minimize the peak weekly load)."""
    c = prep.c
    terms = prep.terms
    m = cp_model.CpModel()
    x: dict[tuple[str, int, str], Any] = {}
    first: dict[str, Any] = {}
    last: dict[str, Any] = {}
    end: dict[str, Any] = {}

    load_terms: dict[int, list[tuple[Any, int]]] = {}
    campus_cand: dict[tuple[int, str], list[Any]] = {}
    point_cand: dict[tuple[int, str, int], list[Any]] = {}
    acad_active: dict[int, list[Any]] = {}
    cost_terms: dict[int, list[tuple[Any, int]]] = {}
    pattern_cand: dict[tuple, list[Any]] = {}
    extra_cost: list[tuple[Any, int]] = []
    tie: list[tuple[Any, int]] = []

    # distinct section start points per day (clique points for the no-overlap constraint)
    day_points: dict[str, set[int]] = {d: set() for d in DAYS}
    for secs in prep.sections.values():
        for sec in secs:
            if sec.timed:
                for d in sec.days:
                    day_points[d].add(sec.start)  # type: ignore[arg-type]

    for s in prep.steps:
        vars_s: list[Any] = []
        f_terms: list[tuple[Any, int]] = []
        l_terms: list[tuple[Any, int]] = []
        e_terms: list[tuple[Any, int]] = []
        for opt in prep.options[s.id]:
            if drop_max_months is False and c.max_months is not None and opt.end_month > c.max_months:
                continue
            term = terms[opt.t]
            for sec in prep.sections[s.id]:
                if not _season_ok(s, sec, term, c):
                    continue
                v = m.new_bool_var(f"x[{s.id},{opt.t},{sec.id}]")
                x[(s.id, opt.t, sec.id)] = v
                vars_s.append(v)
                f_terms.append((v, opt.t))
                l_terms.append((v, opt.cover[-1]))
                e_terms.append((v, opt.end_month))
                tie.append((v, opt.t))
                ld = prep.load[(s.id, sec.id)]
                share = int(round(s.cost_usd / len(opt.cover)))
                if sec.cost_usd:
                    extra_cost.append((v, int(round(sec.cost_usd))))
                if sec.pattern:
                    pattern_cand.setdefault(sec.pattern, []).append(v)
                pts = []
                if sec.timed:
                    pts = [(d, p) for d in sec.days for p in day_points[d] if sec.start <= p < sec.end]  # type: ignore[operator]
                for u in opt.cover:
                    load_terms.setdefault(u, []).append((v, ld))
                    cost_terms.setdefault(u, []).append((v, share))
                    if sec.on_campus:
                        for d in sec.days:
                            campus_cand.setdefault((u, d), []).append(v)
                    for d, p in pts:
                        point_cand.setdefault((u, d, p), []).append(v)
                    if s.academic:
                        acad_active.setdefault(u, []).append(v)
        if not vars_s:
            m.add_bool_or([])  # infeasible marker: empty clause
            continue
        m.add_exactly_one(vars_s)
        first[s.id] = cp_model.LinearExpr.weighted_sum([v for v, _ in f_terms], [k for _, k in f_terms])
        last[s.id] = cp_model.LinearExpr.weighted_sum([v for v, _ in l_terms], [k for _, k in l_terms])
        end[s.id] = cp_model.LinearExpr.weighted_sum([v for v, _ in e_terms], [k for _, k in e_terms])

    for s in prep.steps:
        if s.id not in first:
            continue
        for p in prep.prereqs.get(s.id, ()):
            if p in last:
                m.add(first[s.id] >= last[p] + 1)
    for a, b in prep.before_rules:
        if a in last and b in first:
            m.add(first[b] >= last[a] + 1)
    for a, b in prep.coreqs:
        if a in first and b in first:
            m.add(first[a] == first[b])
    by_id = {s.id: s for s in prep.steps}
    waived_units = sum(s.units or 0 for s in prep.waived)
    for units, b in prep.min_units_rules:
        if b not in first:
            continue
        need = units - waived_units
        if need <= 0:
            continue
        done_terms = []
        for s in prep.steps:
            if s.id == b or not s.units or s.id not in last:
                continue
            before = m.new_bool_var(f"before[{s.id},{b}]")
            m.add(last[s.id] + 1 <= first[b]).only_enforce_if(before)
            done_terms.append((before, int(round(s.units * 10))))
        m.add(cp_model.LinearExpr.weighted_sum([v for v, _ in done_terms], [k for _, k in done_terms]) >= int(round(need * 10)))
        _ = by_id

    for (u, d, p), vs in point_cand.items():
        if len(vs) > 1:
            m.add(cp_model.LinearExpr.sum(vs) <= 1)

    campus: dict[tuple[int, str], Any] = {}
    for (u, d), vs in campus_cand.items():
        cv = m.new_bool_var(f"campus[{u},{d}]")
        campus[(u, d)] = cv
        for v in vs:
            m.add_implication(v, cv)

    commute = c.commute_round_trip_minutes
    load_exprs: dict[int, Any] = {}
    for u, items in load_terms.items():
        days_u = [campus[(u, d)] for d in DAYS if (u, d) in campus]
        expr = cp_model.LinearExpr.weighted_sum([v for v, _ in items] + days_u, [k for _, k in items] + [commute] * len(days_u))
        load_exprs[u] = expr
        if mode == "optimize":
            m.add(expr <= c.cap_minutes)
        if c.max_campus_days is not None and days_u:
            m.add(cp_model.LinearExpr.sum(days_u) <= c.max_campus_days)

    if c.max_courses_per_term is not None:
        for u, vs in acad_active.items():
            m.add(cp_model.LinearExpr.sum(vs) <= c.max_courses_per_term)

    enrolled: dict[int, Any] = {}
    if prep.fee > 0:
        for u, vs in acad_active.items():
            ev = m.new_bool_var(f"enrolled[{u}]")
            enrolled[u] = ev
            for v in vs:
                m.add_implication(v, ev)

    if c.max_cost_per_term is not None:
        for u, items in cost_terms.items():
            vs = [v for v, _ in items] + ([enrolled[u]] if u in enrolled else [])
            ks = [k for _, k in items] + ([prep.fee] if u in enrolled else [])
            m.add(cp_model.LinearExpr.weighted_sum(vs, ks) <= int(math.floor(c.max_cost_per_term)))

    var_cost = cp_model.LinearExpr.weighted_sum(
        [v for v, _ in extra_cost] + list(enrolled.values()), [k for _, k in extra_cost] + [prep.fee] * len(enrolled)
    )
    if extra_cost or enrolled:
        m.add(var_cost + prep.fixed_cost <= int(math.floor(c.budget_usd)))

    horizon_end = max((o.end_month for opts in prep.options.values() for o in opts), default=1)
    months = m.new_int_var(0, max(1, horizon_end), "months")
    if end:
        m.add_max_equality(months, list(end.values()))

    max_load = None
    if mode == "min_hours":
        max_load = m.new_int_var(0, 80 * 60 + 7 * 480, "max_load")
        for expr in load_exprs.values():
            m.add(expr <= max_load)
        m.minimize(max_load)
    else:
        w = {**DEFAULT_WEIGHTS, **(weights or {})}
        w_pat = w["patterns"] * (1 + 0.5 * c.dependents)
        used = []
        for pat, vs in pattern_cand.items():
            pv = m.new_bool_var(f"pattern[{pat}]")
            used.append(pv)
            for v in vs:
                m.add_implication(v, pv)
        obj = (
            int(round(w["months"] * OBJ_SCALE)) * months
            + int(round(w["cost"] * OBJ_SCALE)) * var_cost
            + int(round(w_pat * OBJ_SCALE)) * cp_model.LinearExpr.sum(used)
            + cp_model.LinearExpr.weighted_sum([v for v, _ in tie], [k for _, k in tie])
        )
        m.minimize(obj)
    return _Built(model=m, x=x, months=months, load_exprs=load_exprs, max_load=max_load)


def _solver(time_limit_s: float, workers: int) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_s)
    solver.parameters.num_workers = int(max(1, workers))
    solver.parameters.random_seed = 0
    return solver


def _hints(prep: _Prep, time_limit_s: float, workers: int) -> dict[str, Any]:
    """When a route is infeasible: the smallest weekly hours (and earliest finish) that would work."""
    hints: dict[str, Any] = {}
    if prep.reason_code in (None, "hours", "max_months", "no_term"):
        try:
            built = _build(prep, mode="min_hours", drop_max_months=False)
            solver = _solver(time_limit_s, workers)
            st = solver.solve(built.model)
            if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) and built.max_load is not None:
                need = solver.value(built.max_load) / 60
                if need > prep.c.hours_per_week + 1e-6:
                    hints["min_hours_per_week"] = math.ceil(need * 2) / 2
        except Exception as exc:  # hints are best effort
            log.warning("planner hint probe failed (%s)", type(exc).__name__)
    return hints


def _infeasible(prep: _Prep, *, reason: str, code: str, status: str, ms: int, hints: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "feasible": False,
        "status": status,
        "reason": reason,
        "reason_code": code,
        "months": None,
        "cost_usd": None,
        "terms": [],
        "solve_ms": ms,
        "hints": hints or {},
        "waived_steps": [{"step": s.id, "title": s.title, "units": s.units} for s in prep.waived],
    }


def solve_cpsat(program: Program, c: Constraints, *, today: date | None = None,
                time_limit_s: float = DEFAULT_TIME_LIMIT_S, workers: int = DEFAULT_WORKERS,
                weights: Mapping[str, float] | None = None, hints: bool = True,
                prep: _Prep | None = None) -> dict[str, Any]:
    t0 = time.perf_counter()
    today = today or date.today()
    prep = prep or prepare(program, c, today)
    if prep.reason:
        h: dict[str, Any] = {}
        if hints and prep.reason_code == "budget":
            h["min_budget_usd"] = int(math.ceil(prep.fixed_cost + sum(min(x.cost_usd for x in prep.sections.get(s.id, [Section('', (), None, None, 'online')])) for s in prep.steps)))
        if hints and prep.reason_code == "hours":
            need = max((min(prep.load[(s.id, sec.id)] + (c.commute_round_trip_minutes * len(sec.days) if sec.on_campus else 0)
                            for sec in prep.sections.get(s.id, [])) for s in prep.steps if prep.sections.get(s.id)), default=0)
            if need:
                h["min_hours_per_week"] = math.ceil(need / 60 * 2) / 2
        return _infeasible(prep, reason=prep.reason, code=prep.reason_code or "infeasible", status="INFEASIBLE",
                           ms=int(round((time.perf_counter() - t0) * 1000)), hints=h)
    built = _build(prep, weights=weights)
    solver = _solver(time_limit_s, workers)
    st = solver.solve(built.model)
    ms = int(round((time.perf_counter() - t0) * 1000))
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        h = _hints(prep, min(0.4, time_limit_s), workers) if hints and st == cp_model.INFEASIBLE else {}
        reason = (
            "No schedule fits all of your limits at once"
            + (f": it needs at least {h['min_hours_per_week']:g} h a week." if "min_hours_per_week" in h else ".")
        )
        if st == cp_model.UNKNOWN:
            reason = "The solver ran out of time before finding a schedule."
        return _infeasible(prep, reason=reason, code="infeasible" if st == cp_model.INFEASIBLE else "timeout",
                           status=solver.status_name(st), ms=int(round((time.perf_counter() - t0) * 1000)), hints=h)
    assign: dict[str, tuple[int, str]] = {}
    for (sid, t, sec_id), v in built.x.items():
        if solver.boolean_value(v):
            assign[sid] = (t, sec_id)
    plan = _assemble(prep, assign)
    plan.update(
        feasible=True,
        status=solver.status_name(st),
        solve_ms=ms,
        hints={},
        reason=None,
        reason_code=None,
        waived_steps=[{"step": s.id, "title": s.title, "units": s.units} for s in prep.waived],
    )
    return plan


# ---------------------------------------------------------------------------
# Greedy baseline
# ---------------------------------------------------------------------------


def solve_greedy(program: Program, c: Constraints, *, today: date | None = None, prep: _Prep | None = None) -> dict[str, Any]:
    """Earliest term, first section that fits; no look-ahead, no re-planning."""
    t0 = time.perf_counter()
    today = today or date.today()
    prep = prep or prepare(program, c, today)
    if prep.reason:
        return _infeasible(prep, reason=prep.reason, code=prep.reason_code or "infeasible", status="INFEASIBLE",
                           ms=int(round((time.perf_counter() - t0) * 1000)))
    terms = prep.terms
    cap = c.cap_minutes
    commute = c.commute_round_trip_minutes
    load: dict[int, int] = {}
    days: dict[int, set[str]] = {}
    busy: dict[int, list[Section]] = {}
    courses: dict[int, int] = {}
    tcost: dict[int, float] = {}
    enrolled: set[int] = set()
    assign: dict[str, tuple[int, str]] = {}
    last_t: dict[str, int] = {}
    start_t: dict[str, int] = {}
    extra = 0.0
    coreq_of: dict[str, set[str]] = {}
    for a, b in prep.coreqs:
        coreq_of.setdefault(a, set()).add(b)
        coreq_of.setdefault(b, set()).add(a)
    prec: dict[str, list[str]] = {sid: list(ps) for sid, ps in prep.prereqs.items()}
    for a, b in prep.before_rules:
        prec.setdefault(b, []).append(a)

    def overlaps(a: Section, b: Section) -> bool:
        return a.timed and b.timed and bool(set(a.days) & set(b.days)) and a.start < b.end and b.start < a.end  # type: ignore[operator]

    for s in prep.steps:
        lo = max([0] + [last_t[p] + 1 for p in prec.get(s.id, ()) if p in last_t])
        fixed_start = next((start_t[q] for q in coreq_of.get(s.id, ()) if q in start_t), None)
        placed = False
        for opt in prep.options[s.id]:
            if opt.t < lo or (fixed_start is not None and opt.t != fixed_start):
                continue
            for sec in prep.sections[s.id]:
                if not _season_ok(s, sec, terms[opt.t], c):
                    continue
                ok = True
                share = s.cost_usd / len(opt.cover)
                for u in opt.cover:
                    new_days = set(sec.days) - days.get(u, set()) if sec.on_campus else set()
                    total_days = len(days.get(u, set())) + len(new_days)
                    if load.get(u, 0) + prep.load[(s.id, sec.id)] + commute * total_days > cap:
                        ok = False
                    elif c.max_campus_days is not None and total_days > c.max_campus_days:
                        ok = False
                    elif any(overlaps(sec, other) for other in busy.get(u, [])):
                        ok = False
                    elif c.max_courses_per_term is not None and s.academic and courses.get(u, 0) + 1 > c.max_courses_per_term:
                        ok = False
                    elif c.max_cost_per_term is not None and (
                        tcost.get(u, 0.0) + share + (prep.fee if s.academic and u not in enrolled else 0) > c.max_cost_per_term + 1e-6
                    ):
                        ok = False
                    if not ok:
                        break
                if not ok:
                    continue
                for u in opt.cover:
                    load[u] = load.get(u, 0) + prep.load[(s.id, sec.id)]
                    if sec.on_campus:
                        days.setdefault(u, set()).update(sec.days)
                    busy.setdefault(u, []).append(sec)
                    if s.academic:
                        courses[u] = courses.get(u, 0) + 1
                        if u not in enrolled:
                            tcost[u] = tcost.get(u, 0.0) + prep.fee
                            enrolled.add(u)
                    tcost[u] = tcost.get(u, 0.0) + share
                extra += sec.cost_usd
                assign[s.id] = (opt.t, sec.id)
                last_t[s.id] = opt.cover[-1]
                start_t[s.id] = opt.t
                placed = True
                break
            if placed:
                break
        if not placed:
            return _infeasible(prep, reason=f"Greedy could not place {s.title}.", code="greedy_stuck", status="INFEASIBLE",
                               ms=int(round((time.perf_counter() - t0) * 1000)))
    # min-units articulation rules are checked after the fact (greedy has no look-ahead)
    plan = _assemble(prep, assign)
    if plan["cost_usd"] > c.budget_usd + 1e-6:
        return _infeasible(prep, reason="Greedy plan goes over budget.", code="budget", status="INFEASIBLE",
                           ms=int(round((time.perf_counter() - t0) * 1000)))
    checks = verify_plan(plan, program, c, today=today)
    if not all(ch["ok"] for ch in checks):
        bad = next(ch for ch in checks if not ch["ok"])
        return _infeasible(prep, reason=f"Greedy plan breaks a rule ({bad['label']}).", code="greedy_rule",
                           status="INFEASIBLE", ms=int(round((time.perf_counter() - t0) * 1000)))
    plan.update(feasible=True, status="GREEDY", solve_ms=int(round((time.perf_counter() - t0) * 1000)), hints={},
                reason=None, reason_code=None,
                waived_steps=[{"step": s.id, "title": s.title, "units": s.units} for s in prep.waived])
    return plan


# ---------------------------------------------------------------------------
# Independent verification
# ---------------------------------------------------------------------------


def verify_plan(plan: Mapping[str, Any], program: Program, c: Constraints, *, today: date | None = None) -> list[dict[str, Any]]:
    """Re-check a plan against the raw program data and every learner constraint.

    Recomputes coverage, weekly hours (with commute per distinct campus day), meeting-time
    overlaps, costs and rule compliance from ``program`` itself rather than the solver model.
    Returns ``[{id, label, ok, detail}]``.
    """
    checks: list[dict[str, Any]] = []

    def add(cid: str, label: str, ok: bool, detail: str = "") -> None:
        checks.append({"id": cid, "label": label, "ok": bool(ok), "detail": detail})

    if not plan.get("feasible"):
        add("feasible", "Plan exists", False, "no plan to verify")
        return checks
    today = today or date.today()
    assignment: Mapping[str, Mapping[str, Any]] = plan.get("assignment") or {}
    waived = {w["step"] for w in plan.get("waived_steps") or []}
    steps = {s.id: s for s in program.steps}
    need = {sid for sid in steps if sid not in waived}
    got = set(assignment)
    add("complete", "Every required step is scheduled once", need == got,
        "" if need == got else f"missing {sorted(need - got)[:3]} extra {sorted(got - need)[:3]}")
    if need != got:
        return checks

    max_t = max(int(a["term_index"]) for a in assignment.values()) if assignment else 0
    terms = build_terms(today, max_t + 200)
    span: dict[str, tuple[int, tuple[int, ...], int]] = {}
    secs: dict[str, Section] = {}
    for sid, a in assignment.items():
        s = steps[sid]
        sec = next((x for x in s.sections if x.id == a["section"]), None)
        if sec is None:
            add("section_exists", "Chosen sections exist", False, f"{sid}: {a['section']}")
            return checks
        secs[sid] = sec
        opt = _cover(s, int(a["term_index"]), terms)
        if opt is None:
            add("coverage", "Steps fit the term calendar", False, sid)
            return checks
        span[sid] = (opt.t, opt.cover, opt.end_month)

    bad_pre = [f"{sid}<-{p}" for sid in span for p in steps[sid].prereqs
               if p in span and span[sid][0] <= span[p][1][-1]]
    add("prereqs", "Prerequisites finish first", not bad_pre, ", ".join(bad_pre[:3]))
    bad_co = [f"{sid}+{q}" for sid in span for q in steps[sid].coreqs if q in span and span[sid][0] != span[q][0]]
    add("coreqs", "Co-requisites share a term", not bad_co, ", ".join(bad_co[:3]))
    before, min_units = _rules_from_program(program, set(span))
    bad_rule = [f"{a}->{b}" for a, b in before if span[b][0] <= span[a][1][-1]]
    waived_units = sum(steps[w].units or 0 for w in waived if w in steps)
    for units, b in min_units:
        done = waived_units + sum(steps[s].units or 0 for s in span if s != b and span[s][1][-1] < span[b][0])
        if done + 1e-9 < units:
            bad_rule.append(f"{units:g} units before {b}")
    add("articulation", "Transfer rules are met", not bad_rule, ", ".join(bad_rule[:3]))

    per_term_load: dict[int, int] = {}
    per_term_days: dict[int, set[str]] = {}
    per_term_secs: dict[int, list[tuple[str, Section]]] = {}
    per_term_courses: dict[int, int] = {}
    per_term_cost: dict[int, float] = {}
    enrolled: set[int] = set()
    for sid, (t, cover, _end) in span.items():
        s, sec = steps[sid], secs[sid]
        for u in cover:
            per_term_load[u] = per_term_load.get(u, 0) + step_load_minutes(s, sec)
            if sec.on_campus:
                per_term_days.setdefault(u, set()).update(sec.days)
            per_term_secs.setdefault(u, []).append((sid, sec))
            if s.academic:
                per_term_courses[u] = per_term_courses.get(u, 0) + 1
                enrolled.add(u)
            per_term_cost[u] = per_term_cost.get(u, 0.0) + s.cost_usd / len(cover)
    fee = program.per_term_fee_usd
    commute = c.commute_round_trip_minutes
    over = []
    for u, ld in per_term_load.items():
        total = ld + commute * len(per_term_days.get(u, set()))
        if total > c.cap_minutes:
            over.append(f"{terms[u].label} {total / 60:.1f} h")
    add("hours", f"Every term fits {c.hours_per_week:g} h/week (with commute)", not over, ", ".join(over[:3]))

    clash = []
    for u, items in per_term_secs.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i][1], items[j][1]
                if a.timed and b.timed and set(a.days) & set(b.days) and a.start < b.end and b.start < a.end:  # type: ignore[operator]
                    clash.append(f"{terms[u].label}: {items[i][0]}/{items[j][0]}")
    add("conflicts", "No overlapping class times", not clash, ", ".join(clash[:3]))

    window = [sid for sid, sec in secs.items() if sec.timed and (
        (c.no_class_before is not None and sec.start < c.no_class_before) or  # type: ignore[operator]
        (c.no_class_after is not None and sec.end > c.no_class_after))]  # type: ignore[operator]
    add("time_window", "Class times inside your window", not window, ", ".join(window[:3]))
    dayoff = [sid for sid, sec in secs.items() if not sec.flexible and set(sec.days) & c.days_off]
    add("days_off", "No class on your days off", not dayoff, ", ".join(dayoff[:3]))
    if c.online_only:
        bad = [sid for sid, sec in secs.items() if not sec.flexible and sec.modality != "online"]
        add("online_only", "Online sections only", not bad, ", ".join(bad[:3]))
    if c.in_person_only:
        bad = [sid for sid, sec in secs.items() if not sec.flexible and sec.modality == "online"]
        add("in_person_only", "In-person sections only", not bad, ", ".join(bad[:3]))
    if c.max_campus_days is not None:
        bad = [terms[u].label for u, ds in per_term_days.items() if len(ds) > c.max_campus_days]
        add("campus_days", f"At most {c.max_campus_days} campus days a week", not bad, ", ".join(bad[:3]))
    if c.max_courses_per_term is not None:
        bad = [terms[u].label for u, n in per_term_courses.items() if n > c.max_courses_per_term]
        add("courses_per_term", f"At most {c.max_courses_per_term} classes per term", not bad, ", ".join(bad[:3]))
    if c.no_summer:
        bad = [sid for sid, (t, cover, _e) in span.items() if steps[sid].academic and any(terms[u].season == "summer" for u in cover)]
        add("no_summer", "No summer classes", not bad, ", ".join(bad[:3]))
    if c.earliest_start:
        first_ok = _earliest_start_index(c, terms)
        bad = [sid for sid, (t, _c, _e) in span.items() if t < first_ok]
        add("earliest_start", "Starts no earlier than you asked", not bad, ", ".join(bad[:3]))
    months = max(e for _t, _c, e in span.values()) if span else 0
    add("months", "Reported length matches the schedule", int(plan.get("months") or 0) == months, f"{months} vs {plan.get('months')}")
    if c.max_months is not None:
        add("max_months", f"Finishes within {c.max_months} months", months <= c.max_months, f"{months} months")
    if c.max_cost_per_term is not None:
        bad = [terms[u].label for u, v in per_term_cost.items() if v + (fee if u in enrolled else 0) > c.max_cost_per_term + 0.5]
        add("cost_per_term", f"At most ${c.max_cost_per_term:,.0f} per term", not bad, ", ".join(bad[:3]))
    cost = sum(steps[sid].cost_usd for sid in span) + sum(secs[sid].cost_usd for sid in span) + fee * len(enrolled)
    add("cost", "Reported cost matches the program data", abs(cost - float(plan.get("cost_usd") or 0)) <= 1.0,
        f"${cost:,.0f} vs ${plan.get('cost_usd')}")
    add("budget", f"Within your ${c.budget_usd:,.0f} budget", cost <= c.budget_usd + 1.0, f"${cost:,.0f}")
    return checks


# ---------------------------------------------------------------------------
# Routes for a career (API + graph)
# ---------------------------------------------------------------------------

_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="planner")
_PARSE_LOCK = threading.Lock()
_PARSED: dict[int, tuple[Any, list[Program]]] = {}


def parsed_programs() -> list[Program]:
    """programs.json parsed once per file version (data.programs() is mtime-cached)."""
    raw = fdata.programs()
    key = id(raw)
    with _PARSE_LOCK:
        hit = _PARSED.get(key)
        if hit is not None and hit[0] is raw:
            return hit[1]
        progs = [parse_program(p) for p in raw if isinstance(p, Mapping)]
        _PARSED.clear()
        _PARSED[key] = (raw, progs)
        return progs


def programs_for(career_id: str, programs: Sequence[Program] | None = None) -> list[Program]:
    return [p for p in (programs if programs is not None else parsed_programs()) if p.career_id == career_id]


def _source(source_id: str | None) -> dict[str, Any] | None:
    if not source_id:
        return None
    src = fdata.get_source(source_id)
    if not src:
        return {"id": source_id}
    return {"id": source_id, "title": src.get("title"), "url": src.get("url"), "publisher": src.get("publisher"),
            "retrieved": src.get("retrieved"), "status": display_status(src.get("status"))}


def program_public(p: Program) -> dict[str, Any]:
    raw_status = str(p.status).upper()
    return {
        "id": p.id,
        "name": p.name,
        "provider": p.provider,
        "credential": p.credential,
        "url": p.url,
        "status": display_status(p.status),
        "status_note": "derived from official figures" if raw_status == "DERIVED" else None,
        "source": _source(p.source_id),
        "route_type": p.route_type,
        "per_term_fee_usd": p.per_term_fee_usd or None,
        "n_steps": len(p.steps),
        "total_units": round(sum(s.units or 0 for s in p.steps), 1) or None,
    }


_WAGE_NOTES = {
    "logistics_lead": "Career profile is O*NET 11-3071 (transportation, storage and distribution managers); the local wage "
                      "shown is OEWS 53-1047 (first-line supervisors of transportation and material moving workers), the "
                      "closest Stockton-Lodi series.",
}


def expected_wage(career: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """careers.json wage block with provenance (None until the wage build step fills it)."""
    if not career:
        return None
    w = career.get("wage")
    if not isinstance(w, Mapping) or (w.get("median_annual") is None and w.get("median_hourly") is None):
        return None
    out = {k: w.get(k) for k in ("median_hourly", "median_annual", "p25_annual", "p75_annual", "area", "period", "source_id")}
    out["status"] = display_status(w.get("status"))
    out["source"] = _source(w.get("source_id"))
    note = w.get("note") or _WAGE_NOTES.get(str(career.get("id")))
    out["note"] = note
    return out


def _paid_start_wage(p: Program) -> float | None:
    wages = [s.paid_wage_hourly for s in p.steps if s.paid_wage_hourly]
    return float(wages[0]) if wages else None


def solve_program(program: Program, c: Constraints, *, today: date | None = None, time_limit_s: float = DEFAULT_TIME_LIMIT_S,
                  workers: int = DEFAULT_WORKERS, weights: Mapping[str, float] | None = None, hints: bool = True,
                  greedy: bool = True, verify: bool = True) -> dict[str, Any]:
    """CP-SAT plan + greedy comparison + verification for one program."""
    today = today or date.today()
    prep = prepare(program, c, today)
    plan = solve_cpsat(program, c, today=today, time_limit_s=time_limit_s, workers=workers, weights=weights,
                       hints=hints, prep=prep)
    g = solve_greedy(program, c, today=today, prep=prep) if greedy else None
    out = dict(plan)
    if g is not None:
        out["greedy"] = {k: g.get(k) for k in ("feasible", "months", "cost_usd", "schedule_changes", "reason", "solve_ms")}
        if plan.get("feasible") and g.get("feasible"):
            out["delta"] = {"months": plan["months"] - g["months"], "cost_usd": plan["cost_usd"] - g["cost_usd"],
                            "schedule_changes": plan["schedule_changes"] - g["schedule_changes"]}
        else:
            out["delta"] = None
    if verify and plan.get("feasible"):
        checks = verify_plan(plan, program, c, today=today)
        out["checks"] = checks
        out["verified"] = all(ch["ok"] for ch in checks)
    out["objective"] = objective_value(plan, c, weights) if plan.get("feasible") else None
    out["warnings"] = list(prep.warnings)
    return out


def solve_routes(
    career_id: str,
    c: Constraints,
    *,
    today: date | None = None,
    route_types: Sequence[str] | None = None,
    programs: Sequence[Program] | None = None,
    time_limit_s: float = DEFAULT_TIME_LIMIT_S,
    workers: int = DEFAULT_WORKERS,
    weights: Mapping[str, float] | None = None,
    program_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Solve every route type for a career (best of up to 3 candidate programs per route)."""
    t0 = time.perf_counter()
    today = today or date.today()
    career = fdata.get_career(career_id)
    progs = programs_for(career_id, programs)
    if program_ids:
        wanted = set(program_ids)
        progs = [p for p in progs if p.id in wanted] or progs
    rts = list(route_types or [])
    if not rts:
        rts = [rt for rt in ROUTE_TYPES if rt in set((career or {}).get("path_types") or []) or any(p.route_type == rt for p in progs)]
    if not rts:
        rts = list(ROUTE_TYPES)
    jobs: dict[str, list[Program]] = {rt: [p for p in progs if p.route_type == rt][:MAX_CANDIDATES_PER_ROUTE] for rt in rts}
    futures = {
        (rt, p.id): _POOL.submit(solve_program, p, c, today=today, time_limit_s=time_limit_s, workers=workers, weights=weights)
        for rt, ps in jobs.items() if rt not in c.avoid_routes for p in ps
    }
    wage = expected_wage(career)
    routes: dict[str, Any] = {}
    for rt in rts:
        base = {"route_type": rt, "label": ROUTE_LABELS.get(rt, rt), "expected_wage": wage}
        if rt in c.avoid_routes:
            routes[rt] = {**base, "available": bool(jobs[rt]), "feasible": False, "excluded": True,
                          "reason": "Excluded by your rule.", "reason_code": "avoided", "terms": [], "months": None,
                          "cost_usd": None, "greedy": None, "solve_ms": 0}
            continue
        if not jobs[rt]:
            routes[rt] = {**base, "available": False, "feasible": False, "reason": "No program data for this route yet.",
                          "reason_code": "no_program", "terms": [], "months": None, "cost_usd": None, "greedy": None,
                          "solve_ms": 0}
            continue
        results = [(p, futures[(rt, p.id)].result()) for p in jobs[rt]]
        feasible = [(p, r) for p, r in results if r.get("feasible")]
        if feasible:
            best_p, best = min(feasible, key=lambda pr: (pr[1]["objective"], pr[1]["months"], pr[1]["cost_usd"]))
        else:
            best_p, best = results[0]
        alts = [
            {"program": program_public(p), "feasible": bool(r.get("feasible")), "months": r.get("months"),
             "cost_usd": r.get("cost_usd"), "reason": r.get("reason")}
            for p, r in results if p.id != best_p.id
        ]
        routes[rt] = {
            **base,
            **best,
            "available": True,
            "program": program_public(best_p),
            "starting_wage_hourly": _paid_start_wage(best_p),
            "alternatives": alts,
        }
    ranked = sorted(
        [rt for rt in rts if routes[rt].get("feasible")],
        key=lambda rt: (routes[rt]["objective"], routes[rt]["months"]),
    )
    season, year = first_term_after(today)
    assumptions = list(ASSUMPTIONS_BASE)
    waived_any = {w["title"] for r in routes.values() for w in r.get("waived_steps") or []}
    if waived_any:
        assumptions.append(
            f"Your {c.current_credits:g} existing units are assumed to cover: {', '.join(sorted(waived_any))}. "
            "Confirm on ASSIST or with a counselor."
        )
    return {
        "career_id": career_id,
        "career_title": (career or {}).get("title"),
        "start_term": f"{season.title()} {year}",
        "constraints": c.summary(),
        "routes": routes,
        "order": rts,
        "best_route": ranked[0] if ranked else None,
        "solve_ms": int(round((time.perf_counter() - t0) * 1000)),
        "assumptions": assumptions,
        "data_status": {
            "programs": "ok" if progs else ("missing" if not fdata.programs() else "none_for_career"),
            "wage": "ok" if wage else "missing",
        },
    }


__all__ = [
    "Constraints", "DAYS", "Program", "ROUTE_LABELS", "ROUTE_TYPES", "RULE_TYPES", "Section", "Step", "Term",
    "apply_rules", "build_terms", "dedupe_rules", "describe_rule", "expected_wage", "first_term_after",
    "make_constraints", "objective_value", "parse_days", "parse_program", "parse_time", "parsed_programs", "prepare",
    "program_public", "programs_for", "rules_from_extra", "solve_cpsat", "solve_greedy", "solve_program",
    "solve_routes", "validate_rule", "verify_plan",
]
