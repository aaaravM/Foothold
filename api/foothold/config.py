"""Paths and settings (CONTRACTS §2, §3).

* ``ROOT`` is computed from this file's location, so imports work from any cwd.
* The repo-root ``.env`` is loaded once at import with python-dotenv; variables
  already present in the process environment win (``override=False``).
* :func:`get_settings` re-reads ``os.environ`` on every call (cheap), so tests can
  monkeypatch env vars and long-running code sees the current values.
* The OpenAI key is a ``pydantic.SecretStr``: ``repr``, ``str``, ``dataclasses``-based
  encoders and FastAPI's ``jsonable_encoder`` all show ``**********``. Code that
  really needs the key (only ``foothold.llm``) reads ``settings.api_key``.

Optional overrides (defaults follow the contract):
  OPENAI_FALLBACK_MODEL     -> tried when the primary model errors (CONTRACTS §12)
  OPENAI_REASONING_EFFORT   -> if set (e.g. "low"), sent as reasoning.effort; unset = not sent
  OPENAI_MAX_OUTPUT_TOKENS  -> max_output_tokens per request (default 2048; "0"/"none" = not sent)
  LLM_CACHE_MODEL           -> model name used in LLM cache keys (default: OPENAI_MODEL, else
                               the CONTRACTS §12 model), so DEMO_MODE replays do not depend on .env
  FOOTHOLD_RECORD_CACHE=1   -> also write ``cache="read"`` LLM calls to the cache (only
                               scripts/prewarm_demo.py, with fictional scripted inputs)
  FOOTHOLD_LLM_CACHE_DIR    -> LLM response cache root (default api/cache/llm)
  FOOTHOLD_RUNTIME_DIR      -> sqlite db + LangGraph checkpoints (default api/.runtime)
  FOOTHOLD_ALLOWED_HOSTS    -> extra comma-separated Host names the API answers (LAN demos)
  FOOTHOLD_MAX_BODY_BYTES   -> request body cap (default 262144 = 256 KiB)
  FOOTHOLD_DEBUG=1          -> log stack frames for graph/route failures (file/line/function
                               only: never exception messages, prompts or keys)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from pydantic import SecretStr

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
DEFAULT_MAX_OUTPUT_TOKENS = 2048
DEFAULT_ALLOWED_HOSTS = ("localhost", "127.0.0.1", "[::1]", "testserver")  # testserver = TestClient
DEFAULT_MAX_BODY_BYTES = 256 * 1024


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


def allowed_hosts() -> list[str]:
    """Host header values the API accepts (DNS-rebinding guard): loopback names plus
    FOOTHOLD_ALLOWED_HOSTS (comma-separated, e.g. "192.168.1.20,my-laptop.local")."""
    extra = [h.strip().lower() for h in os.environ.get("FOOTHOLD_ALLOWED_HOSTS", "").split(",") if h.strip()]
    return list(dict.fromkeys([*DEFAULT_ALLOWED_HOSTS, *extra]))


def max_body_bytes() -> int:
    raw = os.environ.get("FOOTHOLD_MAX_BODY_BYTES", "").strip()
    try:
        value = int(raw) if raw else DEFAULT_MAX_BODY_BYTES
    except ValueError:
        value = DEFAULT_MAX_BODY_BYTES
    return value if value > 0 else DEFAULT_MAX_BODY_BYTES


def _flag(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _max_output_tokens(value: str | None) -> int | None:
    raw = (value or "").strip().lower()
    if not raw:
        return DEFAULT_MAX_OUTPUT_TOKENS
    if raw in {"0", "none", "off"}:
        return None
    try:
        n = int(raw)
    except ValueError:
        return DEFAULT_MAX_OUTPUT_TOKENS
    return n if n > 0 else None


@dataclass(frozen=True)
class Settings:
    openai_api_key: SecretStr | None = field(default=None, repr=False)  # never log; use .api_key
    openai_model: str | None = None
    openai_fallback_model: str | None = None
    llm_mode: str = "auto"  # auto | openai | mock
    demo_mode: bool = False
    reasoning_effort: str | None = None
    max_output_tokens: int | None = DEFAULT_MAX_OUTPUT_TOKENS
    llm_cache_model: str | None = None
    record_cache: bool = False
    debug: bool = False

    @property
    def api_key(self) -> str:
        """The raw key ("" when unset). Only foothold.llm should read this."""
        return self.openai_api_key.get_secret_value() if self.openai_api_key is not None else ""

    @property
    def key_present(self) -> bool:
        return bool(self.api_key)


def get_settings() -> Settings:
    """Current settings from the environment (``.env`` already loaded at import)."""
    mode = (_clean(os.environ.get("LLM_MODE")) or "auto").lower()
    if mode not in VALID_LLM_MODES:
        mode = "auto"
    key = _clean(os.environ.get("OPENAI_API_KEY"))
    return Settings(
        openai_api_key=SecretStr(key) if key else None,
        openai_model=_clean(os.environ.get("OPENAI_MODEL")),
        openai_fallback_model=_clean(os.environ.get("OPENAI_FALLBACK_MODEL")),
        llm_mode=mode,
        demo_mode=_flag(os.environ.get("DEMO_MODE")),
        reasoning_effort=_clean(os.environ.get("OPENAI_REASONING_EFFORT")),
        max_output_tokens=_max_output_tokens(os.environ.get("OPENAI_MAX_OUTPUT_TOKENS")),
        llm_cache_model=_clean(os.environ.get("LLM_CACHE_MODEL")),
        record_cache=_flag(os.environ.get("FOOTHOLD_RECORD_CACHE")),
        debug=_flag(os.environ.get("FOOTHOLD_DEBUG")),
    )


def __getattr__(name: str):
    """``config.settings`` is a live view of :func:`get_settings` (PEP 562)."""
    if name == "settings":
        return get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
