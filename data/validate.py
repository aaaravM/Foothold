#!/usr/bin/env python3
"""Validate every file in data/processed/ against docs/CONTRACTS.md (shapes, id references, provenance).

Usage:
    $FOOTHOLD_PY data/validate.py            # summary table; exit 1 if any ERROR in a file that exists
    $FOOTHOLD_PY data/validate.py -v         # also print every warning / error message

Missing files are reported as MISSING, never fatal. Schemas come from data/schemas/*.schema.json
(written by build_processed.py); a small built-in JSON Schema validator covers the draft 2020-12
keywords those schemas use, so no extra package is needed (jsonschema is used instead if installed).
Stdlib only.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
SCHEMAS = ROOT / "data" / "schemas"

STATUSES = ["REAL", "SAMPLE", "SYNTHETIC", "FICTIONAL"]
ROUTE_TYPES = ["cc_transfer", "certificate", "apprenticeship", "direct_to_work"]
CAREER_IDS = ["logistics_lead", "registered_nurse", "diesel_mechanic", "welder",
              "electrician", "software_dev", "farm_ops_manager", "robotics_tech"]
TRAIT_IDS = ["innovation", "achievement_orientation", "intellectual_curiosity", "tolerance_for_ambiguity",
             "initiative", "adaptability", "self_confidence", "perseverance", "leadership_orientation",
             "humility", "sincerity", "empathy", "cooperation", "optimism", "social_orientation",
             "cautiousness", "attention_to_detail", "dependability", "integrity", "stress_tolerance",
             "self_control"]
SIM_STATS = ["safety", "output", "team_trust", "stress"]
PERSONA_IDS = ["maya", "dev", "luis", "tri_valley_freight"]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
SOC_RE = re.compile(r"^\d{2}-\d{4}\.\d{2}$")
EXPECTED = [
    "sources.json", "traits.json", "skills.json", "careers.json", "occupations.json", "courses.json",
    "jobs.json", "programs.json", "events.json", "personas.json",
    "synthetic/learners.json", "synthetic/employers.json", "synthetic/circles.json", "synthetic/talent_pool.json",
]


# --------------------------------------------------------------------------------------------
# Minimal JSON Schema (draft 2020-12 subset) validator
# --------------------------------------------------------------------------------------------
def _is_type(v, t: str) -> bool:
    if t == "object":
        return isinstance(v, dict)
    if t == "array":
        return isinstance(v, list)
    if t == "string":
        return isinstance(v, str)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "null":
        return v is None
    if t == "integer":
        return (isinstance(v, int) and not isinstance(v, bool)) or (isinstance(v, float) and v.is_integer())
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return False


def _eq(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    return a == b


def _resolve(ref: str, root: dict) -> dict:
    if not ref.startswith("#/"):
        raise ValueError(f"only local $ref supported, got {ref}")
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def schema_errors(inst, schema, root=None, path: str = "$", limit: int = 50) -> list[str]:
    root = root if root is not None else schema
    errs: list[str] = []

    def walk(v, s, p):
        if len(errs) >= limit or s is True or s == {}:
            return
        if s is False:
            errs.append(f"{p}: not allowed")
            return
        if "$ref" in s:
            walk(v, _resolve(s["$ref"], root), p)
        if "allOf" in s:
            for sub in s["allOf"]:
                walk(v, sub, p)
        if "anyOf" in s:
            if not any(not schema_errors(v, sub, root, p, 1) for sub in s["anyOf"]):
                errs.append(f"{p}: does not match any allowed shape")
        if "if" in s:  # draft 2020-12 conditional: then applies when if matches, else otherwise
            if not schema_errors(v, s["if"], root, p, 1):
                if "then" in s:
                    walk(v, s["then"], p)
            elif "else" in s:
                walk(v, s["else"], p)
        if "type" in s:
            types = s["type"] if isinstance(s["type"], list) else [s["type"]]
            if not any(_is_type(v, t) for t in types):
                errs.append(f"{p}: expected {'/'.join(types)}, got {type(v).__name__}")
                return
        if "const" in s and not _eq(v, s["const"]):
            errs.append(f"{p}: must be {s['const']!r}")
        if "enum" in s and not any(_eq(v, e) for e in s["enum"]):
            shown = s["enum"] if len(s["enum"]) <= 8 else s["enum"][:8] + ["..."]
            errs.append(f"{p}: {v!r} not in {shown}")
        if isinstance(v, str):
            if "minLength" in s and len(v) < s["minLength"]:
                errs.append(f"{p}: shorter than {s['minLength']} characters")
            if "maxLength" in s and len(v) > s["maxLength"]:
                errs.append(f"{p}: longer than {s['maxLength']} characters ({len(v)})")
            if "pattern" in s and not re.search(s["pattern"], v):
                errs.append(f"{p}: {v!r} does not match {s['pattern']}")
        if _is_type(v, "number"):
            if "minimum" in s and v < s["minimum"]:
                errs.append(f"{p}: {v} < minimum {s['minimum']}")
            if "maximum" in s and v > s["maximum"]:
                errs.append(f"{p}: {v} > maximum {s['maximum']}")
            if "exclusiveMinimum" in s and v <= s["exclusiveMinimum"]:
                errs.append(f"{p}: {v} must be > {s['exclusiveMinimum']}")
            if "exclusiveMaximum" in s and v >= s["exclusiveMaximum"]:
                errs.append(f"{p}: {v} must be < {s['exclusiveMaximum']}")
        if isinstance(v, list):
            if "minItems" in s and len(v) < s["minItems"]:
                errs.append(f"{p}: {len(v)} items, need at least {s['minItems']}")
            if "maxItems" in s and len(v) > s["maxItems"]:
                errs.append(f"{p}: {len(v)} items, at most {s['maxItems']} allowed")
            if s.get("uniqueItems"):
                keys = [json.dumps(x, sort_keys=True) for x in v]
                if len(keys) != len(set(keys)):
                    errs.append(f"{p}: items are not unique")
            if "items" in s:
                for i, x in enumerate(v):
                    walk(x, s["items"], f"{p}[{i}]")
        if isinstance(v, dict):
            for k in s.get("required", []):
                if k not in v:
                    errs.append(f"{p}: missing required key {k!r}")
            props = s.get("properties", {})
            for k, x in v.items():
                if k in props:
                    walk(x, props[k], f"{p}.{k}")
                elif "additionalProperties" in s:
                    ap = s["additionalProperties"]
                    if ap is False:
                        errs.append(f"{p}: unexpected key {k!r}")
                    elif isinstance(ap, dict):
                        walk(x, ap, f"{p}.{k}")
                if "propertyNames" in s:
                    walk(k, s["propertyNames"], f"{p}.<key {k!r}>")
            if "minProperties" in s and len(v) < s["minProperties"]:
                errs.append(f"{p}: {len(v)} keys, need at least {s['minProperties']}")
            if "maxProperties" in s and len(v) > s["maxProperties"]:
                errs.append(f"{p}: {len(v)} keys, at most {s['maxProperties']} allowed")

    walk(inst, schema, path)
    return errs


def validate_with_schema(inst, schema) -> list[str]:
    try:  # prefer the real library if it happens to be installed
        import jsonschema  # type: ignore

        v = jsonschema.Draft202012Validator(schema)
        return [f"$.{'.'.join(str(x) for x in e.absolute_path)}: {e.message}" for e in v.iter_errors(inst)][:50]
    except ImportError:
        return schema_errors(inst, schema)


# --------------------------------------------------------------------------------------------
# Report plumbing
# --------------------------------------------------------------------------------------------
class Report:
    def __init__(self, name: str):
        self.name = name
        self.state = "OK"
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []

    def error(self, msg: str):
        self.errors.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    def note(self, msg: str):
        self.info.append(msg)

    def final_state(self) -> str:
        if self.state in ("MISSING", "SKIPPED"):
            return self.state
        if self.errors:
            return "ERROR"
        if self.warnings:
            return "WARN"
        return "OK"


class Ctx:
    def __init__(self):
        self.data: dict[str, object] = {}
        self.reports: list[Report] = []
        self.schemas: dict[str, dict] = {}
        for p in sorted(SCHEMAS.glob("*.schema.json")) if SCHEMAS.exists() else []:
            try:
                self.schemas[p.name.replace(".schema.json", "")] = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass

    def load(self, rel: str) -> tuple[Report, object]:
        rep = Report(rel)
        self.reports.append(rep)
        path = PROCESSED / rel
        if not path.exists():
            rep.state = "MISSING"
            return rep, None
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            rep.error(f"cannot parse: {type(e).__name__}: {e}")
            return rep, None
        self.data[rel] = obj
        return rep, obj

    def ids(self, rel: str, key: str = "id") -> set[str]:
        obj = self.data.get(rel)
        if isinstance(obj, list):
            return {x.get(key) for x in obj if isinstance(x, dict)}
        return set()

    @property
    def source_ids(self) -> set[str] | None:
        return self.ids("sources.json") if "sources.json" in self.data else None

    def check_source(self, rep: Report, where: str, sid):
        ids = self.source_ids
        if ids is None:
            return
        if not sid:
            rep.error(f"{where}: missing source_id")
        elif sid not in ids:
            rep.error(f"{where}: source_id {sid!r} not in sources.json")

    def check_status(self, rep: Report, where: str, status, required: bool = True):
        if status is None and not required:
            return
        if status not in STATUSES:
            rep.error(f"{where}: status {status!r} not one of {STATUSES}")


def apply_schema(ctx: Ctx, rep: Report, name: str, obj) -> None:
    schema = ctx.schemas.get(name)
    if not schema:
        rep.warn(f"schema data/schemas/{name}.schema.json not found (run build_processed.py); shape checks limited")
        return
    for e in validate_with_schema(obj, schema):
        rep.error(e)


# --------------------------------------------------------------------------------------------
# File validators
# --------------------------------------------------------------------------------------------
def v_sources(ctx: Ctx):
    rep, obj = ctx.load("sources.json")
    if obj is None:
        if rep.state == "MISSING":
            rep.note("run data/build_sources.py")
        return
    apply_schema(ctx, rep, "sources", obj)
    ids = [r.get("id") for r in obj if isinstance(r, dict)]
    for i, n in collections.Counter(ids).items():
        if n > 1:
            rep.error(f"duplicate source id {i!r}")
    for r in obj:
        if isinstance(r, dict):
            url = str(r.get("url") or "")
            if not url.startswith(("http://", "https://")) and not (ROOT / url).exists():
                rep.warn(f"{r.get('id')}: url {url!r} is neither http(s) nor an existing repo path")
            if r.get("status") == "REAL" and not r.get("retrieved"):
                rep.error(f"{r.get('id')}: REAL source without a retrieved date")
    c = collections.Counter(r.get("status") for r in obj if isinstance(r, dict))
    rep.note(f"{len(obj)} sources {dict(c)}")


def v_traits(ctx: Ctx):
    rep, obj = ctx.load("traits.json")
    if obj is None:
        return
    apply_schema(ctx, rep, "traits", obj)
    ids = [t.get("id") for t in obj if isinstance(t, dict)]
    if ids != TRAIT_IDS:
        rep.error("trait ids/order differ from CONTRACTS section 4")
    for t in obj:
        if isinstance(t, dict):
            ctx.check_source(rep, f"trait {t.get('id')}", t.get("source_id"))
    rep.note(f"{len(obj)} traits")


def v_skills(ctx: Ctx):
    rep, obj = ctx.load("skills.json")
    if obj is None:
        return
    apply_schema(ctx, rep, "skills", obj)
    ids = [s.get("id") for s in obj if isinstance(s, dict)]
    for i, n in collections.Counter(ids).items():
        if n > 1:
            rep.error(f"duplicate skill id {i!r}")
    for s in obj:
        if isinstance(s, dict) and s.get("source_id"):
            ctx.check_source(rep, f"skill {s.get('id')}", s.get("source_id"))
    c = collections.Counter(s.get("source") for s in obj if isinstance(s, dict))
    rep.note(f"{len(obj)} skills {dict(c)}")


def v_careers(ctx: Ctx):
    rep, obj = ctx.load("careers.json")
    if obj is None:
        return
    apply_schema(ctx, rep, "careers", obj)
    skills = ctx.ids("skills.json")
    ids = [c.get("id") for c in obj if isinstance(c, dict)]
    if sorted(ids) != sorted(CAREER_IDS):
        rep.error(f"career ids {ids} differ from the 8 contract ids")
    seen_cw: dict[str, str] = {}
    filled = 0
    for c in obj:
        if not isinstance(c, dict):
            continue
        cid = c.get("id")
        if skills:
            bad = [s for s in c.get("skills", []) if s not in skills]
            if bad:
                rep.error(f"{cid}: skills not in skills.json: {bad}")
        for cw in c.get("coworkers") or []:
            if not isinstance(cw, dict):
                continue
            if cw.get("id") in seen_cw:
                rep.error(f"coworker id {cw.get('id')!r} used by {seen_cw[cw.get('id')]} and {cid}")
            seen_cw[cw.get("id")] = cid
            if cw.get("fictional") is not True:
                rep.warn(f"{cid}: coworker {cw.get('id')} not labeled fictional")
        for k in ("wage", "outlook"):
            v = c.get(k)
            if v is None:
                continue
            filled += 1
            if isinstance(v, dict):
                ctx.check_status(rep, f"{cid}.{k}", v.get("status"))
                ctx.check_source(rep, f"{cid}.{k}", v.get("source_id"))
    if filled == 0:
        rep.warn("wage/outlook are null for every career (filled by the wages build step)")
    rep.note(f"{len(obj)} careers, {len(seen_cw)} fictional coworkers, {filled} wage/outlook blocks filled")


def v_occupations(ctx: Ctx):
    rep, obj = ctx.load("occupations.json")
    if obj is None:
        return
    apply_schema(ctx, rep, "occupations", obj)
    if not isinstance(obj, dict):
        return
    prov = obj.get("provenance") or {}
    ctx.check_source(rep, "provenance", prov.get("source_id"))
    occs = obj.get("occupations") or []
    by_career = collections.Counter(o.get("career_id") for o in occs if isinstance(o, dict) and o.get("career_id"))
    for cid in CAREER_IDS:
        if by_career.get(cid) != 1:
            rep.error(f"career {cid} appears {by_career.get(cid, 0)} times (expected 1)")
    socs = [o.get("onet_soc") for o in occs if isinstance(o, dict)]
    for s, n in collections.Counter(socs).items():
        if n > 1:
            rep.error(f"duplicate onet_soc {s}")
    careers = ctx.data.get("careers.json")
    if isinstance(careers, list):
        ws = {o["career_id"]: o.get("work_styles") for o in occs if isinstance(o, dict) and o.get("career_id")}
        for c in careers:
            if isinstance(c, dict) and ws.get(c.get("id")) != c.get("work_styles"):
                rep.error(f"careers.json work_styles for {c.get('id')} differ from occupations.json")
    rep.note(f"{len(occs)} occupations ({sum(by_career.values())} careers + {len(occs) - sum(by_career.values())} related), "
             f"provenance {prov.get('status')}, universe N={obj.get('method', {}).get('universe_size')}")


def v_courses(ctx: Ctx):
    rep, obj = ctx.load("courses.json")
    if obj is None:
        return
    apply_schema(ctx, rep, "courses", obj)
    skills = ctx.ids("skills.json")
    ids = [c.get("id") for c in obj if isinstance(c, dict)]
    for i, n in collections.Counter(ids).items():
        if n > 1:
            rep.error(f"duplicate course id {i!r}")
    for c in obj:
        if not isinstance(c, dict):
            continue
        cid = c.get("id")
        if skills:
            bad = [s for s in c.get("skills", []) if s not in skills]
            if bad:
                rep.error(f"{cid}: skills not in skills.json: {bad}")
        st = c.get("status")
        ctx.check_status(rep, cid, st)
        ctx.check_status(rep, f"{cid}.hours_status", c.get("hours_status"), required=False)
        ctx.check_source(rep, cid, c.get("source_id"))
        if c.get("cost_source_id"):
            ctx.check_source(rep, f"{cid}.cost", c.get("cost_source_id"))
        if c.get("cost_usd") is None and st == "REAL":
            rep.error(f"{cid}: REAL listing with unknown cost")
        if st == "REAL" and not c.get("retrieved"):
            rep.error(f"{cid}: REAL listing without a retrieved date")
        if st == "REAL" and c.get("url") != c.get("verify_url"):
            rep.warn(f"{cid}: REAL listing whose url differs from verify_url")
    c1 = collections.Counter(c.get("status") for c in obj if isinstance(c, dict))
    c2 = collections.Counter(c.get("hours_status") for c in obj if isinstance(c, dict))
    free = sum(1 for c in obj if isinstance(c, dict) and c.get("cost_usd") == 0)
    rep.note(f"{len(obj)} resources status={dict(c1)} hours_status={dict(c2)} free={free}")


def v_jobs(ctx: Ctx):
    rep, obj = ctx.load("jobs.json")
    if obj is None:
        return
    apply_schema(ctx, rep, "jobs", obj)
    skills = ctx.ids("skills.json")
    ids = [j.get("id") for j in obj if isinstance(j, dict)]
    idset = set(ids)
    for i, n in collections.Counter(ids).items():
        if n > 1:
            rep.error(f"duplicate job id {i!r}")
    levels = collections.defaultdict(set)
    for j in obj:
        if not isinstance(j, dict):
            continue
        jid = j.get("id")
        levels[j.get("career_id")].add(j.get("level"))
        if skills:
            bad = [s for s in j.get("required_skills", []) if s not in skills]
            if bad:
                rep.error(f"{jid}: required_skills not in skills.json: {bad}")
        bad = [x for x in j.get("leads_to", []) if x not in idset]
        if bad:
            rep.error(f"{jid}: leads_to unknown jobs {bad}")
        ctx.check_status(rep, jid, j.get("status"), required=False)
        if j.get("source_id"):
            ctx.check_source(rep, jid, j.get("source_id"))
    for cid in CAREER_IDS:
        if levels.get(cid) != {"entry", "mid", "senior"}:
            rep.warn(f"{cid}: job levels {sorted(levels.get(cid, []))} (expected entry, mid, senior)")
    c = collections.Counter(j.get("career_id") for j in obj if isinstance(j, dict))
    rep.note(f"{len(obj)} job nodes across {len(c)} careers")


def v_programs(ctx: Ctx):
    rep, obj = ctx.load("programs.json")
    if obj is None:
        return
    items = obj.get("programs") if isinstance(obj, dict) else obj
    if not isinstance(items, list):
        rep.error("expected a list of programs (or {programs: [...]})")
        return
    ids = [p.get("id") for p in items if isinstance(p, dict)]
    for i, n in collections.Counter(ids).items():
        if n > 1:
            rep.error(f"duplicate program id {i!r}")
    routes = collections.defaultdict(set)
    for p in items:
        if not isinstance(p, dict):
            rep.error("program entry is not an object")
            continue
        pid = p.get("id")
        for k in ("id", "career_id", "route_type", "name", "provider", "credential", "url", "status", "source_id",
                  "steps"):
            if k not in p:
                rep.error(f"{pid}: missing {k!r}")
        if not isinstance(p.get("steps", []), list):
            rep.error(f"{pid}: steps must be a list")
            continue
        if p.get("career_id") not in CAREER_IDS:
            rep.error(f"{pid}: unknown career_id {p.get('career_id')!r}")
        if p.get("route_type") not in ROUTE_TYPES:
            rep.error(f"{pid}: unknown route_type {p.get('route_type')!r}")
        routes[p.get("career_id")].add(p.get("route_type"))
        ctx.check_status(rep, pid, p.get("status"))
        ctx.check_source(rep, pid, p.get("source_id"))
        steps = p.get("steps") or []
        step_ids = [s.get("id") for s in steps if isinstance(s, dict)]
        for i, n in collections.Counter(step_ids).items():
            if n > 1:
                rep.error(f"{pid}: duplicate step id {i!r}")
        known = set(step_ids)
        graph = {}
        for s in steps:
            if not isinstance(s, dict):
                rep.error(f"{pid}: step is not an object")
                continue
            sid = f"{pid}/{s.get('id')}"
            if not s.get("title"):
                rep.error(f"{sid}: missing title")
            if s.get("kind") not in ("course", "block", "job"):
                rep.error(f"{sid}: kind {s.get('kind')!r} not in course|block|job")
            for k in ("hours_per_week", "weeks", "cost_usd"):
                v = s.get(k)
                if v is None or not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
                    rep.error(f"{sid}: {k} must be a number >= 0 (got {v!r})")
            for k in ("units", "paid_wage_hourly"):  # optional per the contract
                v = s.get(k)
                if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0):
                    rep.error(f"{sid}: {k} must be a number >= 0 when present (got {v!r})")
            for k in ("prereqs", "sections"):
                if k not in s:
                    rep.warn(f"{sid}: no {k!r} list (contract lists it on every step; use [])")
                elif not isinstance(s[k], list):
                    rep.error(f"{sid}: {k} must be a list")
                    s = {**s, k: []}
            pre = s.get("prereqs") or []
            bad = [x for x in pre if x not in known]
            if bad:
                rep.error(f"{sid}: prereqs reference unknown steps {bad}")
            graph[s.get("id")] = [x for x in pre if x in known]
            for sec in s.get("sections") or []:
                if not isinstance(sec, dict):
                    continue
                days = sec.get("days") or []
                if any(d not in DAYS for d in days):
                    rep.error(f"{sid}: section {sec.get('id')} has bad days {days}")
                st, en = sec.get("start"), sec.get("end")
                if not (isinstance(st, str) and TIME_RE.match(st) and isinstance(en, str) and TIME_RE.match(en)):
                    rep.error(f"{sid}: section {sec.get('id')} start/end must be HH:MM")
                elif st >= en:
                    rep.error(f"{sid}: section {sec.get('id')} starts at or after it ends")
                if sec.get("modality") not in ("in_person", "online", "hybrid"):
                    rep.error(f"{sid}: section {sec.get('id')} modality {sec.get('modality')!r}")
        # prerequisite cycles
        state: dict = {}

        def dfs(n) -> bool:
            state[n] = 1
            for m in graph.get(n, []):
                if state.get(m) == 1 or (state.get(m) is None and dfs(m)):
                    return True
            state[n] = 2
            return False

        if any(state.get(n) is None and dfs(n) for n in graph):
            rep.error(f"{pid}: prerequisite cycle")
    for cid in CAREER_IDS:
        if not routes.get(cid):
            rep.warn(f"no programs for career {cid}")
    careers = ctx.data.get("careers.json")
    if isinstance(careers, list):
        for c in careers:
            if isinstance(c, dict):
                missing = [r for r in c.get("path_types", []) if r not in routes.get(c.get("id"), set())]
                if missing:
                    rep.warn(f"{c.get('id')}: careers.json path_types {missing} have no program")
    c = collections.Counter(p.get("status") for p in items if isinstance(p, dict))
    rep.note(f"{len(items)} programs status={dict(c)}")


def v_events(ctx: Ctx):
    rep, obj = ctx.load("events.json")
    if obj is None:
        return
    if not isinstance(obj, dict):
        rep.error("expected {schema_version: 1, status, events: [...]}")
        return
    if obj.get("schema_version") != 1:
        rep.error(f"schema_version is {obj.get('schema_version')!r}, expected 1")
    if not obj.get("status"):
        rep.error("missing top-level status")
    events = obj.get("events")
    if not isinstance(events, list):
        rep.error("events must be a list")
        return
    schema = ctx.schemas.get("event")
    if not schema:
        rep.warn("event.schema.json missing; run build_processed.py")
    cw_owner = {}
    careers = ctx.data.get("careers.json")
    if isinstance(careers, list):
        for c in careers:
            for cw in (c.get("coworkers") or []) if isinstance(c, dict) else []:
                cw_owner[cw.get("id")] = c.get("id")
    ids = []
    per_career = collections.Counter()
    crunch = 0
    for i, ev in enumerate(events):
        eid = ev.get("event_id", f"#{i}") if isinstance(ev, dict) else f"#{i}"
        ids.append(eid)
        if schema:
            for e in validate_with_schema(ev, schema)[:10]:
                rep.error(f"{eid}: {e}")
        if not isinstance(ev, dict):
            continue
        crunch += bool(ev.get("crunch"))
        for cid in ev.get("career_ids") or []:
            per_career[cid] += 1
        choices = ev.get("choices") or []
        cids = [ch.get("choice_id") for ch in choices if isinstance(ch, dict)]
        if len(cids) != len(set(cids)):
            rep.error(f"{eid}: duplicate choice_id")
        for ch in choices:
            for cw in (ch.get("coworker_hints") or {}) if isinstance(ch, dict) else {}:
                owner = cw_owner.get(cw)
                if owner and owner not in (ev.get("career_ids") or []):
                    rep.warn(f"{eid}: coworker {cw} belongs to {owner}, not to this event's careers")
    for i, n in collections.Counter(ids).items():
        if n > 1:
            rep.error(f"duplicate event_id {i!r}")
    for cid in CAREER_IDS:
        if per_career.get(cid, 0) < 3:
            rep.warn(f"only {per_career.get(cid, 0)} events for {cid} (contract: ~5)")
    if events and not crunch:
        rep.warn("no crunch events (contract: a few)")
    rep.note(f"{len(events)} events ({crunch} crunch); per career {dict(per_career)}")


def v_personas(ctx: Ctx):
    rep, raw = ctx.load("personas.json")
    if raw is None:
        return
    obj = raw["personas"] if isinstance(raw, dict) and isinstance(raw.get("personas"), list) else raw
    if isinstance(obj, list):
        recs = {p.get("id"): p for p in obj if isinstance(p, dict)}
    elif isinstance(obj, dict):  # keyed by persona id; non-object values are file metadata, not personas
        recs = {k: v for k, v in obj.items() if isinstance(v, dict)}
    else:
        rep.error("expected a list of personas or an object keyed by persona id")
        return
    missing = [p for p in PERSONA_IDS if p not in recs]
    if missing:
        rep.error(f"missing personas {missing}")
    unlabeled = [k for k, r in recs.items() if r.get("fictional") is not True]
    if unlabeled and not (isinstance(raw, dict) and raw.get("fictional") is True):
        rep.warn(f'personas are fictional but not labeled ("fictional": true): {unlabeled}')
    check_refs(ctx, rep, raw)
    rep.note(f"{len(recs)} personas")


# Keys whose values must be ids from another processed file (checked wherever they appear in files with
# open-ended shapes: personas and synthetic/*). Unknown ids are warnings: those shapes are not fixed by
# the contract, but a dangling id breaks graph edges, recommendations, or the planner.
REF_KEYS = {
    "skills.json": {"skill_id", "skill_ids", "skills", "demonstrated_skills", "required_skills", "target_skills",
                    "missing_skills", "skill_gaps"},
    "careers.json": {"career_id", "career_ids", "target_career", "target_career_id", "target_careers", "interests_careers"},
    "courses.json": {"course_id", "course_ids", "completed_courses", "courses_completed", "enrolled_courses"},
    "jobs.json": {"job_id", "job_ids", "target_job", "target_jobs"},
}


def check_refs(ctx: Ctx, rep: Report, obj, path: str = "$", budget: list | None = None) -> None:
    budget = budget if budget is not None else [0]
    vocab = {f: ctx.ids(f) for f in REF_KEYS}
    if "careers.json" not in ctx.data:
        vocab["careers.json"] = set(CAREER_IDS)

    def ids_in(v):
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            out = []
            for x in v:
                if isinstance(x, str):
                    out.append(x)
                elif isinstance(x, dict) and isinstance(x.get("id"), str):  # e.g. [{"id": "python", "level": 3}]
                    out.append(x["id"])
            return out
        if isinstance(v, dict) and all(isinstance(x, (int, float, str, bool)) or x is None for x in v.values()):
            return list(v.keys())  # scalar map such as {"python": 0.8}; nested dicts are walked instead
        return []

    def walk(v, p):
        if isinstance(v, dict):
            for k, x in v.items():
                for f, keys in REF_KEYS.items():
                    if k in keys and vocab[f]:
                        bad = sorted({i for i in ids_in(x) if i not in vocab[f]})
                        if bad:
                            budget[0] += 1
                            if budget[0] <= 20:
                                rep.warn(f"{p}.{k}: ids not in {f}: {bad[:6]}{' ...' if len(bad) > 6 else ''}")
                walk(x, f"{p}.{k}")
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, f"{p}[{i}]")

    walk(obj, path)
    if budget[0] > 20:
        rep.warn(f"... {budget[0] - 20} more dangling-id findings")


def v_synthetic(ctx: Ctx, rel: str):
    rep, obj = ctx.load(rel)
    if obj is None:
        return
    if isinstance(obj, dict):
        if obj.get("fictional") is not True:
            rep.error('top-level "fictional": true is missing')
        records = next((v for v in obj.values() if isinstance(v, list)), [])
    elif isinstance(obj, list):
        records = obj
        unlabeled = sum(1 for r in obj if not (isinstance(r, dict) and r.get("fictional") is True))
        if unlabeled:
            rep.error(f'{unlabeled} records without "fictional": true')
    else:
        rep.error("unexpected JSON shape")
        return
    ids = [r.get("id") for r in records if isinstance(r, dict) and r.get("id") is not None]
    for i, n in collections.Counter(ids).items():
        if n > 1:
            rep.error(f"duplicate record id {i!r}")
    check_refs(ctx, rep, obj)
    rep.note(f"{len(records)} records")


def v_producer_sources(ctx: Ctx):
    folder = PROCESSED / "sources"
    for path in sorted(folder.glob("*.json")) if folder.exists() else []:
        rel = f"sources/{path.name}"
        rep, obj = ctx.load(rel)
        if obj is None:
            continue
        items = obj.get("sources") if isinstance(obj, dict) else obj
        apply_schema(ctx, rep, "sources", items)
        merged = ctx.source_ids
        if merged is not None:
            missing = [r.get("id") for r in items or [] if isinstance(r, dict) and r.get("id") not in merged]
            if missing:
                rep.warn(f"not yet merged into sources.json (run build_sources.py): {missing}")
        rep.note(f"{len(items or [])} records")


def v_schema_consistency(ctx: Ctx):
    rep = Report("schemas/event.schema.json")
    ctx.reports.append(rep)
    schema = ctx.schemas.get("event")
    if not schema:
        rep.state = "MISSING"
        return
    try:
        ch = schema["$defs"]["choice"]["properties"]
        traits = ch["trait_deltas"]["propertyNames"]["enum"]
        cws = ch["coworker_hints"]["propertyNames"]["enum"]
    except (KeyError, TypeError):
        rep.error("unexpected event schema layout")
        return
    t = ctx.data.get("traits.json")
    if isinstance(t, list) and traits != [x.get("id") for x in t]:
        rep.error("trait enum differs from traits.json (re-run build_processed.py)")
    c = ctx.data.get("careers.json")
    if isinstance(c, list):
        ids = [cw.get("id") for x in c for cw in (x.get("coworkers") or [])]
        if sorted(cws) != sorted(ids):
            rep.error("coworker enum differs from careers.json (re-run build_processed.py)")
    rep.note(f"{len(traits)} trait ids, {len(cws)} coworker ids enumerated")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="Validate data/processed/*.json")
    ap.add_argument("-v", "--verbose", action="store_true", help="print every message")
    ap.add_argument("--dir", help="validate this folder instead of data/processed (e.g. a staging copy)")
    args = ap.parse_args()
    global PROCESSED
    if args.dir:
        PROCESSED = Path(args.dir).resolve()

    ctx = Ctx()
    v_sources(ctx)
    v_traits(ctx)
    v_skills(ctx)
    v_careers(ctx)
    v_occupations(ctx)
    v_courses(ctx)
    v_jobs(ctx)
    v_programs(ctx)
    v_events(ctx)
    v_personas(ctx)
    for rel in EXPECTED:
        if rel.startswith("synthetic/"):
            v_synthetic(ctx, rel)
    v_producer_sources(ctx)
    v_schema_consistency(ctx)

    known = set(EXPECTED) | {r.name for r in ctx.reports}
    for path in sorted(PROCESSED.rglob("*.json")) if PROCESSED.exists() else []:
        rel = path.relative_to(PROCESSED).as_posix()
        if rel not in known and not rel.endswith(".tmp"):
            rep = Report(rel)
            ctx.reports.append(rep)
            try:
                json.loads(path.read_text(encoding="utf-8"))
                rep.note("parsed OK (no validator for this file)")
            except (OSError, json.JSONDecodeError) as e:
                rep.error(f"cannot parse: {e}")

    width = max(len(r.name) for r in ctx.reports) + 2
    try:
        shown_dir = PROCESSED.relative_to(ROOT).as_posix()
    except ValueError:
        shown_dir = str(PROCESSED)
    print(f"Foothold data validation ({shown_dir})")
    print(f"{'file'.ljust(width)}{'state':8}details")
    errors = 0
    for r in ctx.reports:
        state = r.final_state()
        errors += state == "ERROR"
        detail = "; ".join(r.info) if r.info else ("not present yet" if state == "MISSING" else "")
        extra = []
        if r.errors:
            extra.append(f"{len(r.errors)} error(s)")
        if r.warnings:
            extra.append(f"{len(r.warnings)} warning(s)")
        print(f"{r.name.ljust(width)}{state:8}{detail}{(' [' + ', '.join(extra) + ']') if extra else ''}")
        shown = (r.errors + r.warnings) if args.verbose else (r.errors[:5] + r.warnings[:3])
        for m in shown:
            print(f"{'':{width}}  - {m}")
        hidden = len(r.errors) + len(r.warnings) - len(shown)
        if hidden > 0:
            print(f"{'':{width}}  ... {hidden} more (use -v)")
    missing = [r.name for r in ctx.reports if r.final_state() == "MISSING"]
    print(f"\n{errors} file(s) with errors; missing (not fatal): {', '.join(missing) if missing else 'none'}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
