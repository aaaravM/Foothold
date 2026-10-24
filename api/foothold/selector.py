"""Bayesian player model + adaptive event selector (brief 6.2). Shared by the sim graph and
``ml/eval_selector.py``.

Player model (a modelling assumption, not fitted to real players)::

    P(choice c | career k) = softmax_c( beta * dot(trait_deltas_c, work_styles_k - 0.5) )

``work_styles_k`` are the REAL O*NET 31.0 work-style percentiles from careers.json; trait deltas
are the drafted event choices in events.json. A choice that leans on traits a career's
profile rates above the median is more likely for someone suited to that career.

After each choice the posterior over the 8 careers is updated by Bayes' rule. The next event
is the remaining one with the highest expected information gain (mutual information between
the choice and the career, ``expected_information_gain``); ``select_event(..., method="thompson")``
instead samples a career from the posterior and picks the event whose choice distribution under
that career differs most (KL) from the posterior-mixture prediction.

A running trait estimate (0..1, 0.5 = no evidence) comes from the chosen trait deltas,
shrunk by how much evidence each trait has had: ``0.5 + 0.5 * S_t / (E_t + 1)`` where S_t is
the sum of chosen deltas for trait t and E_t the sum over shown events of max_c |delta_c,t|.

State is a plain JSON-able dict (it lives in the LangGraph checkpoint)::

    {"career_ids": [...], "posterior": {cid: p}, "beta": float,
     "evidence": {trait: S_t}, "exposure": {trait: E_t}, "n": int,
     "history": [{"event_id", "choice_id", "p_choice"}]}
"""

from __future__ import annotations

import random
from typing import Any, Iterable, Sequence

import numpy as np

from foothold import data

BETA = 4.5  # see the beta_sensitivity block of metrics.json["selector"]
CONFIDENT = 0.8
METHOD = "Bayesian player model + max expected information gain (foothold.selector)"


# ---------------------------------------------------------------------------
# model pieces
# ---------------------------------------------------------------------------


def trait_ids() -> list[str]:
    return list(data.traits_order())


def career_profiles(career_ids: Sequence[str] | None = None) -> tuple[list[str], np.ndarray]:
    """(career ids, P[K, T]) with work styles from careers.json (0.5 where missing)."""
    cids = list(career_ids or data.career_ids())
    traits = trait_ids()
    rows = []
    for cid in cids:
        ws = (data.get_career(cid) or {}).get("work_styles") or {}
        rows.append([float(ws.get(t, 0.5)) for t in traits])
    return cids, np.array(rows, dtype=float).reshape(len(cids), len(traits))


def choice_matrix(event: dict[str, Any], traits: Sequence[str] | None = None) -> tuple[list[str], np.ndarray]:
    """(choice ids, D[C, T]) of trait deltas for an event."""
    traits = list(traits or trait_ids())
    choices = [c for c in (event.get("choices") or []) if isinstance(c, dict)]
    ids = [str(c.get("choice_id")) for c in choices]
    D = np.array([[float((c.get("trait_deltas") or {}).get(t, 0.0)) for t in traits] for c in choices], dtype=float)
    return ids, D.reshape(len(choices), len(traits))


def _softmax(z: np.ndarray, axis: int = -1) -> np.ndarray:
    z = z - z.max(axis=axis, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=axis, keepdims=True)


def likelihoods(event: dict[str, Any], profiles: np.ndarray, beta: float = BETA) -> tuple[list[str], np.ndarray]:
    """(choice ids, L[K, C]) with L[k, c] = P(choice c | career k)."""
    ids, D = choice_matrix(event)
    if not ids:
        return ids, np.ones((profiles.shape[0], 0))
    util = (profiles - 0.5) @ D.T  # [K, C]
    return ids, _softmax(beta * util, axis=1)


def entropy(p: np.ndarray) -> float:
    p = np.asarray(p, dtype=float)
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def info_gain(post: np.ndarray, L: np.ndarray) -> float:
    """Mutual information (bits) between the choice and the career under ``post``."""
    if L.size == 0:
        return 0.0
    pc = post @ L  # [C]
    h_after = 0.0
    for c in range(L.shape[1]):
        if pc[c] <= 0:
            continue
        pk = post * L[:, c] / pc[c]
        h_after += pc[c] * entropy(pk)
    return max(0.0, entropy(post) - h_after)


def likelihood_tensor(events: Sequence[dict[str, Any]], profiles: np.ndarray, beta: float = BETA) -> np.ndarray:
    """LT[E, K, Cmax] = P(choice c | career k) per event, zero-padded for events with fewer choices."""
    Ls = [likelihoods(ev, profiles, beta)[1] for ev in events]
    cmax = max((L.shape[1] for L in Ls), default=0)
    LT = np.zeros((len(Ls), profiles.shape[0], cmax))
    for i, L in enumerate(Ls):
        LT[i, :, : L.shape[1]] = L
    return LT


def info_gain_batch(post: np.ndarray, LT: np.ndarray) -> np.ndarray:
    """Vectorized ``info_gain`` for every event in LT[E, K, C] -> [E] bits."""
    if LT.size == 0:
        return np.zeros(LT.shape[0])
    joint = post[None, :, None] * LT                  # [E, K, C]
    pc = joint.sum(axis=1)                            # [E, C]
    with np.errstate(divide="ignore", invalid="ignore"):
        cond = np.where(pc[:, None, :] > 0, joint / pc[:, None, :], 0.0)
        h = -np.where(cond > 0, cond * np.log2(cond), 0.0).sum(axis=1)  # [E, C]
    return np.maximum(0.0, entropy(post) - (pc * h).sum(axis=1))


def thompson_score(post: np.ndarray, L: np.ndarray, k: int) -> float:
    """KL( P(c | k) || sum_j post_j P(c | j) ): how much this event would single out career k."""
    if L.size == 0:
        return 0.0
    mix = np.maximum(post @ L, 1e-12)
    lk = np.maximum(L[k], 1e-12)
    return float((lk * np.log2(lk / mix)).sum())


# ---------------------------------------------------------------------------
# state API used by the sim graph
# ---------------------------------------------------------------------------


def _post_vec(state_or_post: Any, cids: Sequence[str]) -> np.ndarray:
    post = state_or_post.get("posterior", state_or_post) if isinstance(state_or_post, dict) else state_or_post
    if isinstance(post, dict):
        v = np.array([float(post.get(c, 0.0)) for c in cids], dtype=float)
    else:
        v = np.asarray(post, dtype=float).reshape(-1)
    s = v.sum()
    return v / s if s > 0 and np.all(np.isfinite(v)) else np.full(len(cids), 1.0 / max(len(cids), 1))


def _cids_of(state: Any) -> list[str]:
    if isinstance(state, dict) and state.get("career_ids"):
        return list(state["career_ids"])
    if isinstance(state, dict) and isinstance(state.get("posterior"), dict):
        return list(state["posterior"].keys())
    if isinstance(state, dict) and state and all(isinstance(v, (int, float)) for v in state.values()):
        return list(state.keys())
    return data.career_ids()


def initial_state(career_ids: Sequence[str] | None = None, prior: dict[str, float] | None = None,
                  beta: float = BETA) -> dict[str, Any]:
    cids = list(career_ids or data.career_ids())
    p = _post_vec(prior, cids) if prior else np.full(len(cids), 1.0 / max(len(cids), 1))
    traits = trait_ids()
    return {"career_ids": cids, "posterior": {c: float(v) for c, v in zip(cids, p)}, "beta": float(beta),
            "evidence": {t: 0.0 for t in traits}, "exposure": {t: 0.0 for t in traits}, "n": 0, "history": []}


def expected_information_gain(state: dict[str, Any], event: dict[str, Any]) -> float:
    cids = _cids_of(state)
    _, P = career_profiles(cids)
    _, L = likelihoods(event, P, float(state.get("beta", BETA)) if isinstance(state, dict) else BETA)
    return round(float(info_gain(_post_vec(state, cids), L)), 6)


def update(state: dict[str, Any], event: dict[str, Any], choice_id: str,
           trait_deltas: dict[str, float] | None = None) -> dict[str, Any]:
    """Bayes update on the chosen option + trait-evidence update. Returns a new state dict."""
    st = dict(state) if state and state.get("career_ids") else initial_state()
    cids = list(st["career_ids"])
    beta = float(st.get("beta", BETA))
    _, P = career_profiles(cids)
    ids, L = likelihoods(event, P, beta)
    post = _post_vec(st, cids)
    p_choice = None
    if str(choice_id) in ids:
        c = ids.index(str(choice_id))
        p_choice = float(post @ L[:, c])
        new = post * L[:, c]
        post = new / new.sum() if new.sum() > 0 else post
    traits = trait_ids()
    evidence = {t: float((st.get("evidence") or {}).get(t, 0.0)) for t in traits}
    exposure = {t: float((st.get("exposure") or {}).get(t, 0.0)) for t in traits}
    if trait_deltas is None:
        ch = next((c for c in event.get("choices") or [] if str(c.get("choice_id")) == str(choice_id)), {})
        trait_deltas = ch.get("trait_deltas") or {}
    for t, d in (trait_deltas or {}).items():
        if t in evidence:
            try:
                evidence[t] += max(-1.0, min(1.0, float(d)))
            except (TypeError, ValueError):
                pass
    _, D = choice_matrix(event, traits)
    span = np.abs(D).max(axis=0) if D.size else np.zeros(len(traits))
    for i, t in enumerate(traits):
        exposure[t] += float(span[i])
    # LLM-blended deltas may touch traits the event's choices didn't: count them as exposure too
    for t, d in (trait_deltas or {}).items():
        if t in exposure and span[traits.index(t)] == 0.0:
            try:
                exposure[t] += min(1.0, abs(float(d)))
            except (TypeError, ValueError):
                pass
    hist = list(st.get("history") or [])
    hist.append({"event_id": event.get("event_id"), "choice_id": str(choice_id),
                 "p_choice": None if p_choice is None else round(p_choice, 4)})
    st.update(posterior={c: round(float(v), 6) for c, v in zip(cids, post)}, evidence=evidence, exposure=exposure,
              n=int(st.get("n", 0)) + 1, history=hist)
    return st


def trait_estimate(state: dict[str, Any]) -> dict[str, float]:
    ev = state.get("evidence") or {}
    ex = state.get("exposure") or {}
    out = {}
    for t in trait_ids():
        s = float(ev.get(t, 0.0))
        e = float(ex.get(t, 0.0))
        out[t] = round(min(1.0, max(0.0, 0.5 + 0.5 * s / (e + 1.0))), 4)
    return out


def summarize(state: dict[str, Any]) -> dict[str, Any]:
    cids = _cids_of(state)
    post = _post_vec(state, cids)
    order = np.argsort(-post, kind="stable")
    top = [{"career_id": cids[i], "probability": round(float(post[i]), 4)} for i in order]
    return {"trait_estimate": trait_estimate(state), "posterior": {c: round(float(v), 4) for c, v in zip(cids, post)},
            "top": top, "confident": bool(post.max() >= CONFIDENT), "entropy_bits": round(entropy(post), 4),
            "n": int(state.get("n", 0)), "method": METHOD}


def select_event(posterior: Any, remaining_events: Iterable[dict[str, Any]], *, method: str = "info_gain",
                 career_ids: Sequence[str] | None = None, beta: float | None = None,
                 rng: random.Random | np.random.Generator | None = None) -> dict[str, Any] | None:
    """Pick the next event: ``info_gain`` (default) or ``thompson``. ``posterior`` may be a
    selector state, a {career_id: p} dict or an array aligned with ``career_ids``."""
    events = list(remaining_events)
    if not events:
        return None
    cids = list(career_ids or _cids_of(posterior))
    b = float(beta if beta is not None else (posterior.get("beta", BETA) if isinstance(posterior, dict) else BETA))
    _, P = career_profiles(cids)
    post = _post_vec(posterior, cids)
    LT = likelihood_tensor(events, P, b)
    if method == "thompson":
        if isinstance(rng, np.random.Generator):
            k = int(rng.choice(len(cids), p=post))
        else:
            k = int((rng or random).choices(range(len(cids)), weights=post.tolist())[0])
        scores = [thompson_score(post, L, k) for L in LT]
    else:
        scores = info_gain_batch(post, LT).tolist()
    best = int(np.argmax(scores))  # ties -> earliest (callers pass events in clock order)
    return events[best]


def gains(state: dict[str, Any], events: Iterable[dict[str, Any]]) -> list[tuple[str, float]]:
    """[(event_id, expected information gain bits)] for display/debugging."""
    return [(str(ev.get("event_id")), expected_information_gain(state, ev)) for ev in events]

