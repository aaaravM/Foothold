"""Central Valley places, campus locations and distance helpers.

Coordinates are APPROXIMATE: city centroids for places, and the main campus (rounded to
~0.001 deg) for providers. Good enough for "which campus is nearer" and rough drive times,
not for navigation.

Drive-time assumption (documented for the UI): road distance = straight-line distance x 1.2; the first
10 road km at 40 km/h (city streets), the rest at 90 km/h (highway), plus 5 minutes to park and walk.
"""

from __future__ import annotations

import math
from typing import Any, Iterable

ROAD_FACTOR = 1.2
CITY_KM = 10.0
CITY_SPEED_KMH = 40.0
HIGHWAY_SPEED_KMH = 90.0
PARK_WALK_MIN = 5
DRIVE_ASSUMPTION = (
    f"Approximate drive time: straight-line distance x {ROAD_FACTOR}; first {CITY_KM:g} km at {CITY_SPEED_KMH:g} km/h, "
    f"the rest at {HIGHWAY_SPEED_KMH:g} km/h, plus {PARK_WALK_MIN} min to park and walk."
)

# id, name, county, lat, lon
_PLACES: tuple[tuple[str, str, str, float, float], ...] = (
    ("stockton", "Stockton", "San Joaquin", 37.9577, -121.2908),
    ("lodi", "Lodi", "San Joaquin", 38.1302, -121.2724),
    ("tracy", "Tracy", "San Joaquin", 37.7397, -121.4252),
    ("manteca", "Manteca", "San Joaquin", 37.7974, -121.2161),
    ("modesto", "Modesto", "Stanislaus", 37.6391, -120.9969),
    ("turlock", "Turlock", "Stanislaus", 37.4947, -120.8466),
    ("merced", "Merced", "Merced", 37.3022, -120.4830),
    ("los_banos", "Los Banos", "Merced", 37.0583, -120.8499),
    ("madera", "Madera", "Madera", 36.9613, -120.0607),
    ("fresno", "Fresno", "Fresno", 36.7378, -119.7871),
    ("hanford", "Hanford", "Kings", 36.3275, -119.6457),
    ("visalia", "Visalia", "Tulare", 36.3302, -119.2921),
    ("porterville", "Porterville", "Tulare", 36.0652, -119.0168),
    ("bakersfield", "Bakersfield", "Kern", 35.3733, -119.0187),
    ("sacramento", "Sacramento", "Sacramento", 38.5816, -121.4944),
    ("elk_grove", "Elk Grove", "Sacramento", 38.4088, -121.3716),
)

PLACES: list[dict[str, Any]] = [
    {"id": i, "name": n, "county": c, "lat": la, "lon": lo, "approximate": True} for i, n, c, la, lo in _PLACES
]
_PLACE_BY_ID = {p["id"]: p for p in PLACES}

# id, name, kind, place_id, lat, lon, aliases (lower-case substrings matched against provider/campus text)
_CAMPUSES: tuple[tuple[str, str, str, str, float, float, tuple[str, ...]], ...] = (
    ("delta", "San Joaquin Delta College", "community_college", "stockton", 37.9990, -121.3170,
     ("san joaquin delta", "delta college")),
    ("mjc_west", "Modesto Junior College (West Campus)", "community_college", "modesto", 37.6289, -121.0393,
     ("mjc west",)),
    ("mjc", "Modesto Junior College", "community_college", "modesto", 37.6505, -120.9900,
     ("modesto junior", "mjc")),
    ("sjeti", "San Joaquin & Calaveras Electrical Training (SJETI)", "apprenticeship", "stockton", 37.9530, -121.2700,
     ("sjeti", "electrical j.a.t.c", "electrical jatc")),
    ("merced_college", "Merced College", "community_college", "merced", 37.3337, -120.4740, ("merced college",)),
    ("fresno_city", "Fresno City College", "community_college", "fresno", 36.7668, -119.7965, ("fresno city",)),
    ("reedley", "Reedley College", "community_college", "fresno", 36.6100, -119.4470, ("reedley",)),
    ("cos", "College of the Sequoias", "community_college", "visalia", 36.3233, -119.3135, ("sequoias",)),
    ("bakersfield_college", "Bakersfield College", "community_college", "bakersfield", 35.4105, -118.9714,
     ("bakersfield college",)),
    ("west_hills_lemoore", "West Hills College Lemoore", "community_college", "hanford", 36.3060, -119.8040,
     ("west hills",)),
    ("csu_stanislaus", "CSU Stanislaus", "university", "turlock", 37.5253, -120.8557, ("stanislaus state", "csu stanislaus")),
    ("uc_merced", "UC Merced", "university", "merced", 37.3660, -120.4240, ("uc merced", "ucm")),
    ("fresno_state", "Fresno State", "university", "fresno", 36.8134, -119.7483, ("fresno state", "csu fresno")),
    ("sac_state", "Sacramento State", "university", "sacramento", 38.5610, -121.4240, ("sacramento state", "sac state")),
)

CAMPUSES: list[dict[str, Any]] = [
    {"id": i, "name": n, "kind": k, "place_id": p, "lat": la, "lon": lo, "approximate": True}
    for i, n, k, p, la, lo, _ in _CAMPUSES
]
_ALIASES = [(a, c) for (i, _n, _k, _p, _la, _lo, al), c in zip(_CAMPUSES, CAMPUSES) for a in al]


def place(place_id: str | None) -> dict[str, Any] | None:
    return _PLACE_BY_ID.get(str(place_id or "").strip().lower())


def place_from_text(text: Any) -> dict[str, Any] | None:
    """'Stockton (San Joaquin County)' / 'Stockton area' -> the Stockton place (first name found)."""
    if not isinstance(text, str) or not text:
        return None
    low = text.lower()
    hits = [(low.find(p["name"].lower()), p) for p in PLACES if p["name"].lower() in low]
    return min(hits, key=lambda h: h[0])[1] if hits else None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def drive_minutes(km: float) -> int:
    road = max(0.0, km) * ROAD_FACTOR
    city = min(road, CITY_KM)
    return int(round(city / CITY_SPEED_KMH * 60 + (road - city) / HIGHWAY_SPEED_KMH * 60 + PARK_WALK_MIN))


def valid_latlon(lat: Any, lon: Any) -> bool:
    try:
        la, lo = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    return -90 <= la <= 90 and -180 <= lo <= 180 and math.isfinite(la) and math.isfinite(lo)


def origin_from(place_id: str | None = None, lat: Any = None, lon: Any = None) -> dict[str, Any] | None:
    """{lat, lon, place_id, name} from explicit lat/lon (wins) or a place id; None when neither is usable."""
    p = place(place_id)
    if valid_latlon(lat, lon):
        return {"lat": float(lat), "lon": float(lon), "place_id": p["id"] if p else None,
                "name": p["name"] if p else "Your location"}
    if p:
        return {"lat": p["lat"], "lon": p["lon"], "place_id": p["id"], "name": p["name"]}
    return None


def campus_for_text(*texts: Any) -> dict[str, Any] | None:
    """Campus whose alias appears in any of the texts (provider name, section campus)."""
    for t in texts:
        if not isinstance(t, str) or not t:
            continue
        low = t.lower()
        for alias, campus in _ALIASES:
            if alias in low:
                return campus
    return None


def leg(origin: dict[str, Any], lat: float, lon: float) -> dict[str, Any]:
    km = haversine_km(origin["lat"], origin["lon"], lat, lon)
    return {"distance_km": round(km, 1), "drive_minutes": drive_minutes(km)}


def program_campus(program: Any) -> dict[str, Any] | None:
    """Main campus for a planner Program (most common on-campus section campus, else the provider)."""
    counts: dict[str, int] = {}
    for step in getattr(program, "steps", ()) or ():
        for sec in getattr(step, "sections", ()) or ():
            if getattr(sec, "on_campus", False) and getattr(sec, "campus", None):
                counts[sec.campus] = counts.get(sec.campus, 0) + 1
    for name in sorted(counts, key=lambda n: -counts[n]):
        hit = campus_for_text(name)
        if hit:
            return hit
    return campus_for_text(getattr(program, "provider", None))


def program_commute(program: Any, origin: dict[str, Any] | None) -> dict[str, Any] | None:
    """{campus_id, campus, distance_km, minutes_one_way} for a program from an origin, or None."""
    if not origin:
        return None
    campus = program_campus(program)
    if not campus:
        return None
    d = leg(origin, campus["lat"], campus["lon"])
    return {"campus_id": campus["id"], "campus": campus["name"], "distance_km": d["distance_km"],
            "minutes_one_way": d["drive_minutes"], "approximate": True}


def nearest(origin: dict[str, Any], items: Iterable[dict[str, Any]], limit: int | None = None) -> list[dict[str, Any]]:
    out = [{**it, **leg(origin, it["lat"], it["lon"])} for it in items]
    out.sort(key=lambda x: x["distance_km"])
    return out[:limit] if limit else out


__all__ = [
    "CAMPUSES", "DRIVE_ASSUMPTION", "PLACES", "campus_for_text", "drive_minutes", "haversine_km", "leg", "nearest",
    "origin_from", "place", "place_from_text", "program_campus", "program_commute", "valid_latlon",
]
