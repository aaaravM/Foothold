"""Foothold API (FastAPI). Run: ``uvicorn main:app --app-dir api --reload --port 8000``.

* CORS: http://localhost:<port> and http://127.0.0.1:<port> (CONTRACTS §2).
* Every module in ``foothold/routes/`` that exposes ``router`` is included. A route
  module that fails to import is logged (module + error class) and listed in
  ``GET /health`` as ``route_errors``; the rest of the app keeps serving.
* Startup: ``db.init_db()`` and one background LLM key check (10 s timeout,
  cached). ``GET /health`` never blocks on it.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import logging
import pkgutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

API_DIR = Path(__file__).resolve().parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from fastapi import APIRouter, FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from foothold import config, db, llm  # noqa: E402

log = logging.getLogger("foothold")
CORS_ORIGIN_REGEX = (
    r"http://(localhost|127\.0\.0\.1)(:\d+)?"
    r"|https://[a-z0-9-]+(--[a-z0-9-]+)?\.netlify\.app"  # Netlify static build (+ deploy previews)
    r"|https://[a-z0-9-]+\.trycloudflare\.com"  # quick tunnel serving the same origin
    r"|https://[a-z0-9-]+\.lhr\.life"  # localhost.run fallback tunnel
)
ROUTES_PACKAGE = "foothold.routes"


def _setup_logging() -> None:
    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)


_setup_logging()


def _describe_error(exc: BaseException) -> str:
    """Error class plus non-sensitive location info (never the exception message)."""
    name = type(exc).__name__
    if isinstance(exc, SyntaxError) and exc.filename:
        return f"{name} at {Path(exc.filename).name}:{exc.lineno}"
    if isinstance(exc, ImportError) and exc.name:
        return f"{name} ({exc.name})"
    return name


def include_routes(app: FastAPI, package: str = ROUTES_PACKAGE) -> tuple[list[str], dict[str, str]]:
    """Import every module in ``package`` and include its ``router``. Never raises."""
    loaded: list[str] = []
    errors: dict[str, str] = {}
    try:
        pkg = importlib.import_module(package)
    except Exception as exc:
        log.warning("routes package %s failed to import: %s", package, type(exc).__name__)
        return loaded, {package: _describe_error(exc)}
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda m: m.name):
        if info.name.startswith("_"):
            continue
        modname = f"{package}.{info.name}"
        try:
            module = importlib.import_module(modname)
            router = getattr(module, "router", None)
            if router is None:
                continue
            if not isinstance(router, APIRouter):
                raise TypeError("router is not an APIRouter")
            app.include_router(router)
        except (Exception, SystemExit) as exc:
            errors[info.name] = _describe_error(exc)
            log.warning("route module %s skipped: %s", modname, type(exc).__name__,
                        exc_info=config.get_settings().debug)
            continue
        loaded.append(info.name)
    if loaded:
        log.info("routes loaded: %s", ", ".join(loaded))
    return loaded, errors


async def _background_key_check() -> None:
    try:
        await asyncio.wait_for(asyncio.to_thread(llm.ensure_key_checked), timeout=llm.KEY_CHECK_TIMEOUT_S + 2)
        st = llm.status()
        log.info("LLM mode=%s (configured=%s, key_present=%s, key_ok=%s)",
                 st["mode"], st["configured"], st["key_present"], st["key_ok"])
    except Exception as exc:
        log.warning("LLM key check did not complete: %s", type(exc).__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        await asyncio.to_thread(db.init_db)
    except Exception as exc:  # keep serving; db routes will report errors themselves
        log.warning("init_db failed: %s", type(exc).__name__)
    task = asyncio.create_task(_background_key_check())
    db_task = asyncio.create_task(asyncio.to_thread(db.remote_startup))  # Supabase probe/sync, never blocks startup
    try:
        yield
    finally:
        task.cancel()
        db_task.cancel()
        with contextlib.suppress(BaseException):
            await task


def create_app(routes_package: str = ROUTES_PACKAGE) -> FastAPI:
    app = FastAPI(
        title="Foothold API",
        version="0.1.0",
        description="Career exploration for California's Central Valley. All people shown are fictional.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=CORS_ORIGIN_REGEX,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )
    loaded, errors = include_routes(app, routes_package)
    app.state.routes_loaded = loaded
    app.state.route_errors = errors

    @app.get("/health", tags=["meta"])
    def health(request: Request) -> dict[str, Any]:
        st = llm.status()
        return {
            "ok": True,
            "llm": {
                "mode": st["mode"],
                "model": st["model"],
                "key_present": st["key_present"],
                "key_ok": st["key_ok"],
                "configured": st["configured"],
                "checked": st["checked"],
                "error_class": st["error_class"],
            },
            "demo_mode": st["demo_mode"],
            "db": db.backend_status(),
            "route_errors": dict(request.app.state.route_errors),
            "routes": list(request.app.state.routes_loaded),
        }

    return app


app = create_app()
