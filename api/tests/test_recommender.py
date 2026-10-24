"""Graph recommender inference (needs ml/artifacts/recommender.* from ml/train_recommender.py)."""

from __future__ import annotations

import pytest

from foothold import config, data, recommender

pytestmark = pytest.mark.skipif(
    not (config.ARTIFACTS_DIR / "recommender.npz").exists(), reason="run ml/train_recommender.py first"
)


def _edge_ok(a: dict, b: dict, learner_skills: set[str], career: str | None) -> bool:
    """True if a->b is a real edge in the data files."""
    courses = {c["id"]: set(c.get("skills", [])) for c in data.courses()}
    jobs = {j["id"]: set(j.get("required_skills", [])) for j in recommender._jobs()}
    t = (a["type"], b["type"])
    if t == ("learner", "skill"):
        return b["id"] in learner_skills
    if t == ("skill", "course"):
        return a["id"] in courses[b["id"]]
    if t == ("course", "skill"):
        return b["id"] in courses[a["id"]]
    if t == ("skill", "job"):
        return a["id"] in jobs[b["id"]]
    if t == ("job", "skill"):
        return b["id"] in jobs[a["id"]]
    if t == ("learner", "career"):
        return b["id"] == career
    if t == ("career", "skill"):
        return a["id"] == career and b["id"] in (data.get_career(career) or {}).get("skills", [])
    if t[0] == "learner" and b.get("edge") == "similar_learners":
        return True
    return False


@pytest.mark.parametrize("persona", ["maya", "dev", "luis"])
@pytest.mark.parametrize("model", ["gnn", "mf", "pop"])
def test_personas_get_courses_and_jobs_with_real_paths(persona, model):
    res = recommender.recommend(persona, model=model, k=10)
    assert res["trained"] is True and res["node"] == f"tp:cand_{persona}"
    kinds = [i["kind"] for i in res["items"]]
    assert kinds.count("course") == 7 and kinds.count("job") == 3
    _, prof = recommender.resolve(persona)
    for it in res["items"]:
        assert 0.0 <= it["score"] <= 1.0
        p = it["path"]
        assert p[0]["type"] == "learner" and any(n["type"] == it["kind"] and n["id"] == it["id"] for n in p)
        for a, b in zip(p, p[1:]):
            assert _edge_ok(a, b, set(prof["skills"]), prof["career_id"]), (a, b)
    course_scores = [i["raw_score"] for i in res["items"] if i["kind"] == "course"]
    assert course_scores == sorted(course_scores, reverse=True)


def test_gnn_uses_profile_for_cold_start_personas():
    # feature-only persona nodes: the GNN differentiates them, popularity cannot
    gm = [i["id"] for i in recommender.recommend("maya", "gnn")["items"] if i["kind"] == "job"]
    gl = [i["id"] for i in recommender.recommend("luis", "gnn")["items"] if i["kind"] == "job"]
    assert gm != gl
    pm = [i["id"] for i in recommender.recommend("maya", "pop")["items"]]
    pl = [i["id"] for i in recommender.recommend("luis", "pop")["items"]]
    assert pm == pl


def test_completed_courses_excluded_and_unknown_learner():
    lr = next(x for x in data.learners() if len(x["completed_courses"]) >= 2)
    res = recommender.recommend(lr["id"], "gnn", k=10)
    assert res["trained"] and not ({i["id"] for i in res["items"]} & set(lr["completed_courses"]))
    miss = recommender.recommend("nobody_here", "gnn")
    assert miss["trained"] is False and miss["items"] == []


def test_score_talent_range_and_group_blind():
    cards = data.talent_pool()
    profile = {"skills": [{"skill_id": "osha_safety", "importance": "required"},
                          {"skill_id": "forklift_safety", "importance": "required"}]}
    s = recommender.score_talent(cards, profile)
    assert len(s) == len(cards) and all(0.0 <= v <= 1.0 for v in s.values())
    flipped = [{**c, "group": "Z"} for c in cards]
    assert recommender.score_talent(flipped, profile) == s
    assert recommender.score_talent(cards, {"skills": []}) == {}


def test_graph_sample_links_resolve():
    g = recommender.graph_sample(60)
    ids = {n["id"] for n in g["nodes"]}
    assert g["stats"]["learner"] == 60 and all(lk["source"] in ids and lk["target"] in ids for lk in g["links"])
    assert {lk["type"] for lk in g["links"]} >= {"has_skill", "completed", "teaches"}


def test_metrics_block_present():
    m = data.metrics().get("recommender")
    assert m and m["status"] == "trained" and m["provenance"] == "SYNTHETIC"
    for model in ("gnn", "mf", "popularity"):
        for seg in ("warm", "cold"):
            assert m[model][seg]["all"]["recall@10"] is not None
