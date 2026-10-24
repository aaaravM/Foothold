"""Per-run trace notes for SSE node events (CONTRACTS §6 ``summary`` / ``llm``).

``sse.stream_graph`` opens :func:`collect` around a graph run. Code running inside
a LangGraph node can then attach notes to *its own task* without touching the
graph state schema:

* ``llm.structured/text/astructured/atext`` call :func:`note` automatically with
  their source ("openai" | "cache" | "mock"), so the node's ``end`` event gets
  ``llm`` for free. If a node makes several calls, the weakest source wins
  (mock > cache > openai), so the UI never overstates "live".
* Nodes may call ``note(summary="picked event rn_02 · gain 0.41 bits")`` for the
  ``summary`` field (keep it short and non-personal).

How it works: a ContextVar holds a per-run dict; LangGraph copies the context into
every node (async tasks and the thread pool used for sync nodes), and the node's
task id is read from ``langgraph.config.get_config()`` (``checkpoint_ns`` is
``"<node>:<task_id>"``). Outside a graph run, :func:`note` is a no-op.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

_NOTES: ContextVar[dict[str, dict[str, Any]] | None] = ContextVar("foothold_trace_notes", default=None)
_LOCK = threading.Lock()

_SOURCE_RANK = {"openai": 0, "cache": 1, "mock": 2}
SUMMARY_MAX_CHARS = 160


def current_task_id() -> str | None:
    """Task id of the LangGraph task running this code (root-level task), or None."""
    try:
        from langgraph.config import get_config

        cfg = get_config()
    except Exception:  # RuntimeError outside a runnable context, ImportError, ...
        return None
    ns = (cfg.get("configurable") or {}).get("checkpoint_ns") or (cfg.get("metadata") or {}).get(
        "langgraph_checkpoint_ns"
    )
    if not ns or not isinstance(ns, str):
        return None
    first = ns.split("|", 1)[0]  # nested subgraph calls are attributed to the root task
    task_id = first.rpartition(":")[2]
    return task_id or None


@contextmanager
def collect() -> Iterator[dict[str, dict[str, Any]]]:
    """Open a notes scope for one graph run; yields the dict ``{task_id: notes}``."""
    notes: dict[str, dict[str, Any]] = {}
    token = _NOTES.set(notes)
    try:
        yield notes
    finally:
        try:
            _NOTES.reset(token)
        except ValueError:  # generator closed from another context; harmless
            pass


def note(*, summary: str | None = None, llm: str | None = None) -> None:
    """Attach a summary and/or an LLM source to the current node's ``end`` event."""
    notes = _NOTES.get()
    if notes is None:
        return
    task_id = current_task_id()
    if task_id is None:
        return
    with _LOCK:
        entry = notes.setdefault(task_id, {"llm": [], "summary": None})
        if llm in _SOURCE_RANK:
            entry["llm"].append(llm)
        if summary:
            entry["summary"] = " ".join(str(summary).split())[:SUMMARY_MAX_CHARS]


def pop(notes: dict[str, dict[str, Any]], task_id: str) -> dict[str, Any]:
    """Remove and return ``{"llm": <weakest source or None>, "summary": str|None}``."""
    with _LOCK:
        entry = notes.pop(task_id, None) or {}
    sources = entry.get("llm") or []
    weakest = max(sources, key=lambda s: _SOURCE_RANK.get(s, 0)) if sources else None
    return {"llm": weakest, "summary": entry.get("summary")}
