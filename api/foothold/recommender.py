"""Graph recommender inference (brief 6.3): GNN / BPR-MF / popularity, no retraining at serve time.

Artifacts (written by ``ml/train_recommender.py``): ``ml/artifacts/recommender.npz`` (final embeddings
+ popularity counts) and ``recommender.json`` (node id order, config, metrics). Scores are dot products
(the last embedding column folds in a learned item bias).

Public API
----------
recommend(learner_id, model="gnn"|"mf"|"pop", k=10) -> dict
    {learner_id, node, model, model_used, model_type, trained, note, provenance,
     items:[{kind: course|job, id, title, score, base_score, raw_score, rank, skills, path, why,
             provider?, url?, cost_usd?, hours?, level?, career_id?}]}
    ``score``/``base_score`` are min-max normalized per item type for this learner (0..1, 1 = top);
    ``raw_score`` is the model's dot product. ``path`` is a chain of REAL supporting edges from the data
    files: [{type, id, label, edge}] where ``edge`` names the relation from the previous node
    (has_skill, taught_by, teaches, required_by, also_requires, targets, needs).
    Learner ids: synthetic ``syn_l####``, talent-card ids ``cand_*``, or persona ids ``maya``/``dev``/``luis``
    (mapped to their talent cards ``cand_<persona>``, which are feature-only nodes in the trained graph).
    Unknown learner or missing artifacts -> ``{"items": [], "trained": False, "note": ...}`` (callers fall back).
score_talent(cards, profile) -> {card_id: 0..1}
    Recommender affinity of talent-pool cards to a posting profile (``profile["skills"]`` =
    [{skill_id, importance}] or [skill_id]): GNN learner->job scores for the jobs that best match the
    posting's skills, normalized over the whole pool. Never uses the synthetic ``group`` label.
graph_sample(n=60) -> {nodes, links, stats, provenance}
    A small learner/skill/course/job subgraph from real data edges (for visualizations).
status() -> {available, model_type, metrics, trained_at}
"""

from __future__ import annotations

import json
import logging
import random
import threading
from typing import Any

import numpy as np

from foothold import config, data

log = logging.getLogger("foothold.recommender")

MODELS = {"gnn": "gnn", "mf": "mf", "pop": "pop", "popularity": "pop"}
_lock = threading.Lock()
_state: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------


def _paths():
    return config.ARTIFACTS_DIR / "recommender.npz", config.ARTIFACTS_DIR / "recommender.json"


def _load() -> dict[str, Any] | None:
    npz_p, js_p = _paths()
    if not npz_p.exists() or not js_p.exists():
        return None
    key = (npz_p.stat().st_mtime_ns, js_p.stat().st_mtime_ns)
    with _lock:
        if _state.get("key") == key:
            return _state["art"]
        meta = json.loads(js_p.read_text(encoding="utf-8"))
        with np.load(npz_p) as z:
            arr = {k: z[k] for k in z.files}
        art = {
            "meta": meta, "arr": arr,
            "lidx": {lid: i for i, lid in enumerate(meta["learner_ids"])},
            "cidx": {c: i for i, c in enumerate(meta["course_ids"])},
            "jidx": {j: i for i, j in enumerate(meta["job_ids"])},
        }
        _state.clear()
        _state.update(key=key, art=art)
        return art


def status() -> dict[str, Any]:
    art = _load()
    if art is None:
        return {"available": False, "note": "run ml/train_recommender.py"}
    m = art["meta"]
    return {"available": True, "model_type": m.get("model_type"), "trained_at": m.get("trained_at"),
            "metrics": m.get("metrics"), "winner": m.get("winner"), "config": m.get("config")}


# ---------------------------------------------------------------------------
# data helpers
# ---------------------------------------------------------------------------


def _jobs() -> list[dict[str, Any]]:
    return data._as_list(data._processed("jobs.json", []), "jobs")


def _names() -> dict[str, str]:
    return {s["id"]: s.get("name", s["id"]) for s in data.skills()}


def _card_for(learner_id: str) -> dict[str, Any] | None:
    for c in data.talent_pool():
        if not isinstance(c, dict):
            continue
        if c.get("persona_id") == learner_id or c.get("id") == learner_id or c.get("candidate_id") == learner_id:
            return c
    return None


def resolve(learner_id: str) -> tuple[str | None, dict[str, Any]]:
    """learner id / card id / persona id -> (graph node id, profile {skills, career_id, completed})."""
    art = _load()
    lidx = art["lidx"] if art else {}
    learner = data.get_learner(learner_id) if learner_id.startswith("syn_") else None
    if learner:
        return (learner_id if learner_id in lidx else None), {
            "skills": [s for s in learner.get("skills", [])], "career_id": learner.get("target_career"),
            "completed": list(learner.get("completed_courses") or []),
        }
    card = _card_for(learner_id)
    if card:
        b = card.get("blind") or {}
        node = "tp:" + str(card.get("id") or card.get("candidate_id"))
        return (node if node in lidx else None), {
            "skills": list(b.get("demonstrated_skills") or []), "career_id": b.get("target_career"), "completed": [],
        }
    return None, {}


def _scores(art: dict[str, Any], model: str, node: str, kind: str) -> np.ndarray:
    a = art["arr"]
    if model == "pop":
        return a[f"pop_{kind}"].astype(np.float64)
    u = a[f"{model}_learner"][art["lidx"][node]]
    return (a[f"{model}_{kind}"] @ u).astype(np.float64)


def _norm(s: np.ndarray) -> np.ndarray:
    lo, hi = float(np.min(s)), float(np.max(s))
    return (s - lo) / (hi - lo) if hi > lo else np.zeros_like(s)


# ---------------------------------------------------------------------------
# explanation paths (real edges only)
# ---------------------------------------------------------------------------


def _course_path(c: dict[str, Any], prof: dict[str, Any], learner_label: str, ranked_jobs: list[dict[str, Any]],
                 names: dict[str, str]) -> tuple[list[dict[str, Any]], str]:
    have = set(prof.get("skills") or [])
    cs = [s for s in c.get("skills", [])]
    path = [{"type": "learner", "id": prof["id"], "label": learner_label, "edge": None}]
    shared = [s for s in cs if s in have]
    career = data.get_career(prof.get("career_id") or "") if prof.get("career_id") else None
    if shared:
        s1 = shared[0]
        path += [{"type": "skill", "id": s1, "label": names.get(s1, s1), "edge": "has_skill"},
                 {"type": "course", "id": c["id"], "label": c.get("title", c["id"]), "edge": "taught_by"}]
        why = f"Builds on {names.get(s1, s1)}, which you already have"
    elif career and any(s in (career.get("skills") or []) for s in cs):
        s1 = next(s for s in cs if s in (career.get("skills") or []))
        path += [{"type": "career", "id": career["id"], "label": career.get("title", career["id"]), "edge": "targets"},
                 {"type": "skill", "id": s1, "label": names.get(s1, s1), "edge": "needs"},
                 {"type": "course", "id": c["id"], "label": c.get("title", c["id"]), "edge": "taught_by"}]
        why = f"Teaches {names.get(s1, s1)}, which {career.get('title', 'your target career')} needs"
    else:
        path += [{"type": "course", "id": c["id"], "label": c.get("title", c["id"]), "edge": "similar_learners"}]
        why = "Learners with a similar profile took this course"
    new = [s for s in cs if s not in have] or cs
    for j in ranked_jobs:
        req = set(j.get("required_skills") or [])
        hit = next((s for s in new if s in req), None)
        if hit:
            path += [{"type": "skill", "id": hit, "label": names.get(hit, hit), "edge": "teaches"},
                     {"type": "job", "id": j["id"], "label": j.get("title", j["id"]), "edge": "required_by"}]
            why += f"; teaches {names.get(hit, hit)} for {j.get('title', j['id'])}"
            break
    return path, why


def _job_path(j: dict[str, Any], prof: dict[str, Any], learner_label: str, ranked_courses: list[dict[str, Any]],
              names: dict[str, str]) -> tuple[list[dict[str, Any]], str]:
    have = set(prof.get("skills") or [])
    req = [s for s in j.get("required_skills") or []]
    path = [{"type": "learner", "id": prof["id"], "label": learner_label, "edge": None}]
    shared = [s for s in req if s in have]
    if shared:
        s1 = shared[0]
        path += [{"type": "skill", "id": s1, "label": names.get(s1, s1), "edge": "has_skill"},
                 {"type": "job", "id": j["id"], "label": j.get("title", j["id"]), "edge": "required_by"}]
        why = f"You have {len(shared)} of {len(req)} required skills"
    else:
        path += [{"type": "job", "id": j["id"], "label": j.get("title", j["id"]), "edge": "similar_learners"}]
        why = "Learners with a similar profile were placed here"
    missing = [s for s in req if s not in have]
    for c in ranked_courses:
        hit = next((s for s in missing if s in (c.get("skills") or [])), None)
        if hit:
            path += [{"type": "skill", "id": hit, "label": names.get(hit, hit), "edge": "also_requires"},
                     {"type": "course", "id": c["id"], "label": c.get("title", c["id"]), "edge": "taught_by"}]
            why += f"; close the {names.get(hit, hit)} gap with {c.get('title', c['id'])}"
            break
    return path, why


# ---------------------------------------------------------------------------
# recommend
# ---------------------------------------------------------------------------


def recommend(learner_id: str, model: str = "gnn", k: int = 10, n_jobs: int = 3) -> dict[str, Any]:
    model = MODELS.get(model, "gnn")
    art = _load()
    base = {"learner_id": learner_id, "model": model, "provenance": "SYNTHETIC", "fictional": True}
    if art is None:
        return {**base, "trained": False, "items": [], "note": "recommender not trained yet (ml/train_recommender.py)"}
    node, prof = resolve(learner_id)
    if node is None:
        return {**base, "trained": False, "items": [], "note": "learner is not a node in the trained graph"}
    prof["id"] = learner_id
    meta = art["meta"]
    trained_items = (meta.get("train_items") or {}).get(node, {})
    done_c = set(prof.get("completed") or []) | set(trained_items.get("courses") or [])
    courses = data.courses()
    cmap = {c["id"]: c for c in courses}
    jobs = _jobs()
    jmap = {j["id"]: j for j in jobs}

    out_items: dict[str, list[dict[str, Any]]] = {}
    for kind, ids, lookup in (("course", meta["course_ids"], cmap), ("job", meta["job_ids"], jmap)):
        raw = _scores(art, model, node, kind)
        nrm = _norm(raw)
        order = np.argsort(-raw, kind="stable")
        rows = []
        for i in order:
            iid = ids[int(i)]
            if iid not in lookup or (kind == "course" and iid in done_c):
                continue
            rows.append((iid, float(raw[i]), float(nrm[i])))
        out_items[kind] = rows

    names = _names()
    label = "You"
    ranked_jobs = [jmap[i] for i, _, _ in out_items["job"][:10]]
    ranked_courses = [cmap[i] for i, _, _ in out_items["course"][:20]]
    n_courses = max(1, k - min(n_jobs, k - 1)) if k > 1 else 1
    items: list[dict[str, Any]] = []
    for rank, (iid, raw, nrm) in enumerate(out_items["course"][:n_courses], 1):
        c = cmap[iid]
        path, why = _course_path(c, prof, label, ranked_jobs, names)
        items.append({"kind": "course", "id": iid, "title": c.get("title"), "provider": c.get("provider"),
                      "url": c.get("url"), "cost_usd": c.get("cost_usd"), "hours": c.get("hours"),
                      "status": c.get("status"), "skills": c.get("skills", []), "score": round(nrm, 4),
                      "base_score": round(nrm, 4), "raw_score": round(raw, 4), "rank": rank, "path": path, "why": why})
    if k > 1:
        for rank, (iid, raw, nrm) in enumerate(out_items["job"][: min(n_jobs, k - 1)], 1):
            j = jmap[iid]
            path, why = _job_path(j, prof, label, ranked_courses, names)
            items.append({"kind": "job", "id": iid, "title": j.get("title"), "level": j.get("level"),
                          "career_id": j.get("career_id"), "status": j.get("status"),
                          "skills": j.get("required_skills", []), "score": round(nrm, 4), "base_score": round(nrm, 4),
                          "raw_score": round(raw, 4), "rank": rank, "path": path, "why": why})
    m = (meta.get("metrics") or {}).get({"pop": "popularity"}.get(model, model), {})
    return {**base, "node": node, "trained": True, "model_used": model, "model_type": meta.get("model_type"),
            "items": items, "metrics": m, "winner": meta.get("winner"),
            "note": ("Scores are normalized per item type for this learner (1 = top). Trained on SYNTHETIC learners; "
                     "explanation paths use real skill/course/job edges from the data files.")}


# ---------------------------------------------------------------------------
# employer-side talent scoring
# ---------------------------------------------------------------------------


def _profile_skills(profile: dict[str, Any] | None) -> dict[str, float]:
    out: dict[str, float] = {}
    raw = (profile or {}).get("skills") or (profile or {}).get("required_skills") or []
    for s in raw:
        if isinstance(s, str):
            out[s] = max(out.get(s, 0.0), 1.0)
        elif isinstance(s, dict) and isinstance(s.get("skill_id") or s.get("id"), str):
            sid = s.get("skill_id") or s.get("id")
            w = 0.5 if s.get("importance") == "preferred" else 1.0
            out[sid] = max(out.get(sid, 0.0), w)
    for s in (profile or {}).get("preferred_skills") or []:
        if isinstance(s, str):
            out.setdefault(s, 0.5)
    return out


def score_talent(cards: list[dict[str, Any] | None], profile: dict[str, Any] | None, model: str = "gnn",
                 top_jobs: int = 3) -> dict[str, float]:
    """{card_id: 0..1}. Uses only the trained learner embeddings of the cards (never the group label)."""
    art = _load()
    weights = _profile_skills(profile)
    if art is None or not weights:
        return {}
    model = "gnn" if MODELS.get(model, "gnn") == "pop" else MODELS.get(model, "gnn")
    total = sum(weights.values())
    rel = []
    for j in _jobs():
        req = set(j.get("required_skills") or [])
        r = sum(w for s, w in weights.items() if s in req) / total
        if r > 0 and j["id"] in art["jidx"]:
            rel.append((r, j["id"]))
    rel.sort(key=lambda t: (-t[0], t[1]))
    rel = rel[:top_jobs]
    a = art["arr"]
    pool_rows = [i for lid, i in art["lidx"].items() if lid.startswith("tp:")]
    if not rel or not pool_rows:
        return {}
    L = a[f"{model}_learner"][pool_rows]
    jix = [art["jidx"][jid] for _, jid in rel]
    S = L @ a[f"{model}_job"][jix].T  # pool x jobs
    lo, hi = S.min(0), S.max(0)
    N = (S - lo) / np.where(hi > lo, hi - lo, 1.0)
    w = np.array([r for r, _ in rel])
    agg = (N * w).sum(1) / w.sum()
    by_node = {art["meta"]["learner_ids"][row]: float(v) for row, v in zip(pool_rows, agg)}
    out: dict[str, float] = {}
    for c in cards:
        if not isinstance(c, dict):
            continue
        cid = c.get("id") or c.get("candidate_id")
        v = by_node.get(f"tp:{cid}")
        if cid and v is not None:
            out[str(cid)] = round(max(0.0, min(1.0, v)), 4)
    return out


# ---------------------------------------------------------------------------
# graph sample
# ---------------------------------------------------------------------------


def graph_sample(n: int = 60, seed: int = 7) -> dict[str, Any]:
    """n synthetic learners + the skills/courses/jobs they touch, from real data edges."""
    learners = [x for x in data.learners() if isinstance(x, dict) and (x.get("completed_courses") or x.get("placed_job"))]
    rng = random.Random(seed)
    pick = sorted(rng.sample(learners, min(n, len(learners))), key=lambda x: x["id"])
    names = _names()
    cmap = {c["id"]: c for c in data.courses()}
    jmap = {j["id"]: j for j in _jobs()}
    nodes: dict[str, dict[str, Any]] = {}
    links: list[dict[str, Any]] = []

    def add(nid, typ, label, **kw):
        nodes.setdefault(nid, {"id": nid, "type": typ, "label": label, **kw})

    for i, l in enumerate(pick, 1):
        lid = f"learner:{l['id']}"
        add(lid, "learner", f"Learner {i}", learner_id=l["id"], cold_start=bool(l.get("cold_start")))
        for cid in l.get("completed_courses") or []:
            c = cmap.get(cid)
            if not c:
                continue
            add(f"course:{cid}", "course", c.get("title", cid))
            links.append({"source": lid, "target": f"course:{cid}", "type": "completed"})
        jid = l.get("placed_job")
        if jid and jid in jmap:
            add(f"job:{jid}", "job", jmap[jid].get("title", jid))
            links.append({"source": lid, "target": f"job:{jid}", "type": "placed_in"})
        for s in l.get("skills") or []:
            add(f"skill:{s}", "skill", names.get(s, s))
            links.append({"source": lid, "target": f"skill:{s}", "type": "has_skill"})
    for nid, nd in list(nodes.items()):
        if nd["type"] == "course":
            for s in cmap[nid.split(":", 1)[1]].get("skills", []):
                if f"skill:{s}" in nodes:
                    links.append({"source": nid, "target": f"skill:{s}", "type": "teaches"})
        elif nd["type"] == "job":
            for s in jmap[nid.split(":", 1)[1]].get("required_skills", []):
                if f"skill:{s}" in nodes:
                    links.append({"source": nid, "target": f"skill:{s}", "type": "requires"})
    stats = {t: sum(1 for x in nodes.values() if x["type"] == t) for t in ("learner", "skill", "course", "job")}
    stats["links"] = len(links)
    return {"nodes": list(nodes.values()), "links": links, "stats": stats, "provenance": "SYNTHETIC", "fictional": True}


__all__ = ["recommend", "score_talent", "graph_sample", "status", "resolve"]
