"""Meta endpoints: static data for the UI, ML metrics, LLM status (CONTRACTS §9).

GET /api/meta/{careers|traits|skills|courses|programs|sources|personas}
GET /api/metrics      -> ml/artifacts/metrics.json or {} (UI shows "not trained yet")
GET /api/llm/status   -> effective LLM mode + key check result (never the key)
GET /api/meta/places  -> {places:[{id,name,county,lat,lon}], campuses:[...], drive_assumption}
GET /api/places/near?place_id= | lat=&lon= [&limit=] -> nearest campuses + their programs + circles
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Literal

from fastapi import APIRouter, HTTPException, Query, status

from foothold import data, llm, places, planner
from foothold.auth import OptionalAccount

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


@router.get("/meta/places")
def get_places() -> dict[str, Any]:
    """Central Valley places (approximate city centroids) and campus locations for the location picker."""
    return {"places": places.PLACES, "campuses": places.CAMPUSES, "drive_assumption": places.DRIVE_ASSUMPTION,
            "approximate": True}


@router.get("/places/near")
def places_near(
    account: OptionalAccount,
    place_id: str | None = Query(None, max_length=40),
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    limit: int = Query(8, ge=1, le=20),
) -> dict[str, Any]:
    """Nearest campuses/training providers (+ the programs they run and circles) from a place, lat/lon,
    or the signed-in user's saved place."""
    origin = places.origin_from(place_id, lat, lon)
    if origin is None and account is not None:
        from foothold import profiles

        origin = profiles.origin_for(account)
    if origin is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Pick a place or share a location.")
    by_campus: dict[str, list[dict[str, Any]]] = {}
    for p in planner.parsed_programs():
        campus = places.program_campus(p)
        if campus:
            by_campus.setdefault(campus["id"], []).append(
                {"id": p.id, "name": p.name, "career_id": p.career_id, "route_type": p.route_type,
                 "credential": p.credential, "url": p.url})
    providers = []
    for c in places.nearest(origin, places.CAMPUSES, limit):
        providers.append({**c, "programs": by_campus.get(c["id"], [])})
    programs = sorted(
        [{**pr, "campus": c["name"], "campus_id": c["id"], "distance_km": c["distance_km"],
          "drive_minutes": c["drive_minutes"]} for c in providers for pr in c["programs"]],
        key=lambda x: x["distance_km"],
    )
    near_places = [p for p in places.nearest(origin, places.PLACES, 6)]
    circles = [{"id": c.get("id"), "name": c.get("name"), "meets": "online", "nearest_meetup": providers[0]["name"]
                if providers else None} for c in data.circles() if isinstance(c, dict) and c.get("id")]
    return {"origin": origin, "providers": providers, "programs": programs, "places": near_places,
            "circles": circles, "drive_assumption": places.DRIVE_ASSUMPTION, "approximate": True}


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
