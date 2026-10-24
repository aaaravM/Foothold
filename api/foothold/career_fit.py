"""Career-fit model (brief 6.1): 21-trait profile -> ranked O*NET occupations.

Inputs are trait values 0..1 in ``data/processed/traits.json`` order (missing traits count
as 0.5, "no evidence"). Classes are the 42 occupations in ``occupations.json`` (8 Foothold
careers + related O*NET occupations); their ``work_styles`` are REAL O*NET 31.0 percentile
ranks, but the training rows are SYNTHETIC noisy samples around those profiles (see
``make_samples``), so accuracy numbers describe the synthetic task, not real people.

Two scorers:

* ``mlp``: small PyTorch MLP trained by ``ml/train_career_fit.py``; weights in
  ``ml/artifacts/career_fit.pt`` (state_dict, loaded with ``weights_only=True``) plus a JSON
  sidecar ``career_fit.json`` (trait order, class order, layer sizes, metrics).
* ``cosine``: untrained baseline, cosine similarity between (profile - 0.5) and
  (occupation work styles - 0.5). Used automatically when the weights are missing or torch
  fails, and reported with ``trained: False``.

``predict(profile, k=3)`` returns::

    {"model": "mlp"|"cosine", "trained": bool, "note": str,
     "top": [{"career_id", "title", "onet_soc", "probability", "p_overall"}],   # top-k of the 8 careers
     "occupations": [{"onet_soc", "title", "career_id"|None, "probability"}]}    # all 42, ranked

``top[].probability`` is renormalized over the 8 careers; ``p_overall`` is the share over
all 42 occupations. For the cosine baseline the "probabilities" are a softmax of the
similarities (temperature ``COSINE_TEMP``), i.e. a ranking score, not a calibrated probability.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from foothold import config, data

log = logging.getLogger(__name__)

ARTIFACT_PT = config.ROOT / "ml" / "artifacts" / "career_fit.pt"
ARTIFACT_JSON = config.ROOT / "ml" / "artifacts" / "career_fit.json"

HIDDEN = (64, 64)
COSINE_TEMP = 8.0

# Synthetic sample generator defaults (documented in metrics.json "data").
NOISE_SD = 0.12          # Gaussian noise on each trait (scale 0..1)
DROPOUT_MAX = 0.6        # per-sample drop rate ~ U(0, DROPOUT_MAX); dropped traits -> 0.5
SHRINK_RANGE = (0.35, 1.0)  # per-sample shrink toward 0.5 (a short workday reveals a compressed profile)

SAMPLE_DOC = (
    "Synthetic rows around each occupation's REAL O*NET 31.0 work-style profile: x = 0.5 + s*(w + N(0, "
    f"{NOISE_SD}^2) - 0.5) with shrink s ~ U{SHRINK_RANGE}, then each trait is replaced by 0.5 (no evidence) "
    f"with probability p ~ U(0, {DROPOUT_MAX}) per sample; clipped to 0..1."
)


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------


def trait_ids() -> list[str]:
    return list(data.traits_order())


def occupation_table() -> tuple[list[str], list[dict[str, Any]], np.ndarray]:
    """(trait order, occupations, W[n_occ, n_traits]) from occupations.json."""
    traits = trait_ids()
    occs = [o for o in data.occupation_list() if isinstance(o, dict) and o.get("work_styles")]
    W = np.array([[float(o["work_styles"].get(t, 0.5)) for t in traits] for o in occs], dtype=np.float32)
    return traits, occs, W


def career_index(occs: Sequence[dict[str, Any]]) -> list[int]:
    """Row indices of the 8 Foothold careers (in occupations.json order)."""
    return [i for i, o in enumerate(occs) if o.get("career_id")]


def make_samples(
    W: np.ndarray,
    n_per_class: int,
    rng: np.random.Generator,
    *,
    noise_sd: float = NOISE_SD,
    dropout_max: float = DROPOUT_MAX,
    shrink_range: tuple[float, float] = SHRINK_RANGE,
) -> tuple[np.ndarray, np.ndarray]:
    """Noisy synthetic profiles around each row of W. Returns (X[n, T], y[n])."""
    n_cls, n_t = W.shape
    y = np.repeat(np.arange(n_cls), n_per_class)
    base = W[y]
    x = base + rng.normal(0.0, noise_sd, size=base.shape)
    s = rng.uniform(shrink_range[0], shrink_range[1], size=(len(y), 1))
    x = 0.5 + s * (x - 0.5)
    p = rng.uniform(0.0, dropout_max, size=(len(y), 1))
    drop = rng.random(size=base.shape) < p
    x = np.where(drop, 0.5, x)
    return np.clip(x, 0.0, 1.0).astype(np.float32), y.astype(np.int64)


def to_vector(profile: dict[str, float] | Sequence[float] | np.ndarray, traits: Sequence[str] | None = None) -> np.ndarray:
    traits = list(traits or trait_ids())
    if isinstance(profile, dict):
        vals = []
        for t in traits:
            try:
                v = float(profile.get(t, 0.5))
            except (TypeError, ValueError):
                v = 0.5
            vals.append(v if np.isfinite(v) else 0.5)
        return np.clip(np.array(vals, dtype=np.float32), 0.0, 1.0)
    arr = np.asarray(profile, dtype=np.float32).reshape(-1)
    if arr.shape[0] != len(traits):
        raise ValueError(f"profile has {arr.shape[0]} values, expected {len(traits)}")
    return np.clip(np.nan_to_num(arr, nan=0.5), 0.0, 1.0)


# ---------------------------------------------------------------------------
# scorers
# ---------------------------------------------------------------------------


def cosine_scores(X: np.ndarray, W: np.ndarray) -> np.ndarray:
    """Cosine similarity of centred profiles X[n,T] to centred occupations W[k,T] -> [n,k]."""
    Xc = np.atleast_2d(X) - 0.5
    Wc = W - 0.5
    xn = np.linalg.norm(Xc, axis=1, keepdims=True)
    wn = np.linalg.norm(Wc, axis=1, keepdims=True).T
    return (Xc @ Wc.T) / np.maximum(xn * wn, 1e-9)


def softmax(z: np.ndarray, axis: int = -1) -> np.ndarray:
    z = z - z.max(axis=axis, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=axis, keepdims=True)


def build_mlp(n_in: int, n_out: int, hidden: Sequence[int] = HIDDEN, dropout: float = 0.1) -> Any:
    import torch.nn as nn

    layers: list[Any] = []
    prev = n_in
    for h in hidden:
        layers += [nn.Linear(prev, h), nn.ReLU(), nn.Dropout(dropout)]
        prev = h
    layers.append(nn.Linear(prev, n_out))
    return nn.Sequential(*layers)


def mlp_proba(model: Any, X: np.ndarray) -> np.ndarray:
    import torch

    model.eval()
    with torch.no_grad():
        logits = model(torch.from_numpy(np.atleast_2d(X).astype(np.float32) - 0.5))
        return torch.softmax(logits, dim=1).numpy()


# ---------------------------------------------------------------------------
# artifact loading (cached by mtime)
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_cache: dict[str, Any] = {"key": None, "model": None, "meta": None}


def _artifact_key() -> tuple[int, int] | None:
    try:
        return (ARTIFACT_PT.stat().st_mtime_ns, ARTIFACT_JSON.stat().st_mtime_ns)
    except OSError:
        return None


def load_model() -> tuple[Any, dict[str, Any]] | None:
    """(torch model, sidecar meta) or None when the artifact is missing/incompatible."""
    key = _artifact_key()
    if key is None:
        return None
    with _lock:
        if _cache["key"] == key:
            return (_cache["model"], _cache["meta"]) if _cache["model"] is not None else None
        model = meta = None
        try:
            import torch

            meta = json.loads(ARTIFACT_JSON.read_text(encoding="utf-8"))
            traits, occs, _ = occupation_table()
            if meta.get("trait_order") != traits or meta.get("classes") != [o["onet_soc"] for o in occs]:
                raise ValueError("artifact trait/class order does not match the current data files")
            model = build_mlp(len(traits), len(occs), tuple(meta.get("hidden") or HIDDEN), float(meta.get("dropout", 0.1)))
            state = torch.load(ARTIFACT_PT, map_location="cpu", weights_only=True)
            model.load_state_dict(state)
            model.eval()
        except Exception as exc:
            log.warning("career_fit artifact not usable (%s: %s); using cosine baseline", type(exc).__name__, exc)
            model = None
        _cache.update(key=key, model=model, meta=meta)
        return (model, meta) if model is not None else None


def model_info() -> dict[str, Any]:
    loaded = load_model()
    if loaded is None:
        return {"model": "cosine", "trained": False, "artifact": None}
    _, meta = loaded
    return {"model": "mlp", "trained": True, "artifact": "ml/artifacts/career_fit.pt",
            "trained_at": meta.get("trained_at"), "seed": meta.get("seed")}


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def predict(profile: dict[str, float] | Sequence[float], k: int = 3) -> dict[str, Any]:
    traits, occs, W = occupation_table()
    if not occs:
        return {"model": "none", "trained": False, "note": "occupations.json missing", "top": [], "occupations": []}
    x = to_vector(profile, traits)
    loaded = load_model()
    if loaded is not None:
        p = mlp_proba(loaded[0], x)[0]
        model, trained = "mlp", True
        note = ("MLP trained on SYNTHETIC noisy samples around REAL O*NET 31.0 work-style profiles "
                "(ml/train_career_fit.py); probabilities are model outputs, not a guarantee of fit.")
    else:
        p = softmax(COSINE_TEMP * cosine_scores(x, W)[0])
        model, trained = "cosine", False
        note = ("Untrained baseline: cosine similarity between your trait estimate and each occupation's "
                "O*NET work-style profile (both centred at 0.5); scores are a ranking, not probabilities.")
    order = np.argsort(-p, kind="stable")
    occupations = [{"onet_soc": occs[i]["onet_soc"], "title": occs[i].get("title"), "career_id": occs[i].get("career_id"),
                    "probability": round(float(p[i]), 4)} for i in order]
    cidx = career_index(occs)
    pc = p[cidx]
    pc_norm = pc / max(float(pc.sum()), 1e-12)
    corder = np.argsort(-pc_norm, kind="stable")[: max(1, int(k))]
    top = []
    for j in corder:
        o = occs[cidx[j]]
        car = data.get_career(o["career_id"]) or {}
        top.append({"career_id": o["career_id"], "title": car.get("title") or o.get("title"), "onet_soc": o["onet_soc"],
                    "probability": round(float(pc_norm[j]), 4), "p_overall": round(float(pc[j]), 4)})
    return {"model": model, "trained": trained, "note": note, "top": top, "occupations": occupations}
