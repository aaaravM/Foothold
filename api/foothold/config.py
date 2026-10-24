"""Paths and settings (CONTRACTS §2, §3).

* ``ROOT`` is computed from this file's location, so imports work from any cwd.
* The repo-root ``.env`` is loaded once at import with python-dotenv; variables
  already present in the process environment win (``override=False``).
* :func:`get_settings` re-reads ``os.environ`` on every call (cheap), so tests can
  monkeypatch env vars and long-running code sees the current values.
* The OpenAI key is never logged and is excluded from ``repr(Settings)``.

Optional overrides (defaults follow the contract):
  FOOTHOLD_LLM_CACHE_DIR  -> LLM response cache root (default api/cache/llm)
  FOOTHOLD_RUNTIME_DIR    -> sqlite db + LangGraph checkpoints (default api/.runtime)
  OPENAI_REASONING_EFFORT -> if set (e.g. "low"), sent as reasoning.effort; unset = not sent
  FOOTHOLD_DEBUG=1        -> log tracebacks for graph/route failures (still no prompts/keys)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

API_DIR = Path(__file__).resolve().parent.parent
ROOT = API_DIR.parent
DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
SCHEMAS_DIR = DATA_DIR / "schemas"
ML_DIR = ROOT / "ml"
ARTIFACTS_DIR = ML_DIR / "artifacts"
ENV_PATH = ROOT / ".env"

load_dotenv(ENV_PATH, override=False)

# Contract defaults; use the functions below at call time so env overrides apply.
CACHE_DIR = API_DIR / "cache" / "llm"
RUNTIME_DIR = API_DIR / ".runtime"
DB_PATH = RUNTIME_DIR / "foothold.db"
CHECKPOINT_DB_PATH = RUNTIME_DIR / "checkpoints.db"

VALID_LLM_MODES = ("auto", "openai", "mock")


def cache_dir() -> Path:
    """LLM response cache root: ``api/cache/llm`` unless FOOTHOLD_LLM_CACHE_DIR is set."""
    override = os.environ.get("FOOTHOLD_LLM_CACHE_DIR", "").strip()
    return Path(override) if override else CACHE_DIR


def runtime_dir() -> Path:
    """Runtime dir (sqlite files): ``api/.runtime`` unless FOOTHOLD_RUNTIME_DIR is set."""
    override = os.environ.get("FOOTHOLD_RUNTIME_DIR", "").strip()
    return Path(override) if override else RUNTIME_DIR


def db_path() -> Path:
    return runtime_dir() / "foothold.db"


def checkpoint_db_path() -> Path:
    return runtime_dir() / "checkpoints.db"


def metrics_path() -> Path:
    return ARTIFACTS_DIR / "metrics.json"


def _flag(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None = field(default=None, repr=False)  # never log
    openai_model: str | None = None
    llm_mode: str = "auto"  # auto | openai | mock
    demo_mode: bool = False
    reasoning_effort: str | None = None
    debug: bool = False

    @property
    def key_present(self) -> bool:
        return bool(self.openai_api_key)


def get_settings() -> Settings:
    """Current settings from the environment (``.env`` already loaded at import)."""
    mode = (_clean(os.environ.get("LLM_MODE")) or "auto").lower()
    if mode not in VALID_LLM_MODES:
        mode = "auto"
    return Settings(
        openai_api_key=_clean(os.environ.get("OPENAI_API_KEY")),
        openai_model=_clean(os.environ.get("OPENAI_MODEL")),
        llm_mode=mode,
        demo_mode=_flag(os.environ.get("DEMO_MODE")),
        reasoning_effort=_clean(os.environ.get("OPENAI_REASONING_EFFORT")),
        debug=_flag(os.environ.get("FOOTHOLD_DEBUG")),
    )


def __getattr__(name: str):
    """``config.settings`` is a live view of :func:`get_settings` (PEP 562)."""
    if name == "settings":
        return get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
