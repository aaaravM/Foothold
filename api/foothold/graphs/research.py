"""Live web research graph (Tavily): makes the web search visible in the trace panel.

    plan_queries ──Send──┬─ web_search (day to day)  ─┬─ rank_sources ── summarize ── done
                         ├─ web_search (openings)    ─┤
                         └─ web_search (training)    ─┘      (group "web_search", parallel)

All logic lives in foothold.websearch (shared with ``websearch.research_career``); this
graph only splits it into nodes so each step streams its own §6 events. Web text is
untrusted: it is sanitized on arrival and only reaches the LLM wrapped (websearch.summarize).
No checkpointer: nothing from the web is persisted beyond the api/cache/web cache.
"""

from __future__ import annotations

import operator
import time
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from foothold import websearch
from foothold.sse import note, trace_node

GRAPH_NAME = "research"
GROUP = "web_search"


def nodes_for(queries: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        trace_node("plan_queries", "Plan web searches", "logic"),
        *[trace_node(f"search:{q['id']}", f"Search: {q['q']}", "model", group=GROUP) for q in queries],
        trace_node("rank_sources", "Rank sources", "logic"),
        trace_node("summarize", "Write cited summary", "llm"),
        trace_node("done", "Done", "logic"),
    ]


class ResearchState(TypedDict, total=False):
    title: str
    place_name: str | None
    started_at: float
    queries: list[dict[str, str]]
    buckets: Annotated[list[dict[str, Any]], operator.add]
    sources: list[dict[str, Any]]
    claims: list[dict[str, Any]]
    llm: str
    report: dict[str, Any]


def plan_queries(state: ResearchState) -> dict[str, Any]:
    queries = websearch.plan_queries(state.get("title") or "", state.get("place_name"))
    note(summary=f"Planned {len(queries)} web searches")
    return {"queries": queries}


def fan_out(state: ResearchState) -> list[Send]:
    return [Send("web_search", {"query": q, "_trace_id": f"search:{q['id']}"}) for q in state.get("queries") or []]


async def web_search(payload: dict[str, Any]) -> dict[str, Any]:
    q = payload["query"]
    d = await websearch.search_detailed(q["q"], prefer_cache=False)  # live: judges see the real search
    n = len(d["results"])
    if n:
        note(summary=f"Read {n} sources: '{d['query']}'" + (" (cached)" if d["source"] != "tavily" else ""))
    else:
        note(summary=f"No results ({d['reason'] or 'empty'}): '{d['query']}'")
    return {"buckets": [{**q, "results": d["results"], "source": d["source"], "reason": d["reason"], "ms": d["ms"]}]}


def rank_sources(state: ResearchState) -> dict[str, Any]:
    sources = websearch.rank_sources(state.get("buckets") or [])
    sites = len({s["source_domain"] for s in sources})
    note(summary=f"Kept {len(sources)} sources from {sites} sites" if sources else "No sources to rank")
    return {"sources": sources}


async def summarize(state: ResearchState) -> dict[str, Any]:
    sources = state.get("sources") or []
    claims, src = await websearch.summarize(state.get("title") or "", state.get("place_name"), sources)
    if claims:
        cited = len({n for c in claims for n in c["sources"]})
        note(summary=f"Wrote {len(claims)} sentences citing {cited} sources")
    else:
        note(summary="No summary (AI offline or nothing verifiable)" if sources else "Nothing to summarize")
    return {"claims": claims, "llm": src}


def done(state: ResearchState) -> dict[str, Any]:
    order = {"day": 0, "jobs": 1, "training": 2}
    buckets = sorted(state.get("buckets") or [], key=lambda b: order.get(b.get("id"), 9))
    queries = [{"id": b["id"], "purpose": b["purpose"], "q": b["q"], "n_results": len(b["results"]),
                "source": b["source"], "reason": b["reason"]} for b in buckets]
    t0 = time.perf_counter() - max(0.0, time.time() - float(state.get("started_at") or time.time()))
    report = websearch.build_report(state.get("title") or "", state.get("place_name"), queries,
                                    state.get("sources") or [], state.get("claims") or [], state.get("llm") or "none", t0)
    websearch.store_research(report)
    note(summary=f"Research ready in {report['ms'] / 1000:.1f} s")
    return {"report": report}


def build_graph():
    b = StateGraph(ResearchState)
    b.add_node("plan_queries", plan_queries)
    b.add_node("web_search", web_search)
    b.add_node("rank_sources", rank_sources)
    b.add_node("summarize", summarize)
    b.add_node("done", done)
    b.add_edge(START, "plan_queries")
    b.add_conditional_edges("plan_queries", fan_out, ["web_search"])
    b.add_edge("web_search", "rank_sources")
    b.add_edge("rank_sources", "summarize")
    b.add_edge("summarize", "done")
    b.add_edge("done", END)
    return b.compile()


GRAPH = build_graph()


def project(name: str, update: dict[str, Any]) -> dict[str, Any] | None:
    """UI-safe state patches (each query's results as they land)."""
    if name == "plan_queries":
        return {"queries": update.get("queries") or []}
    if name == "web_search":
        b = (update.get("buckets") or [None])[0]
        if not b:
            return None
        return {"search": {"id": b["id"], "q": b["q"], "purpose": b["purpose"], "results": b["results"],
                           "source": b["source"], "reason": b["reason"]}}
    if name == "rank_sources":
        return {"sources": update.get("sources") or []}
    if name == "summarize":
        claims = update.get("claims") or []
        return {"summary": websearch.summary_text(claims), "claims": claims}
    return None


def node_label(name: str, inp: Any) -> str | None:
    if name == "web_search" and isinstance(inp, dict) and isinstance(inp.get("query"), dict):
        return f"search:{inp['query']['id']}"
    return None
