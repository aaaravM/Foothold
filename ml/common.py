"""Shared helpers for the ml/ scripts (CONTRACTS section 10).

* Puts ``api/`` on ``sys.path`` so scripts can ``import foothold``.
* ``seed_everything(seed)`` seeds random, numpy and torch (when installed).
* ``write_metrics(key, block)`` read-merge-writes ONE top-level key of
  ``ml/artifacts/metrics.json`` and checks the required fields
  (status, provenance, data, seed, trained_at, reproduce). Other keys are left untouched.
"""

from __future__ import annotations

import json
import os
import random
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "api"
ML_DIR = ROOT / "ml"
ARTIFACTS_DIR = ML_DIR / "artifacts"
CURVES_DIR = ARTIFACTS_DIR / "curves"
METRICS_PATH = ARTIFACTS_DIR / "metrics.json"

if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

REQUIRED_FIELDS = ("status", "provenance", "data", "seed", "trained_at", "reproduce")


def seed_everything(seed: int) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:  # pragma: no cover
        pass
    try:
        import torch

        torch.manual_seed(seed)
    except ImportError:  # pragma: no cover
        pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def read_metrics(path: Path = METRICS_PATH) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def write_metrics(key: str, block: dict[str, Any], path: Path = METRICS_PATH) -> dict[str, Any]:
    """Merge ``block`` under ``key`` (replacing only that key) and write atomically."""
    missing = [f for f in REQUIRED_FIELDS if f not in block]
    if missing:
        raise ValueError(f"metrics block {key!r} is missing {missing}")
    merged = read_metrics(path)
    merged[key] = block
    _atomic_write_json(path, merged)
    return merged


def write_json(path: Path, obj: Any) -> None:
    _atomic_write_json(path, obj)
