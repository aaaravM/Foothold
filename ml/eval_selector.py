"""Evaluate the adaptive event selector (brief 6.2) on simulated players.

    python ml/eval_selector.py [--players 2000] [--seed 11] [--cap 20]

Each synthetic player: true career ~ uniform over the 8 careers; profile = that career's O*NET
work styles + N(0, 0.10^2) noise (clipped 0..1); choices are sampled from the softmax player
model with a DIFFERENT beta (``--player-beta``, default 4.0) than the selector assumes (selector.BETA = 4.5),
so the selector's model is deliberately mis-specified. Each player's answer to each event is
drawn once up front (common random numbers), so every strategy sees the same player.

Strategies over the non-crunch events (the sim's candidate pool): adaptive (max expected
information gain), thompson, random order, fixed order (clock order, then event id).
Metrics: events until a confident match (posterior max >= 0.8 AND the argmax is the true
career), capped at ``--cap`` (non-converged players are reported and counted at the cap in
the headline average); accuracy (argmax == true career) after k = 1..10 events.
Writes the ``selector`` key of ml/artifacts/metrics.json and ml/artifacts/curves/selector.json.
"""

from __future__ import annotations

import argparse
import sys
import time

import common  # noqa: F401
from common import CURVES_DIR, now_iso, seed_everything, write_json, write_metrics

import numpy as np

from foothold import data
from foothold import selector as sel

STRATEGIES = ("adaptive", "thompson", "random", "fixed")


def run(players: int, seed: int, cap: int, player_beta: float, noise_sd: float, kmax: int) -> dict:
    rng = np.random.default_rng(seed)
    cids, P = sel.career_profiles()
    K = len(cids)
    events = sorted([e for e in data.events_list() if not e.get("crunch")],
                    key=lambda e: (str(e.get("clock", "")), e["event_id"]))
    E = len(events)
    cap = min(cap, E)
    LT = sel.likelihood_tensor(events, P, sel.BETA)            # selector's model
    D = [sel.choice_matrix(ev)[1] for ev in events]

    steps = max(cap, kmax)
    res = {s: {"hit": np.full(players, -1), "wrong_conf": np.zeros(players, bool),
               "correct": np.zeros((players, steps), bool), "maxp": np.zeros((players, steps))} for s in STRATEGIES}
    true = rng.integers(0, K, size=players)
    for i in range(players):
        prof = np.clip(P[true[i]] + rng.normal(0, noise_sd, P.shape[1]), 0, 1)
        answers = np.empty(E, dtype=int)
        for e in range(E):
            p = sel._softmax(player_beta * (D[e] @ (prof - 0.5)))
            answers[e] = rng.choice(len(p), p=p)
        rand_order = rng.permutation(E)
        ts_rng = np.random.default_rng(seed * 100003 + i)
        for s in STRATEGIES:
            post = np.full(K, 1.0 / K)
            remaining = list(range(E))
            r = res[s]
            for t in range(min(steps, E)):
                if s == "adaptive":
                    g = sel.info_gain_batch(post, LT[remaining])
                    e = remaining[int(np.argmax(g))]
                elif s == "thompson":
                    k = int(ts_rng.choice(K, p=post))
                    sc = [sel.thompson_score(post, LT[j], k) for j in remaining]
                    e = remaining[int(np.argmax(sc))]
                elif s == "random":
                    e = int(rand_order[t])
                else:
                    e = remaining[0]
                remaining.remove(e)
                post = post * LT[e][:, answers[e]]
                post = post / post.sum()
                top = int(np.argmax(post))
                r["correct"][i, t] = top == true[i]
                r["maxp"][i, t] = post[top]
                if r["hit"][i] < 0 and t < cap and post[top] >= sel.CONFIDENT:
                    if top == true[i]:
                        r["hit"][i] = t + 1
                    elif not r["wrong_conf"][i]:
                        r["wrong_conf"][i] = True
    out = {}
    for s in STRATEGIES:
        r = res[s]
        hit = r["hit"]
        conv = hit > 0
        out[s] = {
            "avg_events_to_confident": round(float(np.where(conv, hit, cap).mean()), 3),
            "avg_events_to_confident_converged_only": round(float(hit[conv].mean()), 3) if conv.any() else None,
            "median_events_to_confident": float(np.median(np.where(conv, hit, cap))),
            "converged_rate": round(float(conv.mean()), 4),
            "non_converged": int((~conv).sum()),
            "confident_within_5": round(float(((hit > 0) & (hit <= 5)).mean()), 4),
            "ever_confident_wrong_rate": round(float(r["wrong_conf"].mean()), 4),
            "accuracy_after_k": [round(float(r["correct"][:, k].mean()), 4) for k in range(kmax)],
            "mean_max_posterior_after_k": [round(float(r["maxp"][:, k].mean()), 4) for k in range(kmax)],
        }
    out["_meta"] = {"n_events_pool": E, "cap": cap, "true_career_counts": {cids[k]: int((true == k).sum()) for k in range(K)}}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--players", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--cap", type=int, default=20)
    ap.add_argument("--player-beta", type=float, default=4.0)
    ap.add_argument("--noise", type=float, default=0.10)
    ap.add_argument("--kmax", type=int, default=10)
    args = ap.parse_args(argv)
    seed_everything(args.seed)
    t0 = time.time()
    r = run(args.players, args.seed, args.cap, args.player_beta, args.noise, args.kmax)
    meta = r.pop("_meta")
    # sensitivity of the headline numbers to the selector's assumed beta (smaller run, same player beta)
    sens = []
    base_beta = sel.BETA
    for b in (2.5, 4.5, 6.0):
        sel.BETA = b
        rb = run(min(500, args.players), args.seed + 1, args.cap, args.player_beta, args.noise, args.kmax)
        sens.append({"selector_beta": b, "n_players": min(500, args.players), **{
            s: {"avg_events_to_confident": rb[s]["avg_events_to_confident"], "non_converged": rb[s]["non_converged"],
                "ever_confident_wrong_rate": rb[s]["ever_confident_wrong_rate"]} for s in ("adaptive", "random", "fixed")}})
    sel.BETA = base_beta
    ks = list(range(1, args.kmax + 1))
    curve = {"k": ks, **{s: r[s]["accuracy_after_k"] for s in STRATEGIES}}
    trained_at = now_iso()
    block = {
        "status": "SYNTHETIC",
        "provenance": "SYNTHETIC",
        "data": (f"{args.players} simulated players: true career uniform over 8; profile = REAL O*NET 31.0 work styles "
                 f"+ N(0, {args.noise}^2); choices sampled from softmax(beta*dot(trait_deltas, profile-0.5)) with player "
                 f"beta {args.player_beta} vs selector beta {sel.BETA} (mis-specified on purpose). Events: "
                 f"{meta['n_events_pool']} non-crunch DRAFT events from events.json."),
        "seed": args.seed,
        "trained_at": trained_at,
        "reproduce": "python ml/eval_selector.py",
        "model_type": "Bayesian player model; next event by max expected information gain (mutual information)",
        "confidence_threshold": sel.CONFIDENT,
        "cap": meta["cap"],
        "n_players": args.players,
        "adaptive": {k: v for k, v in r["adaptive"].items() if not k.endswith("_after_k")},
        "thompson": {k: v for k, v in r["thompson"].items() if not k.endswith("_after_k")},
        "random": {k: v for k, v in r["random"].items() if not k.endswith("_after_k")},
        "fixed": {k: v for k, v in r["fixed"].items() if not k.endswith("_after_k")},
        "curve": curve,
        "beta_sensitivity": sens,
        "winner": min(("adaptive", "random", "fixed"), key=lambda s: r[s]["avg_events_to_confident"]),
        "note": (f"avg_events_to_confident counts players who never reach a correct confident match within {meta['cap']} "
                 "events at the cap; the converged-only mean and non_converged count are reported alongside. "
                 f"Higher selector beta reaches confidence sooner but is wrong-confident more often (beta_sensitivity); "
                 "4.5 was chosen as the middle of that trade-off. Simulated players follow the model family, so this measures selection efficiency, not real-player accuracy."),
        "seconds": round(time.time() - t0, 1),
    }
    write_metrics("selector", block)
    write_json(CURVES_DIR / "selector.json", {
        "status": "SYNTHETIC", "provenance": "SYNTHETIC", "x": "k (events answered)", "y": "accuracy (argmax == true career)",
        "seed": args.seed, "n_players": args.players, "generated_at": trained_at, **curve,
        "mean_max_posterior": {s: r[s]["mean_max_posterior_after_k"] for s in STRATEGIES},
    })
    for s in STRATEGIES:
        x = r[s]
        print(f"{s:9s} avg events to confident {x['avg_events_to_confident']:6.3f} (converged-only "
              f"{x['avg_events_to_confident_converged_only']}, non-converged {x['non_converged']}/{args.players}, "
              f"within 5: {x['confident_within_5']:.3f}, ever confident-wrong {x['ever_confident_wrong_rate']:.3f}) | "
              f"acc@1 {x['accuracy_after_k'][0]:.3f} acc@5 {x['accuracy_after_k'][4]:.3f} acc@10 {x['accuracy_after_k'][9]:.3f}")
    print(f"winner: {block['winner']}; {block['seconds']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
