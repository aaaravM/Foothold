"""Train the career-fit MLP (brief 6.1) and compare it with the cosine baseline.

    python ml/train_career_fit.py [--seed 7] [--per-class 600] [--epochs 60]

Writes ml/artifacts/career_fit.pt (state_dict), ml/artifacts/career_fit.json (sidecar) and the
``career_fit`` key of ml/artifacts/metrics.json. Runs in seconds on CPU.
"""

from __future__ import annotations

import argparse
import sys
import time

import common  # noqa: F401  (puts api/ on sys.path)
from common import ARTIFACTS_DIR, now_iso, seed_everything, write_json, write_metrics

import numpy as np
import torch
import torch.nn as nn

from foothold import career_fit as cf


def topk_acc(P: np.ndarray, y: np.ndarray, k: int) -> float:
    top = np.argsort(-P, axis=1, kind="stable")[:, :k]
    return float(np.mean([y[i] in top[i] for i in range(len(y))]))


def evaluate(P: np.ndarray, y: np.ndarray, cidx: list[int]) -> dict:
    """Overall (42-way) and restricted to the 8 careers (samples of the 8, argmax among the 8)."""
    mask = np.isin(y, cidx)
    remap = {c: j for j, c in enumerate(cidx)}
    y8 = np.array([remap[c] for c in y[mask]])
    P8 = P[mask][:, cidx]
    return {
        "overall": {"top1": round(topk_acc(P, y, 1), 4), "top3": round(topk_acc(P, y, 3), 4), "n": int(len(y))},
        "careers8": {"top1": round(topk_acc(P8, y8, 1), 4), "top3": round(topk_acc(P8, y8, 3), 4), "n": int(mask.sum())},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--per-class", type=int, default=600)
    ap.add_argument("--test-per-class", type=int, default=200)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--lr", type=float, default=3e-3)
    args = ap.parse_args(argv)

    t0 = time.time()
    seed_everything(args.seed)
    traits, occs, W = cf.occupation_table()
    cidx = cf.career_index(occs)
    print(f"{len(occs)} occupations ({len(cidx)} Foothold careers), {len(traits)} traits")

    rng = np.random.default_rng(args.seed)
    Xtr, ytr = cf.make_samples(W, args.per_class, rng)
    Xva, yva = cf.make_samples(W, 50, rng)
    # held-out test set from an independent generator stream
    Xte, yte = cf.make_samples(W, args.test_per_class, np.random.default_rng(args.seed + 1000))

    model = cf.build_mlp(len(traits), len(occs))
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    loss_fn = nn.CrossEntropyLoss()
    Xt = torch.from_numpy(Xtr - 0.5)
    yt = torch.from_numpy(ytr)
    g = torch.Generator().manual_seed(args.seed)
    best = (-1.0, None)
    for ep in range(args.epochs):
        model.train()
        perm = torch.randperm(len(yt), generator=g)
        for i in range(0, len(perm), 256):
            idx = perm[i:i + 256]
            opt.zero_grad()
            loss = loss_fn(model(Xt[idx]), yt[idx])
            loss.backward()
            opt.step()
        va = topk_acc(cf.mlp_proba(model, Xva), yva, 1)
        if va > best[0]:
            best = (va, {k: v.clone() for k, v in model.state_dict().items()})
        if ep % 10 == 0 or ep == args.epochs - 1:
            print(f"epoch {ep:3d} loss {loss.item():.3f} val top1 {va:.3f}")
    model.load_state_dict(best[1])

    P_mlp = cf.mlp_proba(model, Xte)
    P_cos = cf.softmax(cf.COSINE_TEMP * cf.cosine_scores(Xte, W))
    mlp = evaluate(P_mlp, yte, cidx)
    cos = evaluate(P_cos, yte, cidx)
    winner = "mlp" if mlp["overall"]["top1"] > cos["overall"]["top1"] else "cosine"
    winner8 = "mlp" if mlp["careers8"]["top1"] > cos["careers8"]["top1"] else "cosine"

    trained_at = now_iso()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), cf.ARTIFACT_PT)
    write_json(cf.ARTIFACT_JSON, {
        "trait_order": traits, "classes": [o["onet_soc"] for o in occs], "class_titles": [o.get("title") for o in occs],
        "career_ids": [o.get("career_id") for o in occs], "hidden": list(cf.HIDDEN), "dropout": 0.1,
        "input": "trait values 0..1 minus 0.5", "seed": args.seed, "trained_at": trained_at,
        "test": {"mlp": mlp, "cosine": cos},
    })
    n_params = sum(p.numel() for p in model.parameters())
    block = {
        "status": "SYNTHETIC",
        "provenance": "SYNTHETIC",
        "data": (f"{len(occs)} classes = O*NET 31.0 occupations (REAL work-style profiles, percentile ranks); "
                 f"{args.per_class}/class training rows and {args.test_per_class}/class held-out rows are SYNTHETIC. "
                 + cf.SAMPLE_DOC),
        "seed": args.seed,
        "trained_at": trained_at,
        "reproduce": "python ml/train_career_fit.py",
        "model_type": f"MLP {len(traits)}-{'-'.join(map(str, cf.HIDDEN))}-{len(occs)} ({n_params} params), AdamW, {args.epochs} epochs",
        "baseline": f"cosine similarity of centred profiles (softmax temperature {cf.COSINE_TEMP} for ranking)",
        "overall": {"mlp": mlp["overall"], "cosine": cos["overall"]},
        "careers8": {"mlp": mlp["careers8"], "cosine": cos["careers8"]},
        "winner": winner,
        "winner_careers8": winner8,
        "n_test": int(len(yte)),
        "n_classes": len(occs),
        "train_seconds": round(time.time() - t0, 1),
        "artifact": "ml/artifacts/career_fit.pt",
        "note": "Accuracy on synthetic noisy profiles, not on real people; it measures how well the model "
                "recovers an occupation from a partial, noisy work-style profile.",
    }
    write_metrics("career_fit", block)
    print(f"MLP    overall top1 {mlp['overall']['top1']:.4f} top3 {mlp['overall']['top3']:.4f} | "
          f"8 careers top1 {mlp['careers8']['top1']:.4f} top3 {mlp['careers8']['top3']:.4f}")
    print(f"cosine overall top1 {cos['overall']['top1']:.4f} top3 {cos['overall']['top3']:.4f} | "
          f"8 careers top1 {cos['careers8']['top1']:.4f} top3 {cos['careers8']['top3']:.4f}")
    print(f"winner (overall top1): {winner}; winner (8 careers top1): {winner8}; {block['train_seconds']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
