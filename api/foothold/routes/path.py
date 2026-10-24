"""Pathway endpoints (CONTRACTS sections 6, 9, 13).

POST /api/path/solve                  public  {career_id, current_credits, hours_per_week, budget_usd,
                                               commute_minutes, dependents, extra_constraints?,
                                               place_id? | lat?+lon?} -> all routes (+ commute per campus)
POST /api/path/translate              public  {text} -> {rules:[{type,...,label}], source}
POST /api/path/start                  learner {career_id, text?, rules?, inputs...} SSE (pathway graph)
POST /api/path/{thread_id}/decision   learner {approve, reason?, rules?} SSE (resumes the pending interrupt)
GET  /api/path/{thread_id}/state      learner (owner only)
GET  /api/path/kanban                 learner -> {items, updated_at}
PUT  /api/path/kanban                 learner {items:[...]} -> {items, updated_at}
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, status
from langgraph.types import Command
from pydantic import BaseModel, Field

from foothold import data, db, places, planner, profiles, sse
from foothold.auth import Account, LearnerAccount, OptionalAccount
from foothold.graphs import pathway

log = logging.getLogger("foothold.path")

router = APIRouter(prefix="/api/path", tags=["path"])

RUN_CONFIG = {"recursion_limit": 80}
SOLVE_TIMEOUT_S = 1.8
_busy: set[str] = set()


class SolveBody(BaseModel):
    career_id: str
    current_credits: float | None = 0
    hours_per_week: float | None = 12
    budget_usd: float | None = 2000
    commute_minutes: float | None = 20
    dependents: int | None = 0
    extra_constraints: Any = None
    # location: explicit lat/lon or place_id; otherwise the signed-in learner's saved place (if they set one)
    place_id: str | None = Field(default=None, max_length=40)
    lat: float | None = None
    lon: float | None = None


class TranslateBody(BaseModel):
    text: str = Field(default="", max_length=1200)


class StartBody(BaseModel):
    career_id: str
    current_credits: float | None = None
    hours_per_week: float | None = None
    budget_usd: float | None = None
    commute_minutes: float | None = None
    dependents: int | None = None
    text: str = Field(default="", max_length=1200)
    rules: list[dict[str, Any]] = Field(default_factory=list)
    place_id: str | None = Field(default=None, max_length=40)
    lat: float | None = None
    lon: float | None = None


class DecisionBody(BaseModel):
    approve: bool = False
    reason: str | None = Field(default=None, max_length=500)
    rules: list[dict[str, Any]] | None = None


class KanbanBody(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list, max_length=200)


def _origin(body: Any, account: Account | None) -> dict[str, Any] | None:
    """Explicit place/lat-lon in the body, else the account's saved place (only once the user set one)."""
    o = places.origin_from(getattr(body, "place_id", None), getattr(body, "lat", None), getattr(body, "lon", None))
    if o is not None or account is None or account.kind != "learner":
        return o
    try:
        return profiles.saved_origin(account)
    except Exception as exc:  # noqa: BLE001  (location is a bonus; never fail the plan)
        log.warning("profile origin unavailable (%s)", type(exc).__name__)
        return None


def _check_career(cid: str) -> None:
    if cid not in data.career_ids():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Unknown career.")


@router.post("/solve")
async def solve(body: SolveBody, account: OptionalAccount) -> dict[str, Any]:
    _check_career(body.career_id)
    t0 = time.perf_counter()
    rules = planner.rules_from_extra(body.extra_constraints) if body.extra_constraints else []
    c = planner.make_constraints(hours_per_week=body.hours_per_week, budget_usd=body.budget_usd,
                                 commute_minutes=body.commute_minutes, dependents=body.dependents,
                                 current_credits=body.current_credits, rules=rules)
    try:
        origin = await asyncio.to_thread(_origin, body, account)
        res = await asyncio.wait_for(asyncio.to_thread(planner.solve_routes, body.career_id, c, origin=origin),
                                     timeout=SOLVE_TIMEOUT_S + 2)
    except asyncio.TimeoutError:
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, detail="The planner took too long; try fewer rules.")
    res["rules"] = [{**r, "label": planner.describe_rule(r)} for r in rules]
    res["request_ms"] = int(round((time.perf_counter() - t0) * 1000))
    return res


@router.post("/translate")
async def translate(body: TranslateBody, account: OptionalAccount) -> dict[str, Any]:
    rules, meta = await asyncio.to_thread(pathway.translate_text, body.text)
    return {"rules": [{**r, "label": planner.describe_rule(r)} for r in rules], "source": meta.get("source"),
            "rule_types": list(planner.RULE_TYPES)}


def _cfg(tid: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": tid}}


async def _owned(tid: str, learner: Account) -> Any:
    if not tid.startswith("path_") or len(tid) > 64:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such plan.")
    snap = await pathway.get_graph().aget_state(_cfg(tid))
    values = getattr(snap, "values", None) or {}
    if not values or values.get("learner_id") != learner.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such plan.")
    return snap


def _pending(snap: Any) -> list[dict[str, Any]]:
    return [{"node": t.name, "payload": i.value} for t in (getattr(snap, "tasks", None) or ()) for i in (t.interrupts or ())]


async def _guarded(tid: str, events: AsyncIterator[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    try:
        async for ev in events:
            yield ev
    finally:
        _busy.discard(tid)


def _claim(tid: str) -> None:
    if tid in _busy:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This step is still running.")
    _busy.add(tid)


def _result(tid: str):
    def result(values: dict[str, Any]) -> dict[str, Any]:
        return {"thread_id": tid, **pathway.public_state(values)}

    return result


def _stream(tid: str, inp: Any):
    events = sse.stream_graph(pathway.get_graph(), graph_name=pathway.GRAPH_NAME, thread_id=tid, input=inp,
                              nodes=pathway.trace_nodes(), projector=pathway.project, result=_result(tid), config=RUN_CONFIG)
    return sse.sse_response(_guarded(tid, events))


@router.post("/start")
async def start(body: StartBody, learner: LearnerAccount):
    _check_career(body.career_id)
    tid = f"path_{uuid.uuid4().hex[:20]}"
    inputs = body.model_dump(include={"current_credits", "hours_per_week", "budget_usd", "commute_minutes", "dependents"})
    origin = await asyncio.to_thread(_origin, body, learner)
    state = pathway.initial_state(learner.id, learner.persona_id, body.career_id, inputs, body.text, body.rules,
                                  origin=origin)
    _claim(tid)
    return _stream(tid, state)


@router.post("/{thread_id}/decision")
async def decision(thread_id: str, body: DecisionBody, learner: LearnerAccount):
    snap = await _owned(thread_id, learner)
    pending = _pending(snap)
    if not pending:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Nothing is waiting for a decision.")
    kind = (pending[0]["payload"] or {}).get("kind")
    if kind == "confirm_rules":
        resume: dict[str, Any] = {"rules": body.rules} if body.rules is not None else {"confirm": True}
    else:
        resume = {"approve": bool(body.approve), "reason": body.reason}
    _claim(thread_id)
    return _stream(thread_id, Command(resume=resume))


@router.post("/{thread_id}/continue")
async def continue_run(thread_id: str, learner: LearnerAccount):
    """Resume a run whose stream was cut mid-step (e.g. a server restart)."""
    snap = await _owned(thread_id, learner)
    if _pending(snap) or not getattr(snap, "next", None):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Nothing to continue.")
    _claim(thread_id)
    return _stream(thread_id, None)


@router.get("/{thread_id}/state")
async def get_state(thread_id: str, learner: LearnerAccount) -> dict[str, Any]:
    snap = await _owned(thread_id, learner)
    pending = _pending(snap)
    values = snap.values or {}
    run = "waiting" if pending else (("busy" if thread_id in _busy else "stalled") if getattr(snap, "next", None) else "done")
    return {"thread_id": thread_id, "status": run, "interrupt": pending[0]["payload"] if pending else None,
            "state": pathway.public_state(values)}


@router.get("/kanban")
async def get_kanban(learner: LearnerAccount) -> dict[str, Any]:
    row = await asyncio.to_thread(db.query_one, "SELECT items_json, updated_at FROM kanban WHERE learner_id = ?", (learner.persona_id,))
    items = db.jloads(row["items_json"], []) if row else []
    return {"items": items if isinstance(items, list) else [], "updated_at": row["updated_at"] if row else None,
            "columns": ["todo", "doing", "done"]}


@router.put("/kanban")
async def put_kanban(body: KanbanBody, learner: LearnerAccount) -> dict[str, Any]:
    clean = []
    for it in body.items:
        if not isinstance(it, dict) or not it.get("id"):
            continue
        col = it.get("column") if it.get("column") in ("todo", "doing", "done") else "todo"
        clean.append({**{k: v for k, v in it.items() if isinstance(k, str) and len(k) <= 40}, "column": col})
    await asyncio.to_thread(pathway.save_kanban, learner.persona_id, clean)
    return await get_kanban(learner)
