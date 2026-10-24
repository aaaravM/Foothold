"""Adaptive event selector (brief 6.2): player model, Bayes update, information gain, selection."""

from __future__ import annotations

import random

import numpy as np

from foothold import data
from foothold import selector as sel


def _events():
    return [e for e in data.events_list() if not e.get("crunch")]


def test_initial_state_uniform_and_jsonable():
    import json

    st = sel.initial_state(career_ids=data.career_ids())
    assert len(st["posterior"]) == 8 and abs(sum(st["posterior"].values()) - 1) < 1e-9
    json.dumps(st)
    s = sel.summarize(st)
    assert set(s) >= {"trait_estimate", "posterior", "method", "top", "confident"}
    assert all(v == 0.5 for v in s["trait_estimate"].values()) and not s["confident"]


def test_likelihoods_rows_are_distributions():
    cids, P = sel.career_profiles()
    for ev in _events()[:10]:
        ids, L = sel.likelihoods(ev, P)
        assert L.shape == (8, len(ids)) and np.allclose(L.sum(axis=1), 1)


def test_info_gain_nonnegative_batch_matches_scalar():
    cids, P = sel.career_profiles()
    evs = _events()
    LT = sel.likelihood_tensor(evs, P)
    post = np.random.default_rng(0).dirichlet(np.ones(8))
    batch = sel.info_gain_batch(post, LT)
    scalar = [sel.info_gain(post, sel.likelihoods(e, P)[1]) for e in evs]
    assert np.allclose(batch, scalar, atol=1e-9) and (batch >= 0).all()
    flat = {"event_id": "x", "choices": [{"choice_id": c, "trait_deltas": {}} for c in "abc"]}
    assert sel.expected_information_gain(sel.initial_state(), flat) == 0.0


def test_update_moves_posterior_toward_consistent_career():
    """Always picking the choice most likely for nurses should make the nurse the posterior max."""
    cids, P = sel.career_profiles()
    k = cids.index("registered_nurse")
    st = sel.initial_state()
    for ev in _events()[:15]:
        ids, L = sel.likelihoods(ev, P)
        st = sel.update(st, ev, ids[int(np.argmax(L[k]))])
    post = st["posterior"]
    assert max(post, key=post.get) == "registered_nurse"
    assert st["n"] == 15 and len(st["history"]) == 15
    est = sel.summarize(st)["trait_estimate"]
    assert all(0 <= v <= 1 for v in est.values()) and any(v != 0.5 for v in est.values())


def test_update_uses_passed_trait_deltas_for_estimate():
    ev = _events()[0]
    st = sel.update(sel.initial_state(), ev, "a", trait_deltas={"empathy": 1.0})
    assert sel.trait_estimate(st)["empathy"] > 0.5


def test_select_event_picks_max_gain_and_thompson_returns_event():
    evs = _events()
    st = sel.initial_state()
    best = sel.select_event(st, evs)
    gains = dict(sel.gains(st, evs))
    assert gains[best["event_id"]] == max(gains.values())
    assert sel.select_event(st["posterior"], evs, method="thompson", rng=random.Random(1)) in evs
    assert sel.select_event(st, []) is None


def test_sim_adapter_sees_selector():
    from foothold.graphs import sim

    assert sim.SelectorAdapter().available
