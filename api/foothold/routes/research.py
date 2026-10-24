"""Live web research endpoints (Tavily). Optional auth: the signed-in profile's place is used
when no place_id is given.

  POST /api/research/stream  {career_id?, title?, place_id?} -> SSE (meta / node / state / done)
       state.data is one of: {queries:[{id,purpose,q}]} | {search:{id,q,purpose,results:[{title,url,
       snippet,source_domain}],source,reason}} | {sources:[{n,title,url,snippet,source_domain,query_id}]}
       | {summary, claims:[{text, sources:[n]}]};  done.result = the report (see websearch.research_career).
  GET  /api/research/local?title=&career_id=&place_id=   cached report (runs the research if not cached)
       -> report + {cached: bool}
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from foothold import data, places, profiles, sse, websearch
from foothold.auth import Account, OptionalAccount
from foothold.graphs import research as rg

router = APIRouter(prefix="/api/research", tags=["research"])


class ResearchIn(BaseModel):
    career_id: str | None = None
    title: str | None = None
    place_id: str | None = None


def _title(career_id: str | None, title: str | None) -> str:
    if career_id:
        c = data.get_career(career_id)
        if c:
            return str(c.get("title") or career_id)
    t = websearch.clean_title(title)
    if not t:
        raise HTTPException(422, detail="Give a career_id or a title.")
    return t


def _place_name(place_id: str | None, viewer: Account | None) -> str | None:
    p = places.place(place_id)
    if p:
        return p["name"]
    try:
        origin = profiles.origin_for(viewer)
    except Exception:
        origin = None
    if origin and origin.get("place_id"):
        return origin.get("name")
    return None


@router.post("/stream")
async def research_stream(body: ResearchIn, viewer: OptionalAccount):
    title = _title(body.career_id, body.title)
    place_name = _place_name(body.place_id, viewer)
    queries = websearch.plan_queries(title, place_name)
    return sse.sse_response(sse.stream_graph(
        rg.GRAPH, graph_name=rg.GRAPH_NAME, thread_id=f"research-{uuid.uuid4().hex[:12]}",
        input={"title": title, "place_name": place_name, "started_at": time.time()},
        nodes=rg.nodes_for(queries), projector=rg.project, node_id=rg.node_label,
        result=lambda s: s.get("report"),
    ))


@router.get("/local")
async def research_local(
    viewer: OptionalAccount,
    title: str | None = Query(None, max_length=120),
    career_id: str | None = Query(None, max_length=64),
    place_id: str | None = Query(None, max_length=64),
) -> dict[str, Any]:
    t = _title(career_id, title)
    place_name = _place_name(place_id, viewer)
    hit = websearch.cached_research(t, place_name)
    if hit:
        return {**hit, "cached": True}
    report = await websearch.research_career(t, place_name)
    return {**report, "cached": False}
