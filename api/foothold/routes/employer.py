"""Employer + consent endpoints (CONTRACTS sections 9, 13; brief 5.3). All data FICTIONAL.

Employer account (token) only:
  POST /api/employer/postings                 {title, text, min_hours?, region?} -> SSE (employer graph) until
                                              the request_consent interrupt (payload.kind = "pick_candidates").
  POST /api/employer/postings/{thread_id}/contact {candidate_ids:[...], message?} -> SSE resume -> done.
  GET  /api/employer/postings                 the employer's postings (id, title, created_at, profile summary).
  GET  /api/employer/talent?posting_id=&limit=&min_hours=&region=&max_km=   blind cards ranked for that posting
                                              (max_km: distance from the employer's profile place)
                                              (+ request status per card). Without posting_id: unranked.
  POST /api/employer/consent-requests         {candidate_id, posting_id?, message}
  GET  /api/employer/requests                 {requests:[...], counts:{pending, accepted, declined, total, acceptance_rate}}
  GET  /api/employer/candidates/{candidate_id} {card, consented, revealed|null, request|null}
  GET  /api/employer/fairness?posting_id=     four-fifths audit of the posting shortlist (+ offline metrics if present)
  GET  /api/employer/gap-report               aggregate skill gaps (min group size 5); refreshes skill_demand
Learner account (token) only:
  GET  /api/employer/inbox                    requests addressed to my card + what acceptance shares
  GET  /api/employer/inbox/{learner_id}       same; learner_id must be the signed-in learner (or "me")
  POST /api/employer/consent/{request_id}     {decision: accept|decline}
Public:
  GET  /api/employer/demand                   skill_demand rows (aggregates) for learner recommendations
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, Query, status
from langgraph.types import Command
from pydantic import BaseModel

from foothold import consent, data, db, profiles, sse
from foothold.auth import Account, EmployerAccount, LearnerAccount
from foothold.graphs import employer as eg

log = logging.getLogger("foothold.employer")

router = APIRouter(prefix="/api/employer", tags=["employer"])

MAX_POSTING_CHARS = 8000
_busy: set[str] = set()


class PostingIn(BaseModel):
    title: str = ""
    text: str = ""
    min_hours: int | None = None
    region: str | None = None
    employer_id: str | None = None  # ignored: identity comes from the token


class ContactIn(BaseModel):
    candidate_ids: list[str] = []
    message: str | None = None


class ConsentIn(BaseModel):
    candidate_id: str = ""
    posting_id: str | None = None
    message: str = ""


class DecisionIn(BaseModel):
    decision: str = ""


def _err(exc: consent.ConsentError) -> HTTPException:
    return HTTPException(exc.status, detail=exc.detail)


def _cfg(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


async def _guarded(thread_id: str, events: AsyncIterator[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    try:
        async for ev in events:
            yield ev
    finally:
        _busy.discard(thread_id)


def _stream(thread_id: str, input: Any):
    if thread_id in _busy:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This step is still running.")
    _busy.add(thread_id)

    def result(values: dict[str, Any]) -> dict[str, Any]:
        return {"thread_id": thread_id, **eg.result(values)}

    events = sse.stream_graph(
        eg.GRAPH, graph_name=eg.GRAPH_NAME, thread_id=thread_id, input=input,
        nodes=eg.NODES, projector=eg.projector, result=result, config={"recursion_limit": 30},
    )
    return sse.sse_response(_guarded(thread_id, events))


# ---------------------------------------------------------------------------
# Postings (SSE graph)
# ---------------------------------------------------------------------------


@router.post("/postings")
async def create_posting(body: PostingIn, employer: EmployerAccount):
    title = " ".join((body.title or "").split())[:120]
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Paste the job posting text.")
    if len(text) > MAX_POSTING_CHARS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Postings are limited to {MAX_POSTING_CHARS} characters.")
    min_hours = body.min_hours if isinstance(body.min_hours, int) and 0 < body.min_hours <= 80 else None
    region = " ".join((body.region or "").split())[:60] or None
    thread_id = eg.new_thread_id()
    state = {
        "employer_id": employer.persona_id,
        "employer_name": employer.org or employer.display_name,
        "title": title or "Untitled posting",
        "text": text,
        "min_hours": min_hours,
        "region": region,
    }
    return _stream(thread_id, state)


@router.post("/postings/{thread_id}/contact")
async def contact(thread_id: str, body: ContactIn, employer: EmployerAccount):
    if not thread_id.startswith("emp_") or len(thread_id) > 64:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such posting run.")
    snap = await eg.GRAPH.aget_state(_cfg(thread_id))
    values = getattr(snap, "values", None) or {}
    if not values or values.get("employer_id") != employer.persona_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such posting run.")
    if not any(t.interrupts for t in (getattr(snap, "tasks", None) or ())):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This posting run is not waiting for a pick.")
    ids = [i for i in body.candidate_ids if isinstance(i, str)][:10]
    resume: dict[str, Any] = {"candidate_ids": ids}
    if body.message and body.message.strip():
        resume["message"] = body.message.strip()[: consent.MAX_MESSAGE_CHARS]
    return _stream(thread_id, Command(resume=resume))


def _posting_row(posting_id: str, employer: Account) -> dict[str, Any] | None:
    return db.query_one(
        "SELECT id, title, profile_json, sim_variant_json, created_at FROM postings WHERE id = ? AND employer_id = ?",
        (posting_id, employer.persona_id),
    )


@router.get("/postings")
def list_postings(employer: EmployerAccount):
    rows = db.query(
        "SELECT id, title, profile_json, created_at FROM postings WHERE employer_id = ? ORDER BY created_at DESC LIMIT 50",
        (employer.persona_id,),
    )
    out = []
    for r in rows:
        prof = db.jloads(r["profile_json"], {}) or {}
        out.append({
            "id": r["id"], "title": r["title"], "created_at": r["created_at"],
            "career_id": prof.get("career_id"), "skills": prof.get("skills") or [],
            "injection": prof.get("injection"),
        })
    return {"postings": out}


# ---------------------------------------------------------------------------
# Talent, requests, candidates
# ---------------------------------------------------------------------------


@router.get("/talent")
def talent(
    employer: EmployerAccount,
    posting_id: str | None = Query(None, max_length=64),
    limit: int = Query(20, ge=1, le=100),
    min_hours: int | None = Query(None, ge=1, le=80),
    region: str | None = Query(None, max_length=60),
    max_km: float | None = Query(None, gt=0, le=1000),
):
    profile = None
    if posting_id:
        row = _posting_row(posting_id, employer)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Posting not found")
        profile = db.jloads(row["profile_json"], {}) or {}
    origin = profiles.origin_for(employer)
    res = eg.rank_pool(profile, min_hours=min_hours or (profile or {}).get("min_hours_per_week"), region=region, limit=limit,
                       origin=origin, max_km=max_km)
    statuses = consent.request_status_by_candidate(employer)
    cards = [{**c, "request": statuses.get(c["candidate_id"])} for c in res["cards"]]
    return {
        "posting_id": posting_id,
        "pool_size": res["pool_size"], "eligible": res["eligible"], "filtered_out": res["filtered_out"],
        "recommender": res["recommender"], "weights": res["weights"],
        "provenance": "SYNTHETIC", "fictional": True,
        "origin": {"place_id": origin.get("place_id"), "name": origin.get("name")} if origin else None,
        "max_km": max_km if origin else None,
        "cards": cards,
    }


@router.post("/consent-requests")
def create_consent_request(body: ConsentIn, employer: EmployerAccount):
    try:
        return consent.create_request(employer, body.candidate_id, body.message, body.posting_id or None)
    except consent.ConsentError as exc:
        raise _err(exc) from None


@router.get("/requests")
def my_requests(employer: EmployerAccount):
    return {"requests": consent.employer_requests(employer), "counts": consent.counts(employer)}


@router.get("/candidates/{candidate_id}")
def candidate(candidate_id: str, employer: EmployerAccount):
    try:
        return consent.candidate_view(employer, candidate_id)
    except consent.ConsentError as exc:
        raise _err(exc) from None


# ---------------------------------------------------------------------------
# Fairness + gap report
# ---------------------------------------------------------------------------


@router.get("/fairness")
async def fairness(employer: EmployerAccount, posting_id: str | None = Query(None, max_length=64)):
    if posting_id is None:
        row = db.query_one(
            "SELECT id, title, profile_json FROM postings WHERE employer_id = ? ORDER BY created_at DESC LIMIT 1",
            (employer.persona_id,),
        )
    else:
        row = _posting_row(posting_id, employer)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Posting not found")
    offline = (data.metrics() or {}).get("fairness")
    if row is None:
        return {"posting_id": None, "audit": {"available": False, "reason": "no postings yet"}, "offline": offline}
    profile = db.jloads(row["profile_json"], {}) or {}
    min_hours = profile.get("min_hours_per_week")

    def run() -> dict[str, Any]:
        ranked = eg.rank_pool(profile, min_hours=min_hours)
        ids = [c["candidate_id"] for c in ranked["cards"] if c["match"]["score"] > 0][: eg.SHORTLIST_SIZE]
        return eg.fairness_audit(ids, min_hours=min_hours)

    audit = await asyncio.to_thread(run)
    return {"posting_id": row["id"], "posting_title": row["title"], "shortlist_size": eg.SHORTLIST_SIZE,
            "audit": audit, "offline": offline}


@router.get("/gap-report")
async def gap_report_route(employer: EmployerAccount):
    return await asyncio.to_thread(eg.compute_gap_report, True)


@router.get("/demand")
def demand():
    return {"rows": consent.read_skill_demand(), "min_group_size": consent.MIN_GROUP_SIZE, "aggregate_only": True}


# ---------------------------------------------------------------------------
# Learner inbox + decisions
# ---------------------------------------------------------------------------


@router.get("/inbox")
def inbox(learner: LearnerAccount):
    try:
        return consent.learner_inbox(learner)
    except consent.ConsentError as exc:
        raise _err(exc) from None


@router.get("/inbox/{learner_id}")
def inbox_for(learner_id: str, learner: LearnerAccount):
    if learner_id not in ("me", learner.persona_id, learner.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You can only open your own inbox")
    return inbox(learner)


@router.post("/consent/{request_id}")
def decide(request_id: str, body: DecisionIn, learner: LearnerAccount):
    try:
        return consent.decide(learner, request_id, body.decision)
    except consent.ConsentError as exc:
        raise _err(exc) from None


__all__ = ["router"]
