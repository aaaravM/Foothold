"""Meta endpoints: static data for the UI, ML metrics, LLM status (CONTRACTS §9).

GET /api/meta/{careers|traits|skills|courses|programs|sources|personas}
GET /api/metrics      -> ml/artifacts/metrics.json or {} (UI shows "not trained yet")
GET /api/llm/status   -> effective LLM mode + key check result (never the key)
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Literal

from fastapi import APIRouter

from foothold import data, llm

router = APIRouter(prefix="/api", tags=["meta"])

MetaName = Literal["careers", "traits", "skills", "courses", "programs", "sources", "personas"]

_LOADERS: dict[str, Callable[[], Any]] = {
    "careers": data.careers,
    "traits": data.traits,
    "skills": data.skills,
    "courses": data.courses,
    "programs": data.programs,
    "sources": data.sources,
    "personas": data.personas,
}


@router.get("/meta/{name}")
def get_meta(name: MetaName) -> Any:
    """Contents of data/processed/<name>.json (empty list/object if not built yet)."""
    return _LOADERS[name]()


@router.get("/metrics")
def get_metrics() -> dict[str, Any]:
    return data.metrics()


@router.get("/llm/status")
async def llm_status(recheck: bool = False) -> dict[str, Any]:
    """``?recheck=true`` re-runs the key check (one cheap authenticated call, 10 s timeout)."""
    if recheck:
        await asyncio.to_thread(llm.ensure_key_checked, True)
    return llm.status()
