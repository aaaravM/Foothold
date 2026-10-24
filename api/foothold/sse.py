"""LangGraph -> Server-Sent Events (CONTRACTS §6).

Wire format of every message: ``event: <type>\\ndata: <json>\\n\\n`` (json includes ``type``).

Usage in a route (graphs are compiled once at import with the shared checkpointer)::

    from langgraph.types import Command
    from foothold.sse import stream_graph, sse_response, trace_node

    NODES = [trace_node("pick_event", "Pick event", "model"),
             *[trace_node(f"coworker:{c}", c.title(), "llm", group="coworkers_react") for c in ids],
             trace_node("await_choice", "Your choice", "human")]

    @router.post("/start")
    async def start(body: StartBody):
        tid = new_thread_id()
        return sse_response(stream_graph(
            GRAPH, graph_name="sim", thread_id=tid, input={"career_id": body.career_id},
            nodes=NODES, projector=project, result=lambda s: {"fit": s.get("fit")},
            node_id=lambda name, inp: f"coworker:{inp['coworker_id']}" if name == "coworker" else name,
        ))

    @router.post("/{thread_id}/choose")
    async def choose(thread_id: str, body: ChooseBody):
        return sse_response(stream_graph(GRAPH, graph_name="sim", thread_id=thread_id,
                                         input=Command(resume=body.choice_id), nodes=NODES, ...))

Event semantics:
  * ``meta`` first (nodes = caller's TraceNode list).
  * ``node`` start/end per LangGraph task (stream mode "tasks": verified to emit a
    start and a result per task, results arriving as each parallel task finishes).
    ``ms`` is wall time from start to end; ``ts`` is epoch milliseconds.
    Send fan-out: each task gets its own label via ``node_id(name, input)``; without
    it, a Send payload containing ``"_trace_id"`` is used, else the node name.
  * ``state`` = ``projector(node_name, update)`` for each finished task, where
    ``update`` is the task's writes ``{channel: value}``. Return a small UI-safe dict
    or None. ``node_name`` is the graph node name (not the Send label).
  * ``interrupt`` for each ``interrupt(payload)`` raised in a task (plus static
    interrupt_before/after). The stream then ends WITHOUT ``done``: the run is
    waiting for a human; resume with ``input=Command(resume=value)``. The event also
    carries ``interrupt_id`` (needed only when several interrupts are pending).
  * ``done`` when the graph reached END: ``result(final_state_values)`` (sync or async).
  * ``error`` on any exception: generic message + error class only (no stack trace,
    no exception text, which may contain personal data). Running nodes get a final
    ``end`` with summary "failed" first.

``summary`` / ``llm`` on node end events, in priority order:
  1. ``foothold.trace.note(summary=..., llm=...)`` called inside the node (also
     re-exported here as ``sse.note``); ``llm.*`` calls record their source
     automatically, so nodes that use foothold.llm need no extra code;
  2. ``"_summary"`` / ``"_llm_source"`` keys in the node's update - only if the state
     schema declares them (LangGraph drops undeclared keys);
  3. ``summarize(node_name, update) -> str | None`` passed to stream_graph.
"""

from __future__ import annotations

import dataclasses
import enum
import inspect
import json
import logging
import math
import time
from datetime import date, datetime
from typing import Any, AsyncIterable, AsyncIterator, Callable, Iterable, Literal, Mapping, NotRequired, TypedDict

from pydantic import BaseModel
from starlette.responses import StreamingResponse

from . import trace
from .config import get_settings
from .trace import note  # noqa: F401  (re-export for graph nodes)

log = logging.getLogger("foothold.sse")

NodeKind = Literal["llm", "model", "solver", "human", "logic"]
LLM_SOURCES = ("openai", "cache", "mock")
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
STREAM_MODES = ["tasks", "values"]  # task start/result events + final values (no-checkpointer fallback)


class TraceNode(TypedDict):
    id: str
    label: str
    kind: NodeKind
    group: NotRequired[str]


def trace_node(id: str, label: str, kind: NodeKind, group: str | None = None) -> TraceNode:
    node: TraceNode = {"id": id, "label": label, "kind": kind}
    if group:
        node["group"] = group
    return node


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------


def _json_default(o: Any) -> Any:
    if isinstance(o, BaseModel):
        return o.model_dump(mode="json")
    if dataclasses.is_dataclass(o) and not isinstance(o, type):
        return dataclasses.asdict(o)
    if isinstance(o, (set, frozenset)):
        return sorted(o, key=str)
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, enum.Enum):
        return o.value
    if hasattr(o, "tolist"):  # numpy arrays / scalars
        return o.tolist()
    return str(o)


def _clean_nans(o: Any) -> Any:
    if isinstance(o, float) and not math.isfinite(o):
        return None
    if isinstance(o, Mapping):
        return {k: _clean_nans(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean_nans(v) for v in o]
    return o


def _dumps(obj: Any) -> str:
    kwargs: dict[str, Any] = {"default": _json_default, "ensure_ascii": False, "separators": (",", ":")}
    try:
        return json.dumps(obj, allow_nan=False, **kwargs)
    except ValueError:  # NaN/Infinity are not valid JSON for browsers
        return json.dumps(_clean_nans(json.loads(json.dumps(obj, **kwargs))), allow_nan=False, **kwargs)


def format_event(event: Mapping[str, Any]) -> str:
    """``event: <type>\\ndata: <json>\\n\\n`` (the json keeps ``type``)."""
    etype = str(event.get("type") or "message")
    return f"event: {etype}\ndata: {_dumps(dict(event))}\n\n"


def _now_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------------------
# Graph streaming
# ---------------------------------------------------------------------------


def _node_dict(n: Any) -> dict[str, Any]:
    if isinstance(n, BaseModel):
        n = n.model_dump()
    elif dataclasses.is_dataclass(n) and not isinstance(n, type):
        n = dataclasses.asdict(n)
    d = dict(n)
    out = {"id": str(d["id"]), "label": str(d.get("label") or d["id"]), "kind": str(d.get("kind") or "logic")}
    if d.get("group"):
        out["group"] = str(d["group"])
    return out


def _label(node_id: Callable[[str, Any], str | None] | None, name: str, inp: Any, pushed: bool) -> str:
    if node_id is not None:
        try:
            lab = node_id(name, inp)
            if lab:
                return str(lab)
        except Exception as exc:
            log.warning("node_id callback failed for %s (%s)", name, type(exc).__name__)
    if pushed and isinstance(inp, Mapping):
        tid = inp.get("_trace_id")
        if isinstance(tid, str) and tid:
            return tid
    return name


def _safe_call(fn: Callable[..., Any] | None, *args: Any) -> Any:
    if fn is None:
        return None
    try:
        return fn(*args)
    except Exception as exc:
        log.warning("sse callback %s failed (%s)", getattr(fn, "__name__", "callback"), type(exc).__name__)
        return None


def _strip_internal(values: Any) -> Any:
    if isinstance(values, Mapping):
        return {k: v for k, v in values.items() if not str(k).startswith("__")}
    return values


def _error_event(graph_name: str, exc: BaseException) -> dict[str, Any]:
    return {"type": "error", "message": f"The {graph_name} run failed ({type(exc).__name__}). Please try again."}


async def stream_graph(
    graph: Any,
    *,
    graph_name: str,
    thread_id: str,
    input: Any,
    nodes: Iterable[Any] = (),
    projector: Callable[[str, dict[str, Any]], dict[str, Any] | None] | None = None,
    result: Callable[[dict[str, Any]], Any] | None = None,
    summarize: Callable[[str, dict[str, Any]], str | None] | None = None,
    node_id: Callable[[str, Any], str | None] | None = None,
    config: Mapping[str, Any] | None = None,
    context: Any = None,
) -> AsyncIterator[dict[str, Any]]:
    """Run ``graph`` for ``thread_id`` and yield §6 events as dicts (see module doc).

    ``input`` is the initial state dict, ``Command(resume=...)``, or ``None`` to
    continue from the last checkpoint. ``config`` is merged into the run config
    (e.g. ``{"recursion_limit": 50}``); ``context`` is passed to ``astream``.
    """
    run_config: dict[str, Any] = dict(config or {})
    configurable = dict(run_config.get("configurable") or {})
    configurable["thread_id"] = thread_id
    run_config["configurable"] = configurable

    yield {"type": "meta", "graph": graph_name, "thread_id": thread_id, "nodes": [_node_dict(n) for n in nodes]}

    labels: dict[str, str] = {}
    started: dict[str, float] = {}
    interrupted = False
    last_values: Any = None
    stream_kwargs: dict[str, Any] = {"stream_mode": STREAM_MODES}
    if context is not None:
        stream_kwargs["context"] = context

    with trace.collect() as notes:
        try:
            async for mode, chunk in graph.astream(input, run_config, **stream_kwargs):
                if mode == "values":
                    last_values = chunk
                    continue
                if mode != "tasks" or not isinstance(chunk, Mapping):
                    continue
                task_id = str(chunk.get("id"))
                name = str(chunk.get("name"))

                if "triggers" in chunk and "result" not in chunk:  # task start
                    pushed = any("push" in str(t) for t in (chunk.get("triggers") or ()))
                    labels[task_id] = _label(node_id, name, chunk.get("input"), pushed)
                    started[task_id] = time.perf_counter()
                    yield {"type": "node", "graph": graph_name, "node": labels[task_id], "status": "start", "ts": _now_ms()}
                    continue

                # task finished (result / error / interrupts)
                label = labels.get(task_id) or _label(node_id, name, None, False)
                t0 = started.pop(task_id, None)
                interrupts = chunk.get("interrupts") or []
                if interrupts:
                    interrupted = True
                    trace.pop(notes, task_id)
                    for intr in interrupts:
                        value = intr.get("value") if isinstance(intr, Mapping) else getattr(intr, "value", None)
                        iid = intr.get("id") if isinstance(intr, Mapping) else getattr(intr, "id", None)
                        yield {"type": "interrupt", "graph": graph_name, "node": label, "payload": value, "interrupt_id": iid}
                    continue

                raw = chunk.get("result")
                update: dict[str, Any] = dict(raw) if isinstance(raw, Mapping) else ({} if raw is None else {"value": raw})
                failed = chunk.get("error") is not None
                tnotes = trace.pop(notes, task_id)
                summary = tnotes["summary"]
                if not summary and isinstance(update.get("_summary"), str):
                    summary = update["_summary"]
                if not summary and not failed:
                    s = _safe_call(summarize, name, update)
                    summary = s if isinstance(s, str) else None
                if failed:
                    summary = "failed"
                llm_source = tnotes["llm"] or (update.get("_llm_source") if update.get("_llm_source") in LLM_SOURCES else None)

                event: dict[str, Any] = {"type": "node", "graph": graph_name, "node": label, "status": "end", "ts": _now_ms()}
                if t0 is not None:
                    event["ms"] = int(round((time.perf_counter() - t0) * 1000))
                if summary:
                    event["summary"] = " ".join(summary.split())[:160]
                if llm_source:
                    event["llm"] = llm_source
                yield event

                if projector is not None and not failed:
                    patch = _safe_call(projector, name, update)
                    if patch:
                        yield {"type": "state", "graph": graph_name, "data": patch}

            # Stream finished: either waiting for a human, or done.
            snapshot = None
            try:
                snapshot = await graph.aget_state(run_config)
            except Exception:  # e.g. no checkpointer: fall back to streamed values
                snapshot = None

            if snapshot is not None and snapshot.next:
                if not interrupted:  # static interrupt_before/after, or interrupts not reported per task
                    emitted = False
                    for task in snapshot.tasks or ():
                        for intr in task.interrupts or ():
                            emitted = True
                            yield {
                                "type": "interrupt", "graph": graph_name,
                                "node": labels.get(task.id) or _label(node_id, task.name, None, False),
                                "payload": intr.value, "interrupt_id": intr.id,
                            }
                    if not emitted:
                        yield {"type": "interrupt", "graph": graph_name,
                               "node": _label(node_id, snapshot.next[0], None, False), "payload": None}
                return
            if interrupted:
                return

            values = _strip_internal(snapshot.values if snapshot is not None else last_values) or {}
            res = result(values) if result is not None else None
            if inspect.isawaitable(res):
                res = await res
            yield {"type": "done", "graph": graph_name, "result": res}

        except Exception as exc:
            now = time.perf_counter()
            for task_id, t0 in list(started.items()):
                yield {"type": "node", "graph": graph_name, "node": labels.get(task_id, "?"), "status": "end",
                       "ts": _now_ms(), "ms": int(round((now - t0) * 1000)), "summary": "failed"}
            started.clear()
            log.warning("graph %s run failed (%s)", graph_name, type(exc).__name__, exc_info=get_settings().debug)
            yield _error_event(graph_name, exc)


async def pending_interrupts(graph: Any, thread_id: str) -> list[dict[str, Any]]:
    """Interrupts the thread is waiting on: ``[{node, payload, interrupt_id}]`` ([] if none)."""
    snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    out: list[dict[str, Any]] = []
    for task in snapshot.tasks or ():
        for intr in task.interrupts or ():
            out.append({"node": task.name, "payload": intr.value, "interrupt_id": intr.id})
    return out


async def thread_values(graph: Any, thread_id: str) -> dict[str, Any] | None:
    """Current state values for a thread, or None if the thread has no checkpoint."""
    snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    if snapshot is None or (not snapshot.values and snapshot.created_at is None):
        return None
    return _strip_internal(snapshot.values)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


def sse_response(
    events: AsyncIterable[Mapping[str, Any] | str],
    *,
    headers: Mapping[str, str] | None = None,
    status_code: int = 200,
) -> StreamingResponse:
    """Stream event dicts (or preformatted strings) as ``text/event-stream``.

    Headers: ``Cache-Control: no-cache``, ``X-Accel-Buffering: no``. An exception
    escaping ``events`` becomes a final ``error`` event (class name only).
    """

    async def body() -> AsyncIterator[str]:
        try:
            async for ev in events:
                yield ev if isinstance(ev, str) else format_event(ev)
        except Exception as exc:
            log.warning("sse stream failed (%s)", type(exc).__name__, exc_info=get_settings().debug)
            yield format_event({"type": "error", "message": f"The stream failed ({type(exc).__name__}). Please try again."})

    return StreamingResponse(
        body(), status_code=status_code, media_type="text/event-stream", headers={**SSE_HEADERS, **(headers or {})}
    )


def sse_events(events: Iterable[Mapping[str, Any]], **kwargs: Any) -> StreamingResponse:
    """SSE response for a fixed list of events (e.g. a crisis short-circuit)."""
    items = list(events)

    async def gen() -> AsyncIterator[Mapping[str, Any]]:
        for ev in items:
            yield ev

    return sse_response(gen(), **kwargs)
