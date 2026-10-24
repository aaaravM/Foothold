"""Test setup: isolate side effects BEFORE any foothold import.

* api/ on sys.path (tests run as ``python -m pytest api/tests -q`` from the repo root).
* Runtime dir (sqlite) and LLM cache go to a temp dir, never api/.runtime or api/cache/llm.
* OPENAI_API_KEY is set to "" so python-dotenv (override=False) cannot load the real
  key from .env; tests that need a key use a fake one with a mock HTTP transport.
  No test touches the network.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

_TMP = Path(tempfile.mkdtemp(prefix="foothold-tests-"))
os.environ["FOOTHOLD_RUNTIME_DIR"] = str(_TMP / "runtime")
os.environ["FOOTHOLD_LLM_CACHE_DIR"] = str(_TMP / "llm-cache")
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENAI_MODEL"] = ""
os.environ["LLM_MODE"] = "mock"
os.environ["DEMO_MODE"] = "0"
os.environ.pop("OPENAI_REASONING_EFFORT", None)

FAKE_KEY = "sk-test-FAKEKEY-0000000000000000abcd"
FAKE_MODEL = "fake-model-mini"


@pytest.fixture(scope="session", autouse=True)
def _cleanup_tmp():
    yield
    from foothold import checkpoint

    checkpoint.close_checkpointer()  # release the sqlite file so Windows can delete it
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(autouse=True)
def baseline_env(monkeypatch, tmp_path):
    """Each test starts offline: mock mode, no key, private cache dir, fresh LLM state."""
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_MODEL", "")
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setenv("FOOTHOLD_LLM_CACHE_DIR", str(tmp_path / "llm-cache"))
    from foothold import llm

    llm.set_client_factory(None)
    llm.reset_state()
    yield
    llm.set_client_factory(None)
    llm.reset_state()


class FakeOpenAI:
    """OpenAI SDK clients backed by ``httpx2.MockTransport`` (the SDK's HTTP layer).

    mode: "ok" | "401" | "connect" | "refusal". Records every request path.
    """

    def __init__(self, mode: str = "ok", payload: dict[str, Any] | None = None, text: str = "Sounds good.") -> None:
        self.mode = mode
        self.payload = payload or {}
        self.text = text
        self.calls: list[str] = []
        self.bodies: list[dict[str, Any]] = []

    def handler(self, request):  # -> httpx2.Response
        import httpx2

        path = request.url.path
        self.calls.append(path)
        if self.mode == "connect":
            raise httpx2.ConnectError("connection refused", request=request)
        if self.mode == "401":
            return httpx2.Response(
                401,
                json={"error": {"message": "Incorrect API key provided: sk-te****abcd. Find your key at ...",
                                "type": "invalid_request_error", "param": None, "code": "invalid_api_key"}},
            )
        if "/models" in path:
            if path.rstrip("/").endswith("/models"):
                return httpx2.Response(200, json={"object": "list", "data": [{"id": FAKE_MODEL, "object": "model", "created": 1, "owned_by": "test"}]})
            return httpx2.Response(200, json={"id": FAKE_MODEL, "object": "model", "created": 1, "owned_by": "test"})
        if path.endswith("/responses"):
            body = json.loads(request.content or b"{}")
            self.bodies.append(body)
            structured = (body.get("text") or {}).get("format", {}).get("type") == "json_schema"
            content: list[dict[str, Any]]
            if self.mode == "refusal":
                content = [{"type": "refusal", "refusal": "I can't help with that."}]
            else:
                out = json.dumps(self.payload) if structured else self.text
                content = [{"type": "output_text", "text": out, "annotations": []}]
            return httpx2.Response(200, json={
                "id": "resp_test", "object": "response", "created_at": 1, "status": "completed", "model": FAKE_MODEL,
                "output": [{"type": "message", "id": "msg_test", "status": "completed", "role": "assistant", "content": content}],
                "parallel_tool_calls": True, "tool_choice": "auto", "tools": [],
            })
        return httpx2.Response(404, json={"error": {"message": "not found", "type": "invalid_request_error"}})

    def factory(self, kind: str, api_key: str):
        import httpx2
        import openai

        transport = httpx2.MockTransport(self.handler)
        if kind == "sync":
            return openai.OpenAI(api_key=api_key, http_client=httpx2.Client(transport=transport), max_retries=0, timeout=5.0)
        return openai.AsyncOpenAI(api_key=api_key, http_client=httpx2.AsyncClient(transport=transport), max_retries=0, timeout=5.0)

    @property
    def generation_calls(self) -> int:
        return sum(1 for p in self.calls if p.endswith("/responses"))


@pytest.fixture
def fake_openai(monkeypatch):
    """Factory: ``fake_openai(mode=..., payload=..., llm_mode="openai")`` -> FakeOpenAI wired into llm."""
    from foothold import llm

    def make(mode: str = "ok", payload: dict[str, Any] | None = None, text: str = "Sounds good.", llm_mode: str = "openai") -> FakeOpenAI:
        fake = FakeOpenAI(mode=mode, payload=payload, text=text)
        monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
        monkeypatch.setenv("OPENAI_MODEL", FAKE_MODEL)
        monkeypatch.setenv("LLM_MODE", llm_mode)
        llm.set_client_factory(fake.factory)
        return fake

    return make
