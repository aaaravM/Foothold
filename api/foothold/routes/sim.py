"""Career Sim endpoints (CONTRACTS sections 6, 9, 13).

POST /api/sim/start               {career_id | null}  learner only; SSE until the first interrupt.
                                  The thread is bound to the signed-in learner (from the token).
POST /api/sim/{thread_id}/choose  {choice_id}         learner who owns the thread; SSE until the next
                                  interrupt, or ``done`` with the end-of-day report.
POST /api/sim/{thread_id}/continue                    resume a run whose stream was cut mid-step.
GET  /api/sim/{thread_id}/state                       owner only: status, pending event, public state, report.
GET  /api/sim/careers                                 public: the 8 careers with their sim event counts.
GET  /api/sim/sample-event                            public: one real event + the trait list (landing widget).

Identity always comes from the bearer token; ``persona_id`` in a body is ignored. Threads owned
by another account answer 404 (no existence leak). A completed report is saved to
``progress_log`` (kind ``sim_report``) for the learner; it stays private to the learner unless the
learner accepts an employer's consent request (enforced by the employer slice).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, Query, status
from langgraph.types import Command
from pydantic import BaseModel

from foothold import data, db, sse
from foothold.auth import Account, LearnerAccount, OptionalAccount
from foothold.graphs import sim

log = logging.getLogger("foothold.sim")

router = APIRouter(prefix="/api/sim", tags=["sim"])

RUN_CONFIG = {"recursion_limit": 60}
_busy: set[str] = set()  # threads with a stream in flight (single uvicorn worker)


class StartBody(BaseModel):
    career_id: str | None = None
    persona_id: str | None = None  # accepted for contract compatibility; identity comes from the token


class ChooseBody(BaseModel):
    choice_id: str = ""


def _graph() -> Any:
    return sim.get_graph()


def _cfg(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


async def _owned_snapshot(thread_id: str, learner: Account) -> Any:
    if not thread_id.startswith("sim_") or len(thread_id) > 64:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such workday.")
    snapshot = await _graph().aget_state(_cfg(thread_id))
    values = getattr(snapshot, "values", None) or {}
    if not values or values.get("learner_id") != learner.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such workday.")
    return snapshot


def _pending(snapshot: Any) -> list[dict[str, Any]]:
    out = []
    for task in getattr(snapshot, "tasks", None) or ():
        for intr in task.interrupts or ():
            out.append({"node": task.name, "payload": intr.value, "interrupt_id": intr.id})
    return out


def _save_report(learner: Account, thread_id: str, values: dict[str, Any]) -> None:
    rep = values.get("report") or {}
    payload = {
        "thread_id": thread_id,
        "mode": rep.get("mode"),
        "career_id": rep.get("career_id"),
        "top_careers": [{"career_id": t.get("career_id"), "probability": t.get("probability")} for t in rep.get("top_careers") or []],
        "model": {k: (rep.get("model") or {}).get(k) for k in ("source", "name", "trained")},
        "stats": rep.get("stats"),
        "traits": {t["id"]: t.get("value") for t in rep.get("traits") or [] if isinstance(t, dict) and t.get("id")},
        "trait_method": rep.get("trait_method"),
        "events_played": rep.get("events_played"),
        "crunch_used": rep.get("crunch_used"),
        "completed_at": db.now_iso(),
        "visibility": "learner_only_until_consent",
    }
    db.insert("progress_log", {"learner_id": learner.persona_id, "kind": "sim_report", "payload_json": payload})
    try:  # opted-in self-registered learners: refresh their blind talent card from this report
        from foothold import profiles

        profiles.sync_card(learner)
    except Exception as exc:  # noqa: BLE001
        log.warning("talent card not refreshed (%s)", type(exc).__name__)


def _result_for(learner: Account, thread_id: str):
    async def result(values: dict[str, Any]) -> dict[str, Any]:
        try:
            await asyncio.to_thread(_save_report, learner, thread_id, values)
            saved = True
        except Exception as exc:  # the report still reaches the learner
            log.warning("sim report not saved (%s)", type(exc).__name__)
            saved = False
        return {"thread_id": thread_id, "report": values.get("report"), "saved": saved}

    return result


async def _guarded(thread_id: str, events: AsyncIterator[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    try:
        async for ev in events:
            yield ev
    finally:
        _busy.discard(thread_id)


def _claim(thread_id: str) -> None:
    if thread_id in _busy:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This step is still running.")
    _busy.add(thread_id)


def _stream(thread_id: str, learner: Account, input: Any, coworkers: list[dict[str, Any]]):
    events = sse.stream_graph(
        _graph(), graph_name=sim.GRAPH_NAME, thread_id=thread_id, input=input,
        nodes=sim.trace_nodes(coworkers), projector=sim.project, result=_result_for(learner, thread_id),
        node_id=sim.node_id, config=RUN_CONFIG,
    )
    return sse.sse_response(_guarded(thread_id, events))


@router.post("/start")
async def start(body: StartBody, learner: LearnerAccount):
    career_id = body.career_id or None
    if career_id is not None and career_id not in data.career_ids():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Unknown career.")
    if not sim.events_available():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Sim events are not available yet.")
    if career_id is not None and not any(career_id in (e.get("career_ids") or []) for e in sim.all_events() if not e.get("crunch")):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="This career has no sim events yet.")
    thread_id = f"sim_{uuid.uuid4().hex[:20]}"
    _claim(thread_id)
    state = await asyncio.to_thread(sim.initial_state, learner.id, career_id)
    return _stream(thread_id, learner, state, sim.coworkers_for(career_id) if career_id else [])


@router.post("/{thread_id}/choose")
async def choose(thread_id: str, body: ChooseBody, learner: LearnerAccount):
    snapshot = await _owned_snapshot(thread_id, learner)
    pending = _pending(snapshot)
    if not pending:
        if getattr(snapshot, "next", None):
            raise HTTPException(status.HTTP_409_CONFLICT, detail="The last step did not finish; continue the run first.")
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This workday is already finished.")
    payload = pending[0]["payload"] or {}
    allowed = [c.get("choice_id") for c in ((payload.get("event") or {}).get("choices") or [])]
    if body.choice_id not in allowed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Pick one of the listed choices.")
    _claim(thread_id)
    return _stream(thread_id, learner, Command(resume=body.choice_id), payload.get("coworkers") or [])


@router.post("/{thread_id}/continue")
async def continue_run(thread_id: str, learner: LearnerAccount):
    snapshot = await _owned_snapshot(thread_id, learner)
    if _pending(snapshot) or not getattr(snapshot, "next", None):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Nothing to continue.")
    _claim(thread_id)
    values = snapshot.values or {}
    work = (values.get("current_event") or {}).get("_workplace")
    return _stream(thread_id, learner, None, sim.coworkers_for(work))


@router.get("/{thread_id}/state")
async def get_state(thread_id: str, learner: LearnerAccount) -> dict[str, Any]:
    snapshot = await _owned_snapshot(thread_id, learner)
    values = snapshot.values or {}
    pending = _pending(snapshot)
    if pending:
        run_status = "waiting"
    elif getattr(snapshot, "next", None):
        run_status = "busy" if thread_id in _busy else "stalled"
    else:
        run_status = "done" if values.get("report") else "empty"
    return {
        "thread_id": thread_id,
        "status": run_status,
        "interrupt": pending[0]["payload"] if pending else None,
        "state": sim.public_state(values),
        "report": values.get("report") if run_status == "done" else None,
    }


def _career_rows() -> list[dict[str, Any]]:
    events = sim.all_events()
    rows = []
    for c in data.careers():
        if not isinstance(c, dict) or not c.get("id"):
            continue
        n = sum(1 for e in events if not e.get("crunch") and c["id"] in (e.get("career_ids") or []))
        wage = c.get("wage") if isinstance(c.get("wage"), dict) else None
        rows.append({
            "id": c["id"], "title": c.get("title"), "summary": c.get("summary"), "onet_soc": c.get("onet_soc"),
            "onet_title": c.get("onet_title"), "path_types": c.get("path_types") or [], "events": n,
            "coworkers": [sim.public_coworker(cw, sim.initial_mood(cw)) for cw in sim.coworkers_for(c["id"])],
            "wage": None if wage is None else {k: wage.get(k) for k in ("median_annual", "median_hourly", "area", "period", "source_id", "status")},
        })
    return rows


@router.get("/careers")
def careers() -> dict[str, Any]:
    events = sim.all_events()
    return {
        "careers": _career_rows(),
        "events_total": sum(1 for e in events if not e.get("crunch")),
        "crunch_events": sum(1 for e in events if e.get("crunch")),
        "events_per_day": sim.EVENTS_PER_DAY,
        "crunch_stress": sim.CRUNCH_STRESS,
        "events_status": data.events().get("status"),
        "available": sim.events_available(),
    }


@router.get("/sample-event")
def sample_event(account: OptionalAccount, career_id: str | None = Query(default=None)) -> dict[str, Any]:
    events = [e for e in sim.all_events() if not e.get("crunch")]
    if career_id:
        events = [e for e in events if career_id in (e.get("career_ids") or [])]
    if not events:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Sim events are not available yet.")
    order = {cid: i for i, cid in enumerate(data.career_ids())}
    ev = sorted(events, key=lambda e: (order.get((e.get("career_ids") or [""])[0], 99), e.get("clock", ""), e["event_id"]))[0]
    cid = (ev.get("career_ids") or [None])[0]
    career = data.get_career(cid) if cid else None
    names = {t["id"]: t.get("name") for t in sim.traits_meta()}
    return {
        "event": {
            "event_id": ev["event_id"], "title": ev.get("title"), "text": ev.get("text"), "clock": ev.get("clock"),
            "career_ids": ev.get("career_ids") or [], "status": ev.get("status"),
            "choices": [{"choice_id": c["choice_id"], "text": c["text"],
                         "trait_deltas": [{"id": t, "name": names.get(t, t), "delta": d} for t, d in sim.precomputed_deltas(c).items()],
                         "stat_deltas": c.get("stat_deltas") or {},
                         "coworker_hints": c.get("coworker_hints") or {}} for c in ev.get("choices") or []],
        },
        "career": None if not career else {"id": career.get("id"), "title": career.get("title")},
        "coworkers": [{"id": w.get("id"), "name": w.get("name"), "role": w.get("role")}
                      for w in ((career or {}).get("coworkers") or [])],
        "traits": [{"id": t["id"], "name": t.get("name"), "group": t.get("group")} for t in sim.traits_meta()],
        "events_status": data.events().get("status"),
        "provenance": "SYNTHETIC",
    }
