"""Any-career search (public).

GET /api/careers/search?q=dental&limit=8 -> [{onet_soc, title, career_id | null}]

Searches every O*NET 31.0 occupation with complete Work Styles data (foothold.occupations_index).
``career_id`` is set for the 8 core Foothold careers (authored workdays); any other result can be
played with POST /api/sim/start {onet_soc}, which generates its moments on the fly.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Query

from foothold import occupations_index

router = APIRouter(prefix="/api/careers", tags=["careers"])


@router.get("/search")
async def search(q: str = Query(default="", max_length=80), limit: int = Query(default=8, ge=1, le=25)) -> list[dict[str, Any]]:
    return await asyncio.to_thread(occupations_index.search, q, limit)
