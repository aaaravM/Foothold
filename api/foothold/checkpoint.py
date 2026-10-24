"""Shared LangGraph checkpointer: SQLite at api/.runtime/checkpoints.db (CONTRACTS §6).

Why this class (verified against langgraph-checkpoint-sqlite 3.1.2 / langgraph 1.2.17):

* ``SqliteSaver(sqlite3.connect(..., check_same_thread=False))`` works for sync
  ``graph.invoke`` but its async methods raise ``NotImplementedError``, so
  ``graph.astream`` (what FastAPI handlers use) fails.
* ``AsyncSqliteSaver`` binds to the event loop that created it (``__init__`` calls
  ``asyncio.get_running_loop()`` and it holds an ``asyncio.Lock``): it cannot be
  created at import time, fails from a second loop ("Lock ... is bound to a
  different event loop"), and its aiosqlite thread must be closed explicitly or
  the process will not exit.
* :class:`ThreadedSqliteSaver` = ``SqliteSaver`` + async methods that run the
  sync implementation in a worker thread. One sqlite3 connection
  (``check_same_thread=False``) guarded by SqliteSaver's internal lock; sqlite is
  in serialized threading mode (``sqlite3.threadsafety == 3``). Works at import
  time, from any event loop, from sync code and under concurrent runs.

Lifecycle:

* ``get_checkpointer()`` returns a process-wide singleton, created lazily on first
  call (creates api/.runtime/ and the db). Call it at import time when compiling
  graphs: ``graph = builder.compile(checkpointer=get_checkpointer())``.
* It stays open for the life of the process (uvicorn --reload restarts the
  process, which closes it). ``close_checkpointer()`` exists for scripts; graphs
  compiled earlier keep a reference to the closed saver, so only call it at exit.
* Tests: use ``langgraph.checkpoint.memory.InMemorySaver`` (alias ``MemorySaver``)
  or ``make_checkpointer(tmp_path / "ckpt.db")`` for an isolated sqlite file.
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from pathlib import Path
from typing import Any, AsyncIterator, Sequence

from langgraph.checkpoint.sqlite import SqliteSaver

from . import config


class ThreadedSqliteSaver(SqliteSaver):
    """SqliteSaver whose async API delegates to the sync API in a worker thread."""

    async def aget_tuple(self, config: Any) -> Any:
        return await asyncio.to_thread(self.get_tuple, config)

    async def alist(
        self,
        config: Any,
        *,
        filter: dict[str, Any] | None = None,
        before: Any = None,
        limit: int | None = None,
    ) -> AsyncIterator[Any]:
        # Materialize in the thread: SqliteSaver.list holds its lock while iterating.
        items = await asyncio.to_thread(lambda: list(self.list(config, filter=filter, before=before, limit=limit)))
        for item in items:
            yield item

    async def aput(self, config: Any, checkpoint: Any, metadata: Any, new_versions: Any) -> Any:
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config: Any, writes: Sequence[tuple[str, Any]], task_id: str, task_path: str = "") -> None:
        await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id: str) -> None:
        await asyncio.to_thread(self.delete_thread, thread_id)

    async def aget_delta_channel_history(self, *, config: Any, channels: Sequence[str]) -> Any:
        return await asyncio.to_thread(lambda: self.get_delta_channel_history(config=config, channels=channels))


def make_checkpointer(path: str | Path) -> ThreadedSqliteSaver:
    """New saver on its own connection (WAL, 30 s busy timeout). Tables are created now."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), check_same_thread=False, timeout=30)
    saver = ThreadedSqliteSaver(conn)
    with saver.lock:
        saver.setup()  # also sets PRAGMA journal_mode=WAL
    return saver


_lock = threading.Lock()
_saver: ThreadedSqliteSaver | None = None


def get_checkpointer() -> ThreadedSqliteSaver:
    """Process-wide checkpointer at api/.runtime/checkpoints.db (ready to use)."""
    global _saver
    with _lock:
        if _saver is None:
            _saver = make_checkpointer(config.checkpoint_db_path())
        return _saver


def close_checkpointer() -> None:
    """Close the singleton (scripts at exit). Graphs compiled with it stop working."""
    global _saver
    with _lock:
        if _saver is not None:
            try:
                _saver.conn.close()
            finally:
                _saver = None
