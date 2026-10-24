"""Pathway planning agent (brief 5.2 / 6.4; CONTRACTS sections 6, 9).

    gather_constraints -> retrieve_programs (TF-IDF) -> translate_rules (LLM, regex mock)
      -> confirm_rules (interrupt: learner confirms / edits the rule chips)
      -> solve (CP-SAT + greedy, foothold.planner) -> verify (plan re-check + claim verifier)
      -> propose (LLM prose; numbers only via verified placeholders)
      -> approval (interrupt) --approve--> finalize (kanban + progress_log) -> END
                              --reject---> learn_from_rejection (reason -> rule) -> solve (loop, max 4 rounds)

Resume values: ``confirm_rules`` takes ``{"rules": [...]}`` (edited chips) or anything else to keep
the proposal; ``approval`` takes ``{"approve": bool, "reason": str | None}``.
Learner free text is untrusted: it is wrapped before it reaches the LLM and never logged.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel

from .. import data, db, llm, planner, safety, verifier
from ..sse import trace_node
from ..trace import note

log = logging.getLogger("foothold.pathway")

GRAPH_NAME = "pathway"
MAX_ROUNDS = 4
SOLVE_TIME_LIMIT_S = 0.8


class PathState(TypedDict, total=False):
    learner_id: str
    persona_id: str
    career_id: str
    inputs: dict[str, Any]
    text: str
    proposed_rules: list[dict[str, Any]]
    rules: list[dict[str, Any]]
    retrieved: list[dict[str, Any]]
    result: dict[str, Any] | None
    verification: dict[str, Any] | None
    proposal: dict[str, Any] | None
    rejections: list[dict[str, Any]]
    round: int
    approved: bool
    kanban: list[dict[str, Any]] | None
    translate_source: str | None
    origin: dict[str, Any] | None


# ---------------------------------------------------------------------------
# Rule translation (shared with POST /api/path/translate)
# ---------------------------------------------------------------------------

RuleType = Literal[
    "no_class_before", "no_class_after", "day_off", "online_only", "in_person_only", "max_hours_per_week",
    "max_budget", "max_cost_per_term", "max_campus_days", "max_courses_per_term", "no_summer", "earliest_start",
    "max_months", "avoid_route",
]


class RuleOut(BaseModel):
    type: RuleType
    day: str | None
    time: str | None
    number: float | None
    season: str | None
    route_type: str | None


class RulesOut(BaseModel):
    rules: list[RuleOut]


TRANSLATE_SYSTEM = (
    "You convert a learner's scheduling and money constraints into planner rules. Use only these rule types: "
    + ", ".join(planner.RULE_TYPES)
    + ". Fields: day (Mon..Sun) for day_off; time (HH:MM 24h) for no_class_before/no_class_after; number for "
    "max_* rules (hours, USD, days, classes, months) and the year of earliest_start; season (spring|summer|fall) for "
    "earliest_start; route_type (cc_transfer|certificate|apprenticeship|direct_to_work) for avoid_route. Set unused "
    "fields to null. Only output rules the text clearly states; output an empty list if none. " + safety.UNTRUSTED_NOTE
)

_DAYS_RE = r"\b(mon(?!th)|tue|tues|wed(?!d)|thu|thur|thurs|fri|sat(?!is)|sun(?!n|s|r))[a-z]*"
_TIME_RE = r"(\d{1,2}(?::\d{2})?\s*(?:[ap]\.?m\.?)?|noon)"
_ROUTE_WORDS = {
    "apprentice": "apprenticeship", "transfer": "cc_transfer", "community college": "cc_transfer",
    "certificate": "certificate", "cert ": "certificate", "straight to work": "direct_to_work", "job right away": "direct_to_work",
}


def _t(raw: str) -> str:
    raw = raw.strip().lower()
    if raw == "noon":
        return "12:00"
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*([ap])?", raw)
    if not m:
        return raw
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ap == "p" and h < 12:
        h += 12
    elif ap == "a" and h == 12:
        h = 0
    elif ap is None and 1 <= h <= 6:  # "after 5" means 5 pm in a class-schedule context
        h += 12
    return f"{h:02d}:{mi:02d}"


def regex_rules(text: str) -> list[dict[str, Any]]:
    """Deterministic translator (LLM mock / offline mode)."""
    s = " " + (text or "").lower().replace("’", "'") + " "
    out: list[dict[str, Any]] = []
    for m in re.finditer(r"(?:no|not|can't|cannot|never)\s+(?:class(?:es)?\s+)?(?:before|until)\s+" + _TIME_RE, s):
        out.append({"type": "no_class_before", "time": _t(m.group(1))})
    for m in re.finditer(r"(?:after|from)\s+" + _TIME_RE + r"\s+(?:only|on|onward)", s):
        out.append({"type": "no_class_before", "time": _t(m.group(1))})
    if re.search(r"evenings? only|only (?:at night|evenings?)|after work|work (?:during the day|days|9 ?- ?5)", s):
        out.append({"type": "no_class_before", "time": "17:00"})
    for m in re.finditer(r"(?:no|not|can't|cannot)\s+(?:class(?:es)?\s+)?after\s+" + _TIME_RE, s):
        out.append({"type": "no_class_after", "time": _t(m.group(1))})
    for m in re.finditer(r"(?:done|finished|home)\s+by\s+" + _TIME_RE, s):
        out.append({"type": "no_class_after", "time": _t(m.group(1))})
    if re.search(r"mornings? only|only mornings?", s):
        out.append({"type": "no_class_after", "time": "12:00"})
    for m in re.finditer(r"(?:no|off|free|busy|can't do|cannot do|work|not on|never on|except)\s+(?:on\s+)?((?:" + _DAYS_RE
                         + r"(?:\s*(?:,|and|&|or)\s*)?)+)", s):
        for d in re.findall(_DAYS_RE, m.group(1)):
            out.append({"type": "day_off", "day": d})
    for m in re.finditer(r"((?:\b" + _DAYS_RE + r"(?:\s*(?:,|and|&|or)\s*)?)+)\s+(?:are\s+|is\s+)?(?:off|out|busy|no good|don't work)", s):
        for d in re.findall(_DAYS_RE, m.group(1)):
            out.append({"type": "day_off", "day": d})
    if re.search(r"\bweekends?\b", s) and re.search(r"(?:no|not|work|busy|off)\s+(?:on\s+)?(?:the\s+)?weekends?", s):
        out += [{"type": "day_off", "day": "Sat"}, {"type": "day_off", "day": "Sun"}]
    if re.search(r"online only|only online|fully online|all online|no (?:in[- ]person|campus)", s):
        out.append({"type": "online_only"})
    elif re.search(r"in[- ]person only|only in[- ]person|no online", s):
        out.append({"type": "in_person_only"})
    for m in re.finditer(r"(\d{1,2})\s*(?:hours|hrs|h)\s*(?:a|per|/|each)?\s*week", s):
        out.append({"type": "max_hours_per_week", "number": float(m.group(1))})
    for m in re.finditer(r"\$\s?(\d[\d,]*)\s*(?:k\b)?\s*(?:a|per|each)\s+(?:term|semester)", s):
        out.append({"type": "max_cost_per_term", "number": float(m.group(1).replace(",", ""))})
    for m in re.finditer(r"(?:budget|spend|afford|up to|max(?:imum)?|only have|under)\D{0,12}\$\s?(\d[\d,]*)(\s*k\b)?(?!\s*(?:a|per|each)\s+(?:term|semester))", s):
        n = float(m.group(1).replace(",", "")) * (1000 if m.group(2) else 1)
        out.append({"type": "max_budget", "number": n})
    for m in re.finditer(r"(\d)\s*days?\s*(?:a week\s*)?(?:on campus|in person|at school)", s):
        out.append({"type": "max_campus_days", "number": int(m.group(1))})
    for m in re.finditer(r"(\d)\s*(?:classes|courses)\s*(?:a|per|each)\s*(?:term|semester)", s):
        out.append({"type": "max_courses_per_term", "number": int(m.group(1))})
    if re.search(r"no summer|not (?:in )?(?:the )?summer|summers? off", s):
        out.append({"type": "no_summer"})
    m = re.search(r"(?:start|begin)\w*\s+(?:in\s+|next\s+)?(spring|summer|fall)(?:\s+(20\d\d))?", s)
    if m:
        out.append({"type": "earliest_start", "season": m.group(1), "number": int(m.group(2)) if m.group(2) else None})
    for m in re.finditer(r"(?:within|in under|in less than|under|max(?:imum)?(?: of)?)\s+(\d{1,3})\s*(months?|years?)", s):
        n = int(m.group(1)) * (12 if m.group(2).startswith("year") else 1)
        out.append({"type": "max_months", "number": n})
    for word, rt in _ROUTE_WORDS.items():
        if re.search(r"(?:no|not|don't want|skip|avoid)\s+(?:an?\s+|the\s+)?" + re.escape(word.strip()), s):
            out.append({"type": "avoid_route", "route_type": rt})
    return planner.dedupe_rules(out)


def _labelled(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**r, "label": planner.describe_rule(r)} for r in rules]


def translate_text(text: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """(validated rules, llm meta). The regex translator is the mock; LLM rules are validated + deduped."""
    text = (text or "").strip()[:1200]
    if not text:
        return [], {"source": "mock", "model": None, "ms": 0}
    user = safety.wrap_untrusted(text, "constraints", 1200)
    obj, meta = llm.structured("path_translate", TRANSLATE_SYSTEM, user, RulesOut,
                               mock=lambda: {"rules": [_full(r) for r in regex_rules(text)]})
    rules = planner.dedupe_rules([r.model_dump() for r in obj.rules])
    if not rules and meta.get("source") != "mock":
        rules = regex_rules(text)  # the model saw nothing; keep the deterministic reading
    return rules, dict(meta)


def _full(rule: dict[str, Any]) -> dict[str, Any]:
    return {k: rule.get(k) for k in ("type", "day", "time", "number", "season", "route_type")}


# ---------------------------------------------------------------------------
# Retrieval (TF-IDF over programs.json)
# ---------------------------------------------------------------------------


def _doc(p: dict[str, Any]) -> str:
    steps = " ".join(str(s.get("title") or "") for s in p.get("steps") or [] if isinstance(s, dict))
    return " ".join(str(p.get(k) or "") for k in ("name", "credential", "provider", "route_type")) + " " + steps


def retrieve(career_id: str, query: str, k: int = 12) -> list[dict[str, Any]]:
    progs = [p for p in data.programs() if isinstance(p, dict) and p.get("id")]
    if not progs:
        return []
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    docs = [_doc(p) for p in progs]
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
    mat = vec.fit_transform(docs + [query or career_id])
    sims = cosine_similarity(mat[-1], mat[:-1]).ravel()
    rows = []
    for p, sc in zip(progs, sims):
        boost = 1.0 if p.get("career_id") == career_id else 0.0
        rows.append({"program_id": p["id"], "career_id": p.get("career_id"), "route_type": p.get("route_type"),
                     "name": p.get("name"), "score": round(float(sc) + boost, 4), "tfidf": round(float(sc), 4)})
    rows.sort(key=lambda r: -r["score"])
    return [r for r in rows if r["career_id"] == career_id][:k]


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

DEFAULT_INPUTS = {"current_credits": 0, "hours_per_week": 12, "budget_usd": 2000, "commute_minutes": 20, "dependents": 0}


def persona_defaults(persona_id: str | None) -> dict[str, Any]:
    p = data.get_persona(persona_id) if persona_id else None
    if not isinstance(p, dict) and persona_id and persona_id.startswith("u_"):
        try:  # self-registered learner: their saved profile
            from foothold import auth, profiles

            acct = auth.get_account_by_persona(persona_id)
            p = profiles.get_profile(acct) if acct else None
        except Exception:  # noqa: BLE001
            p = None
    if not isinstance(p, dict):
        return {}
    src = p.get("constraints") if isinstance(p.get("constraints"), dict) else p
    out = {}
    for k in DEFAULT_INPUTS:
        v = src.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = v
    return out


def gather_constraints(state: PathState) -> dict[str, Any]:
    inputs = {**DEFAULT_INPUTS, **persona_defaults(state.get("persona_id")), **(state.get("inputs") or {})}
    inputs = {k: inputs[k] for k in DEFAULT_INPUTS}
    note(summary=f"{inputs['hours_per_week']:g} h/week · budget ${inputs['budget_usd']:,.0f}")
    return {"inputs": inputs, "round": 0, "rejections": [], "approved": False}


def retrieve_programs(state: PathState) -> dict[str, Any]:
    cid = state["career_id"]
    career = data.get_career(cid) or {}
    query = " ".join([str(career.get("title") or cid), str(career.get("summary") or ""), state.get("text") or ""])
    rows = retrieve(cid, query)
    note(summary=f"{len(rows)} programs ranked (TF-IDF)" if rows else "no program data for this career yet")
    return {"retrieved": rows}


async def translate_rules(state: PathState) -> dict[str, Any]:
    rules, meta = await asyncio.to_thread(translate_text, state.get("text") or "")
    base = planner.dedupe_rules(list(state.get("rules") or []) + rules)
    note(summary=f"{len(rules)} rule(s) from your words", llm=meta.get("source"))
    return {"proposed_rules": base, "translate_source": meta.get("source")}


def confirm_rules(state: PathState) -> dict[str, Any]:
    proposed = state.get("proposed_rules") or []
    if not (state.get("text") or "").strip():
        return {"rules": proposed}
    answer = interrupt({"kind": "confirm_rules", "text_received": True, "proposed": _labelled(proposed),
                        "rule_types": list(planner.RULE_TYPES)})
    if isinstance(answer, dict) and isinstance(answer.get("rules"), list):
        rules = planner.dedupe_rules(answer["rules"])
    else:
        rules = proposed
    return {"rules": rules}


def _constraints(state: PathState) -> planner.Constraints:
    inp = state.get("inputs") or DEFAULT_INPUTS
    return planner.make_constraints(rules=state.get("rules") or [], **inp)


def _solve_sync(state: PathState, rules: list[dict[str, Any]]) -> dict[str, Any]:
    inp = state.get("inputs") or DEFAULT_INPUTS
    c = planner.make_constraints(rules=rules, **inp)
    ids = [r["program_id"] for r in state.get("retrieved") or []] or None
    return planner.solve_routes(state["career_id"], c, program_ids=ids, time_limit_s=SOLVE_TIME_LIMIT_S,
                                origin=state.get("origin"))


def _any_feasible(res: dict[str, Any]) -> bool:
    return any(r.get("feasible") for r in (res.get("routes") or {}).values())


async def solve(state: PathState) -> dict[str, Any]:
    rules = list(state.get("rules") or [])
    res = await asyncio.to_thread(_solve_sync, state, rules)
    rejections = list(state.get("rejections") or [])
    relaxed: list[str] = []
    last = rejections[-1] if rejections else None
    if not _any_feasible(res) and last and last.get("added_rules") and not last.get("relaxed"):
        # the learner's feedback made every route infeasible: drop just those new rules and say so
        added = {planner.rule_key(r) for r in last["added_rules"]}
        rules2 = [r for r in rules if planner.rule_key(r) not in added]
        res2 = await asyncio.to_thread(_solve_sync, state, rules2)
        if _any_feasible(res2):
            relaxed = [r.get("label") or planner.describe_rule(r) for r in last["added_rules"]]
            res, rules = res2, rules2
            rejections[-1] = {**last, "relaxed": True}
    res = {**res, "relaxed_rules": relaxed}
    feas = [rt for rt, r in res["routes"].items() if r.get("feasible")]
    msg = f"{len(feas)}/{len(res['routes'])} routes feasible · {res['solve_ms']} ms"
    note(summary=msg + (f" · relaxed {len(relaxed)} rule(s)" if relaxed else ""))
    return {"result": res, "rules": rules, "rejections": rejections, "round": int(state.get("round") or 0) + 1}


def verify(state: PathState) -> dict[str, Any]:
    res = state.get("result") or {}
    plan_checks = {"passed": 0, "failed": 0}
    claims = []
    for rt, r in (res.get("routes") or {}).items():
        if not r.get("feasible"):
            continue
        if r.get("verified"):
            plan_checks["passed"] += 1
        else:
            plan_checks["failed"] += 1
        w = r.get("expected_wage") or {}
        if isinstance(w.get("median_annual"), (int, float)):
            claims.append({"kind": "wage", "value": w["median_annual"], "unit": "usd_per_year", "entity_id": res["career_id"],
                           "source_id": w.get("source_id"), "field": "median_annual"})
    out = verifier.verify_claims(claims)
    v = {"plans": plan_checks, "claims": out["counts"]}
    note(summary=f"{plan_checks['passed']} plan(s) re-checked · {out['counts']['verified']} claim(s) verified")
    return {"verification": v}


class ProposalText(BaseModel):
    template: str


PROPOSE_SYSTEM = (
    "Write 2 short, warm sentences recommending a study plan to a learner. You MUST NOT write any digits; refer to "
    "numbers only with the placeholders described in the input (write them in curly braces, e.g. {months}); each "
    "placeholder already includes its unit. Plain words, no hype, no promises about jobs."
)


def _proposal_values(res: dict[str, Any]) -> dict[str, str] | None:
    best = res.get("best_route")
    if not best:
        return None
    r = res["routes"][best]
    g = r.get("greedy") or {}
    if g.get("feasible") and r.get("months") is not None:
        diff = int(g["months"]) - int(r["months"])
        greedy_note = (f"{diff} month{'s' if diff != 1 else ''} sooner than a first-fit schedule" if diff > 0
                       else "as fast as a first-fit schedule")
    else:
        greedy_note = "a first-fit schedule could not fit your rules"
    months = int(r.get("months") or 0)
    return {"route": str(r.get("label") or best).lower(), "months": f"{months} month{'s' if months != 1 else ''}",
            "cost": f"${r.get('cost_usd', 0):,.0f}", "hours": f"{r.get('peak_hours_per_week', 0):g} hours a week",
            "start": str(r.get("start_term") or res.get("start_term")), "greedy_note": greedy_note}


PLACEHOLDER_MEANING = {
    "route": "name of the recommended route, e.g. 'certificate'",
    "months": "total length with unit, e.g. '18 months'",
    "cost": "total listed program cost in dollars, e.g. '$1,320'",
    "hours": "peak weekly load with unit, e.g. '12 hours a week'",
    "start": "first term, e.g. 'Spring 2027'",
    "greedy_note": "a clause comparing with a first-fit schedule, e.g. '3 months sooner than a first-fit schedule'",
}


def _mock_template() -> dict[str, str]:
    return {"template": "The {route} route fits your rules: about {months} starting {start}, around {cost} in "
                        "listed costs, and at most {hours}. That is {greedy_note}."}


async def propose(state: PathState) -> dict[str, Any]:
    res = state.get("result") or {}
    vals = _proposal_values(res)
    if vals is None:
        reasons = sorted({str(r.get("reason")) for r in (res.get("routes") or {}).values() if r.get("reason")})
        prop = {"best_route": None, "text": "No route fits every rule yet. Try loosening one rule.", "reasons": reasons,
                "source": "logic"}
        note(summary="no feasible route")
        return {"proposal": prop}
    obj, meta = await llm.astructured("path_propose", PROPOSE_SYSTEM, json.dumps({"placeholders": PLACEHOLDER_MEANING, "recommended_route": vals["route"]}, sort_keys=True), ProposalText, mock=_mock_template)
    template, source = obj.template, meta["source"]
    if verifier.placeholder_problems(template, vals.keys()):
        template, source = _mock_template()["template"], "mock"
    text = verifier.fill_template(template, vals)
    if verifier.unbacked_numbers(text, list(vals.values())):
        text, source = verifier.fill_template(_mock_template()["template"], vals), "mock"
    relaxed = res.get("relaxed_rules") or []
    if relaxed:
        text = ("No route could meet " + "; ".join(f"'{x}'" for x in relaxed) + ", so I kept your other rules and "
                "found the closest plan. " + text)
    prop = {"best_route": res["best_route"], "text": text, "values": vals, "source": source, "relaxed_rules": relaxed}
    note(summary=f"recommend {res['best_route']}")
    return {"proposal": prop}


def approval(state: PathState) -> dict[str, Any]:
    res = state.get("result") or {}
    payload = {
        "kind": "approve_plan", "round": state.get("round"), "proposal": state.get("proposal"),
        "best_route": res.get("best_route"), "rules": _labelled(state.get("rules") or []),
        "can_retry": int(state.get("round") or 0) < MAX_ROUNDS,
    }
    answer = interrupt(payload)
    if isinstance(answer, dict) and answer.get("approve"):
        return {"approved": True}
    reason = str((answer or {}).get("reason") or "").strip()[:500] if isinstance(answer, dict) else ""
    return {"approved": False, "rejections": list(state.get("rejections") or []) + [{"round": state.get("round"), "reason": reason}]}


def rejection_rules(reason: str, res: dict[str, Any], llm_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn a rejection into tighter rules: explicit rules from the text, plus relative ones ("too long")."""
    s = (reason or "").lower()
    best = res.get("best_route")
    r = (res.get("routes") or {}).get(best) or {}
    out = list(llm_rules)
    if r.get("feasible"):
        if re.search(r"too long|faster|sooner|quicker|takes forever", s) and r.get("months"):
            out.append({"type": "max_months", "number": max(1, int(r["months"]) - 1)})
        if re.search(r"too expensive|cheaper|costs? too much|can't afford|less money", s) and r.get("cost_usd") is not None:
            out.append({"type": "max_budget", "number": max(0, float(r["cost_usd"]) - 1)})
        if re.search(r"too many hours|too much time|too busy|fewer hours|less time", s) and r.get("peak_hours_per_week"):
            out.append({"type": "max_hours_per_week", "number": max(1, float(r["peak_hours_per_week"]) - 1)})
        if re.search(r"(?:don't|do not|not) (?:like|want) (?:this|that) (?:route|path|option)|different route|something else", s):
            out.append({"type": "avoid_route", "route_type": best})
    if not out and best and r.get("feasible") and not s:
        out.append({"type": "avoid_route", "route_type": best})
    return planner.dedupe_rules(out)


async def learn_from_rejection(state: PathState) -> dict[str, Any]:
    reason = ((state.get("rejections") or [{}])[-1] or {}).get("reason") or ""
    llm_rules, meta = await asyncio.to_thread(translate_text, reason)
    new = rejection_rules(reason, state.get("result") or {}, llm_rules)
    rules = planner.dedupe_rules(list(state.get("rules") or []) + new)
    added = [planner.describe_rule(r) for r in new]
    note(summary=("added: " + "; ".join(added)) if added else "no new rule found; re-solving", llm=meta.get("source"))
    rej = list(state.get("rejections") or [])
    if rej:
        rej[-1] = {**rej[-1], "added_rules": _labelled(new)}
    return {"rules": rules, "rejections": rej}


def kanban_items(res: dict[str, Any], route: str) -> list[dict[str, Any]]:
    r = (res.get("routes") or {}).get(route) or {}
    prog = (r.get("program") or {}).get("id")
    items = []
    for term in r.get("terms") or []:
        for st in term.get("steps") or []:
            items.append({
                "id": f"{prog}:{st.get('step')}", "title": st.get("title"), "column": "todo", "term": term.get("term"),
                "kind": st.get("kind"), "program_id": prog, "route_type": route, "section": st.get("section"),
                "days": st.get("days") or [], "start": st.get("start"), "end": st.get("end"), "modality": st.get("modality"),
            })
    return items


def merge_kanban(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prev = {i.get("id"): i for i in old if isinstance(i, dict)}
    out = [{**n, "column": (prev.get(n["id"]) or {}).get("column", n["column"])} for n in new]
    keep = [i for i in old if isinstance(i, dict) and i.get("custom") and i.get("id") not in {n["id"] for n in new}]
    return out + keep


def load_kanban(persona_id: str) -> list[dict[str, Any]]:
    row = db.query_one("SELECT items_json FROM kanban WHERE learner_id = ?", (persona_id,))
    items = db.jloads(row["items_json"], []) if row else []
    return items if isinstance(items, list) else []


def save_kanban(persona_id: str, items: list[dict[str, Any]]) -> None:
    db.upsert("kanban", {"learner_id": persona_id, "items_json": items, "updated_at": db.now_iso()}, key="learner_id")


async def finalize(state: PathState) -> dict[str, Any]:
    res = state.get("result") or {}
    best = res.get("best_route")
    items: list[dict[str, Any]] | None = None
    pid = state.get("persona_id")
    if best and pid:
        def _write() -> list[dict[str, Any]]:
            merged = merge_kanban(load_kanban(pid), kanban_items(res, best))
            save_kanban(pid, merged)
            r = res["routes"][best]
            db.insert("progress_log", {"learner_id": pid, "kind": "path_plan", "payload_json": {
                "career_id": res.get("career_id"), "route_type": best, "program_id": (r.get("program") or {}).get("id"),
                "months": r.get("months"), "cost_usd": r.get("cost_usd"), "rules": state.get("rules") or [],
                "approved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}})
            return merged

        try:
            items = await asyncio.to_thread(_write)
        except Exception as exc:
            log.warning("kanban/progress not saved (%s)", type(exc).__name__)
    note(summary=f"plan saved · {len(items or [])} kanban cards" if items is not None else "plan approved")
    return {"kanban": items}


def route_after_approval(state: PathState) -> str:
    if state.get("approved"):
        return "finalize"
    if int(state.get("round") or 0) >= MAX_ROUNDS:
        return END
    return "learn_from_rejection"


def route_after_propose(state: PathState) -> str:
    return "approval"


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


def build_graph(checkpointer: Any) -> Any:
    b = StateGraph(PathState)
    for name, fn in (("gather_constraints", gather_constraints), ("retrieve_programs", retrieve_programs),
                     ("translate_rules", translate_rules), ("confirm_rules", confirm_rules), ("solve", solve),
                     ("verify", verify), ("propose", propose), ("approval", approval),
                     ("learn_from_rejection", learn_from_rejection), ("finalize", finalize)):
        b.add_node(name, fn)
    b.add_edge(START, "gather_constraints")
    b.add_edge("gather_constraints", "retrieve_programs")
    b.add_edge("retrieve_programs", "translate_rules")
    b.add_edge("translate_rules", "confirm_rules")
    b.add_edge("confirm_rules", "solve")
    b.add_edge("solve", "verify")
    b.add_edge("verify", "propose")
    b.add_edge("propose", "approval")
    b.add_conditional_edges("approval", route_after_approval, ["finalize", "learn_from_rejection", END])
    b.add_edge("learn_from_rejection", "solve")
    b.add_edge("finalize", END)
    return b.compile(checkpointer=checkpointer)


_graph: Any = None


def get_graph() -> Any:
    global _graph
    if _graph is None:
        from ..checkpoint import get_checkpointer

        _graph = build_graph(get_checkpointer())
    return _graph


def trace_nodes() -> list[dict[str, Any]]:
    return [dict(n) for n in (
        trace_node("gather_constraints", "Your constraints", "logic"),
        trace_node("retrieve_programs", "Find programs (TF-IDF)", "model"),
        trace_node("translate_rules", "Read your rules", "llm"),
        trace_node("confirm_rules", "Confirm rules", "human"),
        trace_node("solve", "CP-SAT solver", "solver"),
        trace_node("verify", "Verify plan", "logic"),
        trace_node("propose", "Write proposal", "llm"),
        trace_node("approval", "Your approval", "human"),
        trace_node("learn_from_rejection", "Turn feedback into a rule", "llm"),
        trace_node("finalize", "Save plan", "logic"),
    )]


def project(name: str, update: dict[str, Any]) -> dict[str, Any] | None:
    if name == "gather_constraints":
        return {"inputs": update.get("inputs")}
    if name == "retrieve_programs":
        return {"retrieved": update.get("retrieved")}
    if name == "translate_rules":
        return {"proposed_rules": _labelled(update.get("proposed_rules") or [])}
    if name in ("confirm_rules", "learn_from_rejection"):
        return {"rules": _labelled(update.get("rules") or []), "rejections": update.get("rejections")}
    if name == "solve":
        return {"result": update.get("result"), "round": update.get("round")}
    if name == "verify":
        return {"verification": update.get("verification")}
    if name == "propose":
        return {"proposal": update.get("proposal")}
    if name == "finalize":
        return {"kanban": update.get("kanban")}
    return None


def public_state(values: dict[str, Any]) -> dict[str, Any]:
    return {
        "career_id": values.get("career_id"), "inputs": values.get("inputs"), "rules": _labelled(values.get("rules") or []),
        "retrieved": values.get("retrieved"), "result": values.get("result"), "verification": values.get("verification"),
        "proposal": values.get("proposal"), "rejections": values.get("rejections") or [], "round": values.get("round"),
        "approved": bool(values.get("approved")), "kanban": values.get("kanban"),
    }


def initial_state(learner_id: str, persona_id: str, career_id: str, inputs: dict[str, Any], text: str,
                  rules: list[dict[str, Any]], origin: dict[str, Any] | None = None) -> PathState:
    return {"learner_id": learner_id, "persona_id": persona_id, "career_id": career_id,
            "inputs": {k: v for k, v in inputs.items() if k in DEFAULT_INPUTS and v is not None},
            "text": text or "", "rules": planner.dedupe_rules(rules or []), "proposed_rules": [], "retrieved": [],
            "result": None, "verification": None, "proposal": None, "rejections": [], "round": 0, "approved": False,
            "kanban": None, "translate_source": None, "origin": origin}


__all__ = ["GRAPH_NAME", "build_graph", "get_graph", "initial_state", "load_kanban", "project", "public_state",
           "regex_rules", "retrieve", "save_kanban", "trace_nodes", "translate_text"]
