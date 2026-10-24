"""Learn: learner graph sample + recommendations (CONTRACTS section 9). All learners FICTIONAL.

GET /api/graph/sample                       public: {nodes, links, stats} ~60 synthetic learners + neighborhoods
                                            + target careers; positions from networkx spring_layout (seed 7), cached.
GET /api/graph/recommend/{learner_id}?model=gnn|mf|pop&k=10
                                            learner_id = persona/learner id, or "me" (from the token).
                                            -> {learner_id, model_requested, model_used, trained, note, items:[...]}
    item = {kind: course|job, id, title, score, base_score, demand_boost|null, path:[{type,id,label}], provider?, url?, cost_usd?}
Employer-demand boosts come from the aggregate skill_demand table (employer gap reports, min group 5) and are
labeled on each item; the base model score is always shown next to the boosted one.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from foothold import auth, consent, data
from foothold.auth import OptionalAccount

log = logging.getLogger("foothold.graph")

router = APIRouter(prefix="/api/graph", tags=["graph"])

SAMPLE_SIZE = 60
SEED = 7
DEMAND_WEIGHT = 0.15

_cache_lock = threading.Lock()
_sample_cache: dict[str, Any] = {}


def _first(rec: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        v = rec.get(k)
        if v not in (None, "", [], {}):
            return v
    for nest in ("profile", "blind", "public", "hidden", "private"):
        sub = rec.get(nest)
        if isinstance(sub, dict):
            for k in keys:
                v = sub.get(k)
                if v not in (None, "", [], {}):
                    return v
    return None


def _label(v: Any) -> str | None:
    if isinstance(v, dict):
        v = v.get("label") or v.get("name") or v.get("neighborhood") or v.get("city")
    return " ".join(str(v).split())[:48] if v not in (None, "") else None


def _skill_ids(rec: dict[str, Any]) -> list[str]:
    raw = _first(rec, "skills", "demonstrated_skills", "skill_ids", "current_skills")
    out: list[str] = []
    if isinstance(raw, dict):
        out = [k for k in raw]
    elif isinstance(raw, list):
        for x in raw:
            sid = x if isinstance(x, str) else (x.get("id") or x.get("skill_id")) if isinstance(x, dict) else None
            if isinstance(sid, str):
                out.append(sid)
    valid = data.skill_ids()
    return [s for s in dict.fromkeys(out) if s in valid]


def _career(rec: dict[str, Any]) -> str | None:
    v = _first(rec, "target_career", "career_id", "target_career_id", "career", "interest_career")
    if isinstance(v, dict):
        v = v.get("career_id") or v.get("id")
    if isinstance(v, list):
        v = v[0] if v else None
    if v is None:
        prog = _first(rec, "pathway_progress", "pathway")
        v = prog.get("career_id") if isinstance(prog, dict) else None
    return v if isinstance(v, str) and v in data.career_ids() else None


def _learner_records() -> tuple[list[dict[str, Any]], str]:
    items = [x for x in data.learners() if isinstance(x, dict) and (x.get("id") or x.get("learner_id"))]
    if items:
        return items, "synthetic/learners.json"
    items = [x for x in data.talent_pool() if isinstance(x, dict) and auth.card_id(x)]
    return items, "synthetic/talent_pool.json"


def _build_sample() -> dict[str, Any]:
    import networkx as nx

    records, source = _learner_records()
    if not records:
        return {"available": False, "reason": "synthetic learners not generated yet", "nodes": [], "links": [],
                "provenance": "SYNTHETIC"}
    records = sorted(records, key=lambda r: str(r.get("id") or r.get("learner_id")))[:SAMPLE_SIZE]
    if source != "synthetic/talent_pool.json":  # add the demo personas' cards so "you" appear in the graph
        records += [c for c in data.talent_pool() if isinstance(c, dict) and auth._card_persona(c)]
    G = nx.Graph()
    titles = {c["id"]: c.get("title", c["id"]) for c in data.careers()}
    nodes: dict[str, dict[str, Any]] = {}
    links: list[dict[str, Any]] = []
    for r in records:
        rid = str(r.get("id") or r.get("learner_id"))
        lid = f"learner:{rid}"
        persona = auth._card_persona(r)
        skills = _skill_ids(r)
        if persona:
            lid = f"learner:{persona}"
        # public endpoint: no names (the UI shows "You" when learner_id matches the signed-in persona)
        nodes[lid] = {"id": lid, "type": "learner",
                      "label": "Demo learner" if persona else f"Learner {len(nodes) + 1}",
                      "learner_id": persona or rid, "persona": bool(persona), "skills": len(skills)}
        G.add_node(lid)
        hood = _label(_first(r, "neighborhood", "region", "commute_region", "city", "area"))
        if hood:
            hid = f"hood:{hood.lower().replace(' ', '_')}"
            nodes.setdefault(hid, {"id": hid, "type": "neighborhood", "label": hood})
            G.add_edge(lid, hid, w=1.0)
            links.append({"source": lid, "target": hid, "type": "lives_in"})
        career = _career(r)
        if career:
            cid = f"career:{career}"
            nodes.setdefault(cid, {"id": cid, "type": "career", "label": titles.get(career, career)})
            G.add_edge(lid, cid, w=0.6)
            links.append({"source": lid, "target": cid, "type": "exploring"})
    pos = nx.spring_layout(G, seed=SEED, weight="w", iterations=80) if len(G) else {}
    out_nodes = []
    for nid, n in nodes.items():
        x, y = pos.get(nid, (0.0, 0.0))
        out_nodes.append({**n, "x": round(float(x), 4), "y": round(float(y), 4), "degree": int(G.degree(nid)) if nid in G else 0})
    counts = {t: sum(1 for n in out_nodes if n["type"] == t) for t in ("learner", "neighborhood", "career")}
    return {"available": True, "nodes": out_nodes, "links": links, "stats": counts, "source": source,
            "layout": f"networkx spring_layout seed={SEED}", "provenance": "SYNTHETIC", "fictional": True}


@router.get("/sample")
async def sample():
    records, source = _learner_records()
    key = f"{source}:{len(records)}"
    with _cache_lock:
        hit = _sample_cache.get(key)
    if hit is None:
        hit = await asyncio.to_thread(_build_sample)
        if hit.get("available"):
            with _cache_lock:
                _sample_cache.clear()
                _sample_cache[key] = hit
    return hit


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def _learner_profile(learner_id: str) -> dict[str, Any] | None:
    for getter in (data.get_learner, data.get_persona):
        try:
            rec = getter(learner_id)
        except Exception:  # noqa: BLE001
            rec = None
        if rec:
            card = auth.candidate_for_persona(learner_id) or {}
            skills = _skill_ids(rec) or _skill_ids(card)
            return {"id": learner_id, "skills": skills, "career_id": _career(rec) or _career(card)}
    card = auth.candidate_for_persona(learner_id)
    if card is None:
        card = next((c for c in data.talent_pool() if isinstance(c, dict) and auth.card_id(c) == learner_id), None)
    if card:
        return {"id": learner_id, "skills": _skill_ids(card), "career_id": _career(card)}
    if auth.get_account_by_persona(learner_id):
        return {"id": learner_id, "skills": [], "career_id": None}
    return None


def _model_recs(learner_id: str, model: str, k: int) -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
    try:
        from foothold import recommender  # built by the ML slice
    except Exception:
        return None, {"note": "trained recommender not available yet"}
    fn = getattr(recommender, "recommend", None)
    if not callable(fn):
        return None, {"note": "recommender has no recommend() yet"}
    try:
        res = fn(learner_id, model=model, k=k)
    except Exception as exc:  # noqa: BLE001
        log.warning("recommender failed (%s)", type(exc).__name__)
        return None, {"note": f"recommender failed ({type(exc).__name__})"}
    meta: dict[str, Any] = {}
    items = res
    if isinstance(res, dict):
        items = res.get("items") or res.get("recommendations") or []
        meta = {k2: v for k2, v in res.items() if k2 not in ("items", "recommendations")}
    if not isinstance(items, list):
        return None, {"note": "recommender returned no items"}
    return [i for i in items if isinstance(i, dict)], meta


def _baseline(profile: dict[str, Any], k: int) -> list[dict[str, Any]]:
    """Transparent skill-gap baseline: courses/jobs covering skills the target career needs and the learner lacks."""
    career = data.get_career(profile.get("career_id") or "") if profile.get("career_id") else None
    have = set(profile.get("skills") or [])
    need = [s for s in (career or {}).get("skills", []) if s not in have]
    names = {s["id"]: s.get("name", s["id"]) for s in data.skills()}
    out: list[dict[str, Any]] = []
    target = set(need) if need else set()
    for c in data.courses():
        cover = [s for s in c.get("skills", []) if s in target] if target else []
        if not cover:
            continue
        out.append({
            "kind": "course", "id": c["id"], "title": c.get("title"), "provider": c.get("provider"), "url": c.get("url"),
            "cost_usd": c.get("cost_usd"), "skills": c.get("skills", []), "base_score": round(len(cover) / max(1, len(need)), 4),
            "path": [{"type": "learner", "id": profile["id"], "label": "You"},
                     {"type": "career", "id": career["id"], "label": career.get("title")},
                     {"type": "skill", "id": cover[0], "label": names.get(cover[0], cover[0])},
                     {"type": "course", "id": c["id"], "label": c.get("title")}],
        })
    out.sort(key=lambda x: (-x["base_score"], x.get("cost_usd") or 0, x["id"]))
    jobs = []
    for j in (x for x in _jobs() if career and x.get("career_id") == career["id"]):
        req = j.get("required_skills") or []
        frac = (sum(1 for s in req if s in have) / len(req)) if req else 0.0
        jobs.append({
            "kind": "job", "id": j["id"], "title": j.get("title"), "skills": req, "level": j.get("level"),
            "base_score": round(frac, 4),
            "path": [{"type": "learner", "id": profile["id"], "label": "You"},
                     {"type": "career", "id": career["id"], "label": career.get("title")},
                     {"type": "job", "id": j["id"], "label": j.get("title")}],
        })
    jobs.sort(key=lambda x: (-x["base_score"], x["id"]))
    return out[: max(1, k - 3)] + jobs[:3]


def _jobs() -> list[dict[str, Any]]:
    raw = data._processed("jobs.json", [])
    return data._as_list(raw, "jobs")


def _apply_demand(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    demand = {r["skill_id"]: r for r in consent.read_skill_demand()}
    used = 0
    out = []
    for it in items:
        base = float(it.get("base_score", it.get("score", 0.0)) or 0.0)
        skills = it.get("skills") or []
        hits = [demand[s] for s in skills if s in demand]
        boost = None
        score = base
        if hits:
            top = max(h["demand_score"] for h in hits)
            add = round(DEMAND_WEIGHT * float(top), 4)
            score = round(base + add, 4)
            boost = {"added": add, "skills": [h["skill_name"] for h in hits][:4],
                     "label": f"Employer demand boost (+{add:.2f}): local postings ask for these skills (aggregate)"}
            used += 1
        out.append({**it, "base_score": round(base, 4), "score": score, "demand_boost": boost})
    out.sort(key=lambda x: -x["score"])
    return out, {"boosted": used, "weight": DEMAND_WEIGHT, "demand_skills": len(demand),
                 "source": "skill_demand table (employer gap reports, aggregate only)"}


@router.get("/recommend/{learner_id}")
async def recommend(
    learner_id: str,
    viewer: OptionalAccount,
    model: str = Query("gnn", pattern="^(gnn|mf|pop)$"),
    k: int = Query(10, ge=1, le=30),
):
    if learner_id == "me":
        if viewer is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Sign in required")
        if viewer.kind != "learner":
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="This needs a learner account")
        learner_id = viewer.persona_id
    learner_id = learner_id[:64]
    profile = _learner_profile(learner_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Learner not found")
    items, meta = await asyncio.to_thread(_model_recs, learner_id, model, k)
    trained = items is not None and len(items) > 0
    if not trained:
        items = _baseline(profile, k)
        model_used = "skill_gap_baseline"
    else:
        model_used = str(meta.get("model_used") or meta.get("model") or model)
    items, demand = _apply_demand(items[: k + 5])
    metrics = (data.metrics() or {}).get("recommender")
    return {
        "learner_id": learner_id, "model_requested": model, "model_used": model_used, "trained": trained,
        "note": meta.get("note") if not trained else meta.get("note"),
        "profile": {"career_id": profile.get("career_id"), "skills": len(profile.get("skills") or [])},
        "items": items[:k], "demand": demand, "metrics": metrics,
    }


__all__ = ["router"]
