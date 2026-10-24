"""Provider-neutral LLM client (CONTRACTS §7): OpenAI + disk cache + deterministic mock.

Interface (sync and async variants behave identically)::

    obj, meta = llm.structured(task, system, user, Schema, mock=lambda: Schema(...))
    txt, meta = llm.text(task, system, user, mock=lambda: "...")
    obj, meta = await llm.astructured(task, system, user, Schema, mock=...)
    txt, meta = await llm.atext(task, system, user, mock=...)
    meta == {"source": "openai" | "cache" | "mock", "model": str | None, "ms": int}

Decision order for each call:
  1. DEMO_MODE=1            -> cache only; miss -> mock (never calls OpenAI)
  2. LLM_MODE=mock          -> mock
  3. no key or no model     -> mock
  4. LLM_MODE=openai        -> OpenAI (forced; still falls back to mock on any error)
     LLM_MODE=auto          -> OpenAI only if the startup key check passed, else mock
  For OpenAI-eligible calls the disk cache is read first (hit -> source "cache");
  a fresh OpenAI response is written to the cache. Mock results are never cached.

Guarantees:
  * Any OpenAI error / refusal / invalid output / timeout (20 s) -> mock. Only the
    error *class* is logged (SDK messages can contain key fragments).
  * Cache file: api/cache/llm/<task>/<sha256(model|task|system|user|schema)>.json
    holding the response only (never the prompt), written atomically.
  * No temperature is sent (some current models reject it). Requests use the
    Responses API with ``store=False``; structured output uses the SDK's Pydantic
    helper ``client.responses.parse(text_format=Schema)``.
  * Thread/async safe: single-flight key check, per-event-loop async clients,
    atomic cache writes, small circuit breaker after repeated connection errors.
  * Inside a LangGraph node, each call tags the node's SSE ``end`` event with its
    source automatically (see ``foothold.trace``).

Schema tips (OpenAI strict structured outputs): every field is sent as required;
for "may be null" use ``X | None`` with NO default; avoid defaults, numeric
``Field(ge=..)`` constraints and free-form ``dict[str, X]`` fields (strict mode
rejects them) - use ``list[KeyValue]`` models and ``Literal[...]`` enums instead;
validate ids against vocabularies (skills.json etc.) after the call. The mock must
return an instance of the schema (or a dict that validates) built from structured data.
Optional env OPENAI_REASONING_EFFORT (e.g. "low"/"none") is sent as reasoning.effort.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import tempfile
import threading
import time
import weakref
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, TypedDict, TypeVar

from pydantic import BaseModel

from . import config, trace

log = logging.getLogger("foothold.llm")

# Third-party HTTP/SDK loggers can print request details at DEBUG; keep them quiet.
for _name in ("openai", "httpx", "httpx2", "httpcore", "httpcore2"):
    logging.getLogger(_name).setLevel(logging.WARNING)

LLM_TIMEOUT_S = 20.0
KEY_CHECK_TIMEOUT_S = 10.0
BREAKER_THRESHOLD = 2  # consecutive connection/timeout failures before backing off
BREAKER_COOLDOWN_S = 60.0
CACHE_FORMAT = 1

Source = Literal["openai", "cache", "mock"]
M = TypeVar("M", bound=BaseModel)


class LLMMeta(TypedDict):
    source: Source
    model: str | None
    ms: int


class KeyStatus(TypedDict):
    key_present: bool
    key_ok: bool
    model: str | None
    error_class: str | None


class LLMNoOutput(Exception):
    """OpenAI returned no usable output (refusal, incomplete, empty)."""


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_TASK_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


def _schema_signature(schema: type[BaseModel] | None) -> str:
    if schema is None:
        return "text"
    try:
        js = schema.model_json_schema()
    except Exception:
        return f"schema:{getattr(schema, '__qualname__', repr(schema))}"
    return json.dumps(js, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def cache_key(
    model: str | None, task: str, system: str, user: str, schema: type[BaseModel] | None = None
) -> str:
    """sha256 over model, task, system, user and the schema's JSON schema ("text" for text calls).

    Fields are joined with the ASCII unit separator (not "|") so no field boundary is ambiguous.
    """
    h = hashlib.sha256()
    for part in (model or "", task, system, user, _schema_signature(schema)):
        h.update(str(part).encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()


def _task_dir(task: str) -> str:
    return (_TASK_SAFE.sub("_", task).strip("._") or "task")[:80]


def cache_path(task: str, key: str) -> Path:
    return config.cache_dir() / _task_dir(task) / f"{key}.json"


def _cache_load(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            entry = json.load(f)
    except FileNotFoundError:
        return None
    except Exception as exc:
        log.warning("llm cache entry unreadable (%s); ignoring", type(exc).__name__)
        return None
    if not isinstance(entry, dict) or "response" not in entry:
        return None
    return entry


def _cache_load_structured(path: Path, schema: type[M]) -> tuple[M, str | None] | None:
    entry = _cache_load(path)
    if entry is None or entry.get("kind") != "structured":
        return None
    try:
        return schema.model_validate(entry["response"]), entry.get("model")
    except Exception as exc:
        log.warning("llm cache entry does not match schema (%s); ignoring", type(exc).__name__)
        return None


def _cache_load_text(path: Path) -> tuple[str, str | None] | None:
    entry = _cache_load(path)
    if entry is None or entry.get("kind") != "text" or not isinstance(entry.get("response"), str):
        return None
    return entry["response"], entry.get("model")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON via temp file + os.replace (retries briefly: Windows/OneDrive can hold locks)."""
    tmp: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=str(path.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(6):
            try:
                os.replace(tmp, path)
                tmp = None
                break
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))
        if tmp is not None:
            log.warning("llm cache write skipped (target locked)")
    except Exception as exc:
        log.warning("llm cache write failed (%s)", type(exc).__name__)
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _cache_store(path: Path, *, task: str, model: str | None, kind: str, schema: str | None, response: Any) -> None:
    _atomic_write_json(
        path,
        {
            "format": CACHE_FORMAT,
            "kind": kind,
            "task": task,
            "model": model,
            "schema": schema,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "response": response,  # the response only; prompts are never stored
        },
    )


# ---------------------------------------------------------------------------
# Clients (lazy openai import so the mock path never depends on the SDK)
# ---------------------------------------------------------------------------

_client_lock = threading.Lock()
_sync_clients: dict[tuple[str, int], Any] = {}
_async_clients: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[tuple[str, int], Any]]" = (
    weakref.WeakKeyDictionary()
)
_client_factory: Callable[[str, str], Any] | None = None


def set_client_factory(factory: Callable[[str, str], Any] | None) -> None:
    """Test hook: ``factory(kind, api_key)`` returns an OpenAI-compatible client
    (``kind`` is "sync" or "async"). ``None`` restores the real SDK clients."""
    global _client_factory
    with _client_lock:
        _client_factory = factory
        _sync_clients.clear()
        _async_clients.clear()


def _client_cache_key(api_key: str) -> tuple[str, int]:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest(), id(_client_factory)


def _new_client(kind: str, api_key: str) -> Any:
    if _client_factory is not None:
        return _client_factory(kind, api_key)
    import openai

    cls = openai.OpenAI if kind == "sync" else openai.AsyncOpenAI
    return cls(api_key=api_key, timeout=LLM_TIMEOUT_S, max_retries=0)


def _sync_client(api_key: str) -> Any:
    key = _client_cache_key(api_key)
    with _client_lock:
        client = _sync_clients.get(key)
        if client is None:
            client = _sync_clients[key] = _new_client("sync", api_key)
        return client


def _async_client(api_key: str) -> Any:
    loop = asyncio.get_running_loop()  # async clients are bound to one event loop
    key = _client_cache_key(api_key)
    with _client_lock:
        per_loop = _async_clients.get(loop)
        if per_loop is None:
            per_loop = _async_clients[loop] = {}
        client = per_loop.get(key)
        if client is None:
            client = per_loop[key] = _new_client("async", api_key)
        return client


# ---------------------------------------------------------------------------
# Key check, mode resolution, circuit breaker
# ---------------------------------------------------------------------------

_key_lock = threading.Lock()
_key_status: dict[str, Any] | None = None  # KeyStatus + "_fp" (settings fingerprint)
_state_lock = threading.Lock()
_consecutive_failures = 0
_breaker_until = 0.0


def _fingerprint(s: config.Settings) -> str:
    raw = f"{s.api_key}\x1f{s.openai_model or ''}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _cached_key_status(s: config.Settings) -> dict[str, Any] | None:
    ks = _key_status
    return ks if ks is not None and ks.get("_fp") == _fingerprint(s) else None


def _public(ks: dict[str, Any]) -> KeyStatus:
    return {
        "key_present": bool(ks.get("key_present")),
        "key_ok": bool(ks.get("key_ok")),
        "model": ks.get("model"),
        "error_class": ks.get("error_class"),
    }


def check_key(timeout: float = KEY_CHECK_TIMEOUT_S) -> KeyStatus:
    """Cheap authenticated call (models.retrieve(model), or models.list() without a model)."""
    s = config.get_settings()
    out: KeyStatus = {"key_present": s.key_present, "key_ok": False, "model": s.openai_model, "error_class": None}
    if not s.key_present:
        return out
    try:
        client = _sync_client(s.api_key)
        if s.openai_model:
            client.models.retrieve(s.openai_model, timeout=timeout)
        else:
            client.models.list(timeout=timeout)
        out["key_ok"] = True
    except Exception as exc:
        out["error_class"] = type(exc).__name__
        log.warning("OpenAI key check failed (%s); LLM calls will use mock in auto mode", type(exc).__name__)
    return out


def ensure_key_checked(force: bool = False) -> KeyStatus:
    """Run :func:`check_key` once per (key, model) and cache it (thread-safe, single-flight).

    Without ``force``, nothing is sent in offline modes (DEMO_MODE=1 or LLM_MODE=mock)
    or without a key; the returned status then has ``key_ok=False`` and is not cached.
    """
    global _key_status
    s = config.get_settings()
    fp = _fingerprint(s)
    with _key_lock:
        ks = _key_status
        if not force and ks is not None and ks.get("_fp") == fp:
            return _public(ks)
        if not force and (s.demo_mode or s.llm_mode == "mock" or not s.key_present):
            return {"key_present": s.key_present, "key_ok": False, "model": s.openai_model, "error_class": None}
        result = check_key()
        _key_status = {**result, "_fp": fp}
        return result


def _mark_key_failed(error_class: str) -> None:
    global _key_status
    s = config.get_settings()
    with _key_lock:
        _key_status = {
            "key_present": s.key_present,
            "key_ok": False,
            "model": s.openai_model,
            "error_class": error_class,
            "_fp": _fingerprint(s),
        }


def _needs_key_check(s: config.Settings) -> bool:
    return (
        not s.demo_mode
        and s.llm_mode == "auto"
        and s.key_present
        and bool(s.openai_model)
        and _cached_key_status(s) is None
    )


def _plan(s: config.Settings) -> str:
    """'cache_only' (demo), 'openai' (cache first) or 'mock'. Never blocks."""
    if s.demo_mode:
        return "cache_only"
    if s.llm_mode == "mock" or not s.key_present or not s.openai_model:
        return "mock"
    if s.llm_mode == "openai":
        return "openai"
    ks = _cached_key_status(s)
    return "openai" if ks is not None and ks.get("key_ok") else "mock"


def _breaker_open() -> bool:
    return time.monotonic() < _breaker_until


def _on_success() -> None:
    global _consecutive_failures
    with _state_lock:
        _consecutive_failures = 0


def _on_failure(task: str, exc: BaseException) -> None:
    global _consecutive_failures, _breaker_until
    name = type(exc).__name__
    log.warning("llm task=%s OpenAI call failed (%s); using mock", task, name)
    mro = {c.__name__ for c in type(exc).__mro__}
    if mro & {"AuthenticationError", "PermissionDeniedError"}:
        _mark_key_failed(name)
    if mro & {"APIConnectionError", "TimeoutError", "InternalServerError", "RateLimitError", "TransportError", "TimeoutException"}:
        with _state_lock:
            _consecutive_failures += 1
            if _consecutive_failures >= BREAKER_THRESHOLD:
                _breaker_until = time.monotonic() + BREAKER_COOLDOWN_S
                _consecutive_failures = 0
                log.warning("llm: repeated OpenAI failures; serving cache/mock for %ds", int(BREAKER_COOLDOWN_S))


def resolve_mode() -> str:
    """Effective mode right now, without blocking: "openai", "mock" or "cache" (demo)."""
    s = config.get_settings()
    plan = _plan(s)
    if plan == "cache_only":
        return "cache"
    if plan == "openai" and _breaker_open():
        return "mock"
    return plan


def status() -> dict[str, Any]:
    """Non-blocking status for /health and /api/llm/status (never includes the key)."""
    s = config.get_settings()
    ks = _cached_key_status(s)
    return {
        "mode": resolve_mode(),
        "configured": s.llm_mode,
        "model": s.openai_model,
        "key_present": s.key_present,
        "key_ok": bool(ks and ks.get("key_ok")),
        "checked": ks is not None,
        "error_class": ks.get("error_class") if ks else None,
        "demo_mode": s.demo_mode,
        "breaker_open": _breaker_open(),
    }


def reset_state() -> None:
    """Forget the key check, breaker and cached clients (tests, or after editing .env)."""
    global _key_status, _consecutive_failures, _breaker_until
    with _key_lock:
        _key_status = None
    with _state_lock:
        _consecutive_failures = 0
        _breaker_until = 0.0
    with _client_lock:
        for client in _sync_clients.values():
            try:
                client.close()
            except Exception:
                pass
        _sync_clients.clear()
        _async_clients.clear()


# ---------------------------------------------------------------------------
# OpenAI calls (return None on any failure)
# ---------------------------------------------------------------------------


def _request_kwargs(s: config.Settings, system: str, user: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"model": s.openai_model, "instructions": system, "input": user, "store": False}
    if s.reasoning_effort:
        kwargs["reasoning"] = {"effort": s.reasoning_effort}
    return kwargs


def _parsed_or_raise(resp: Any, schema: type[M]) -> M:
    parsed = resp.output_parsed
    if parsed is None:
        raise LLMNoOutput("no parsed output")
    return parsed if isinstance(parsed, schema) else schema.model_validate(parsed)


def _text_or_raise(resp: Any) -> str:
    out = resp.output_text or ""
    if not out.strip():
        raise LLMNoOutput("empty text")
    return out


def _call_structured(s: config.Settings, task: str, system: str, user: str, schema: type[M]) -> M | None:
    try:
        client = _sync_client(s.api_key)
        obj = _parsed_or_raise(client.responses.parse(text_format=schema, **_request_kwargs(s, system, user)), schema)
    except Exception as exc:
        _on_failure(task, exc)
        return None
    _on_success()
    return obj


def _call_text(s: config.Settings, task: str, system: str, user: str) -> str | None:
    try:
        client = _sync_client(s.api_key)
        out = _text_or_raise(client.responses.create(**_request_kwargs(s, system, user)))
    except Exception as exc:
        _on_failure(task, exc)
        return None
    _on_success()
    return out


async def _acall_structured(s: config.Settings, task: str, system: str, user: str, schema: type[M]) -> M | None:
    try:
        client = _async_client(s.api_key)
        resp = await asyncio.wait_for(
            client.responses.parse(text_format=schema, **_request_kwargs(s, system, user)), LLM_TIMEOUT_S + 1.0
        )
        obj = _parsed_or_raise(resp, schema)
    except Exception as exc:  # CancelledError is a BaseException and propagates
        _on_failure(task, exc)
        return None
    _on_success()
    return obj


async def _acall_text(s: config.Settings, task: str, system: str, user: str) -> str | None:
    try:
        client = _async_client(s.api_key)
        resp = await asyncio.wait_for(client.responses.create(**_request_kwargs(s, system, user)), LLM_TIMEOUT_S + 1.0)
        out = _text_or_raise(resp)
    except Exception as exc:
        _on_failure(task, exc)
        return None
    _on_success()
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _finish(source: Source, model: str | None, t0: float) -> LLMMeta:
    trace.note(llm=source)
    return {"source": source, "model": model, "ms": int(round((time.perf_counter() - t0) * 1000))}


def _mock_structured(schema: type[M], mock: Callable[[], Any]) -> M:
    value = mock()
    if isinstance(value, schema):
        return value
    if isinstance(value, BaseModel):
        return schema.model_validate(value.model_dump())
    return schema.model_validate(value)


def structured(
    task: str, system: str, user: str, schema: type[M], mock: Callable[[], M | dict[str, Any]]
) -> tuple[M, LLMMeta]:
    """Structured output validated as ``schema``; falls back to ``mock()``."""
    t0 = time.perf_counter()
    s = config.get_settings()
    if _needs_key_check(s):
        ensure_key_checked()
    plan = _plan(s)
    if plan != "mock":
        path = cache_path(task, cache_key(s.openai_model, task, system, user, schema))
        hit = _cache_load_structured(path, schema)
        if hit is not None:
            return hit[0], _finish("cache", hit[1], t0)
        if plan == "openai" and not _breaker_open():
            obj = _call_structured(s, task, system, user, schema)
            if obj is not None:
                _cache_store(
                    path, task=task, model=s.openai_model, kind="structured", schema=schema.__name__,
                    response=obj.model_dump(mode="json"),
                )
                return obj, _finish("openai", s.openai_model, t0)
    return _mock_structured(schema, mock), _finish("mock", None, t0)


def text(task: str, system: str, user: str, mock: Callable[[], str]) -> tuple[str, LLMMeta]:
    """Plain text; falls back to ``mock()``."""
    t0 = time.perf_counter()
    s = config.get_settings()
    if _needs_key_check(s):
        ensure_key_checked()
    plan = _plan(s)
    if plan != "mock":
        path = cache_path(task, cache_key(s.openai_model, task, system, user, None))
        hit = _cache_load_text(path)
        if hit is not None:
            return hit[0], _finish("cache", hit[1], t0)
        if plan == "openai" and not _breaker_open():
            out = _call_text(s, task, system, user)
            if out is not None:
                _cache_store(path, task=task, model=s.openai_model, kind="text", schema=None, response=out)
                return out, _finish("openai", s.openai_model, t0)
    return str(mock()), _finish("mock", None, t0)


async def astructured(
    task: str, system: str, user: str, schema: type[M], mock: Callable[[], M | dict[str, Any]]
) -> tuple[M, LLMMeta]:
    """Async :func:`structured` (never blocks the event loop on I/O)."""
    t0 = time.perf_counter()
    s = config.get_settings()
    if _needs_key_check(s):
        await asyncio.to_thread(ensure_key_checked)
    plan = _plan(s)
    if plan != "mock":
        path = cache_path(task, cache_key(s.openai_model, task, system, user, schema))
        hit = await asyncio.to_thread(_cache_load_structured, path, schema)
        if hit is not None:
            return hit[0], _finish("cache", hit[1], t0)
        if plan == "openai" and not _breaker_open():
            obj = await _acall_structured(s, task, system, user, schema)
            if obj is not None:
                await asyncio.to_thread(
                    lambda: _cache_store(
                        path, task=task, model=s.openai_model, kind="structured", schema=schema.__name__,
                        response=obj.model_dump(mode="json"),
                    )
                )
                return obj, _finish("openai", s.openai_model, t0)
    return _mock_structured(schema, mock), _finish("mock", None, t0)


async def atext(task: str, system: str, user: str, mock: Callable[[], str]) -> tuple[str, LLMMeta]:
    """Async :func:`text`."""
    t0 = time.perf_counter()
    s = config.get_settings()
    if _needs_key_check(s):
        await asyncio.to_thread(ensure_key_checked)
    plan = _plan(s)
    if plan != "mock":
        path = cache_path(task, cache_key(s.openai_model, task, system, user, None))
        hit = await asyncio.to_thread(_cache_load_text, path)
        if hit is not None:
            return hit[0], _finish("cache", hit[1], t0)
        if plan == "openai" and not _breaker_open():
            out = await _acall_text(s, task, system, user)
            if out is not None:
                await asyncio.to_thread(
                    lambda: _cache_store(path, task=task, model=s.openai_model, kind="text", schema=None, response=out)
                )
                return out, _finish("openai", s.openai_model, t0)
    return str(mock()), _finish("mock", None, t0)
