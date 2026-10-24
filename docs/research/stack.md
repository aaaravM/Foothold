# Foothold stack: verified versions and APIs

Retrieved: **Sat Oct 24 11:55:32 PDT 2026** (`date` on the dev box). Every version and API below was checked live that day.

Status legend: **VERIFIED** means read from official docs, the package registry, or the package source code. **INFERENCE** means my reasoning from verified facts. **UNVERIFIED** means not confirmed, with the reason given.

How it was checked:
- `py -3.12 -m pip index versions <pkg>` and `npm view <pkg> version`
- the PyPI JSON API, to list wheel filenames per platform
- `pip download --no-deps` wheels, unzipped into a scratch folder and read, not installed: openai, langgraph, langgraph-checkpoint, langgraph-checkpoint-sqlite, fastapi, sse-starlette, uvicorn, torch-geometric
- `npm pack` tarballs for shadcn and create-next-app
- `next@16.4.3` font files read through jsDelivr/unpkg, because `web/node_modules` did not exist yet

> Windows gotcha found while doing this: on this machine `py` defaults to **3.13** (`py -0` shows `-V:3.13 *`). Always type `py -3.12`, or create the venv with it and use the venv's `python`.
> When curl runs from Git Bash here, `developers.openai.com` fails with schannel `CRYPT_E_REVOCATION_OFFLINE`. Add `--ssl-no-revoke` to fix it.

---

## 0. Pins (all VERIFIED latest on 2026-10-24)

### Python (3.12 venv)
| package | pin | notes |
|---|---|---|
| openai | 3.37.0 | major version 3. `responses.parse` and `chat.completions.parse` both exist |
| langgraph | 1.2.17 | requires langchain-core `>=1.4.7,<2` (latest 1.7.0), langgraph-checkpoint `>=4.3.0,<5` (latest 4.3.0), langgraph-prebuilt `>=1.1.0,<1.2.0` (latest 1.1.1), pydantic `>=2.7.4`, xxhash `>=3.5.0` |
| langgraph-checkpoint-sqlite | 3.1.2 | requires aiosqlite `>=0.20` (latest 0.22.1, pure-Python wheel) and sqlite-vec `>=0.1.6` (latest 0.1.9 ships `py3-none-win_amd64`) |
| fastapi | 0.162.0 | built-in SSE (`fastapi.sse`), added in 0.135.0. Requires starlette `>=0.46.0` (latest 1.10.0) |
| uvicorn[standard] | 0.54.0 | the `uvloop` extra is skipped on win32 by an env marker |
| pydantic | 2.14.1 | |
| ortools | 9.15.6755 | `ortools-9.15.6755-cp312-cp312-win_amd64.whl` (23.9 MB) is on PyPI. Requires numpy>=2.0.2, pandas>=2.0.0, protobuf>=6.33.1,<6.34, absl-py>=2.0.0, immutabledict>=3.0.0 |
| torch | 2.14.1 | the PyPI `torch-2.14.1-cp312-cp312-win_amd64.whl` is 124.1 MB, which is CPU-sized |
| torch-geometric | 2.8.1 | `torch_geometric-2.8.1-py3-none-any.whl`: pure Python |
| sse-starlette | 3.5.1 | optional, only as a fallback (see section 3) |

### JavaScript
| package | latest | notes |
|---|---|---|
| next / create-next-app | 16.4.3 | `web/` is already on next 16.4.3 |
| react / react-dom | 19.3.1 | `web/package.json` pins 19.3.0, which is fine |
| tailwindcss, @tailwindcss/turbopack, @tailwindcss/postcss | 4.3.3 | the scaffold uses the **turbopack** loader (section 6.2) |
| shadcn (CLI) | 4.22.1 | |
| motion (and framer-motion) | 14.6.0 | `motion/react` re-exports all of framer-motion |
| react-force-graph-2d | 1.29.2 | depends on force-graph ^1.52 (latest 1.52.0), react-kapsule ^2.6, prop-types 15. Peer dep: react `*` |
| tw-animate-css | 1.4.0 | version only. I did not check whether shadcn 4.22.1 adds it |
| typescript | 7.0.2 latest | **keep `^5`**: the create-next-app 16.4.3 template writes `"typescript": "^5"` (VERIFIED in its source). TS 7 compatibility with Next 16.4 is UNVERIFIED |

### Copy-paste install (Git Bash, run from the folder that will own the venv)
```bash
py -3.12 -m venv .venv
source .venv/Scripts/activate            # PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install "openai==3.37.0" "langgraph==1.2.17" "langgraph-checkpoint-sqlite==3.1.2" \
  "fastapi==0.162.0" "uvicorn[standard]==0.54.0" "pydantic==2.14.1" "ortools==9.15.6755"
python -m pip install "torch==2.14.1"            # official Windows+CPU command is plain PyPI (see 5.1)
python -m pip install "torch-geometric==2.8.1"   # do NOT install pyg_lib / torch_scatter / torch_sparse
```

---

## 1. OpenAI

### 1.1 Docs location (VERIFIED)
- `https://platform.openai.com/docs/models` now returns **301** to `https://developers.openai.com/api/docs/models`.
- Add `.md` to any docs URL to get Markdown, e.g. `https://developers.openai.com/api/docs/models/gpt-6-luna.md`.
- The page has three featured models: `gpt-6-astra` (flagship), `gpt-6.1-sol` (balanced), and `gpt-6-luna` (for cost-sensitive, high-volume work).

### 1.2 Recommendation
```
OPENAI_MODEL=gpt-6-luna            # primary: cheapest current-gen, fast
OPENAI_FALLBACK_MODEL=gpt-5.6-luna # fallback: previous gen, same reasoning-effort surface
OPENAI_REASONING_EFFORT=low        # "none" for snappy coworker chat; "low" for extraction/grading
```
Second fallback: `gpt-5.4-mini`. Do **not** use `gpt-5.4-nano`, because its model page marks it **Deprecated**.

| model id | reasoning.effort values (default) | price per 1M tokens, in / cached in / out | context / max out | knowledge cutoff | Chat Completions? |
|---|---|---|---|---|---|
| `gpt-6-luna` | none, low, **medium**, high, xhigh, max | $0.10 / $0.01 / $0.50 (cache writes $0.125) | 1,050,000 / 128,000 | May 18, 2026 | Yes. Function calling there only with `reasoning_effort: "none"`. Use Responses for tools |
| `gpt-5.6-luna` | none, low, **medium**, high, xhigh, max | $0.20 / $0.02 / $1.20 | 1,050,000 / 128,000 | Feb 16, 2026 | Yes (structured_outputs and function_calling listed) |
| `gpt-5.4-mini` (snapshot `gpt-5.4-mini-2026-03-17`) | **none**, low, medium, high, xhigh | $0.75 / $0.075 / $4.50 | 400,000 / 128,000 | Aug 31, 2025 | Yes |
| `gpt-6.1-sol` (not for us) | low, **medium**, high, xhigh, max. No `none` or `minimal` | $2 / $0.10 / $10 | 1,050,000 / 128,000 | Apr 30, 2026 | No tools in Chat Completions |

All of the above are VERIFIED from the model pages. `gpt-6-luna` lists the features streaming, structured_outputs, function_calling, and prompt_caching. Its only snapshot is `gpt-6-luna`. On every model page, prompts over 272K input tokens cost more, which does not matter for us.

### 1.3 Parameter rules (VERIFIED: GPT-6 guide, "Update API and model parameters")
- Responses API: `reasoning={"effort": "low"}`. Chat Completions: `reasoning_effort="low"`.
- **When effort is not `"none"`, do not send `temperature`, `top_p`, or `top_logprobs`.** On Chat Completions, also drop `logprobs`. On Responses, do not add `message.output_text.logprobs` to `include`. Simplest rule for us: never send temperature or top_p.
- The SDK's `ReasoningEffort` Literal is `"none" | "minimal" | "low" | "medium" | "high" | "xhigh" | "max"`. The `gpt-6-luna` page does **not** list `minimal`, so don't send it.
- Use the Responses API for reasoning plus tools.
- On GPT-6, prompt caching uses `prompt_cache_options.ttl` (`"30m"`) in place of `prompt_cache_retention`. This only matters if you set it.
- Structured Outputs schema rules (VERIFIED, structured-outputs guide):
  - every field must be **required**. To make a field optional, type it `X | None` and give it **no default**.
  - the root must be an object, not `anyOf`
  - a schema can have at most 5000 properties and 10 levels of nesting
  - `strict: true` with an unsupported schema returns an error
  - INFERENCE: avoid Pydantic `Field(ge=..., le=...)` and similar numeric constraints, because I did not check which keywords strict mode supports

### 1.4 SDK usage (VERIFIED against openai 3.37.0 source)
- `client.responses.parse(model=..., input=str|list, instructions=..., text_format=PydanticModel, reasoning={...}, max_output_tokens=..., verbosity="low"|"medium"|"high", store=..., prompt_cache_key=..., safety_identifier=...)` returns a `ParsedResponse`. Read the result from `.output_parsed`. Passing both `text={"format":...}` and `text_format` raises `TypeError`.
- `client.chat.completions.parse(model=..., messages=[...], response_format=PydanticModel, reasoning_effort=...)` puts the result at `.choices[0].message.parsed`. It is top level, **not** `client.beta`.
- `AsyncOpenAI` has the same methods, with `await`.
- `client.responses.stream(...)` exists and also accepts `text_format`. The text delta event type is `"response.output_text.delta"`.
- Exception classes (`from openai import ...`): `NotFoundError`, `BadRequestError`, `RateLimitError`, `APIConnectionError`, `APITimeoutError`, `InternalServerError`, `AuthenticationError`, `LengthFinishReasonError`, `ContentFilterFinishReasonError`.
- The docs' own Python example is `client.responses.parse(..., text_format=Model)` followed by `response.output_parsed`. For a manual check, look at `response.status == "incomplete"` and `response.incomplete_details.reason == "max_output_tokens"`. A refusal shows up as a content item with `type == "refusal"`.

```python
# minimal: structured output with model fallback (async, FastAPI-friendly)
import os
from openai import AsyncOpenAI, NotFoundError, BadRequestError, RateLimitError, APIConnectionError, InternalServerError
from pydantic import BaseModel

client = AsyncOpenAI()  # uses OPENAI_API_KEY
MODELS = [os.getenv("OPENAI_MODEL", "gpt-6-luna"), os.getenv("OPENAI_FALLBACK_MODEL", "gpt-5.6-luna")]
EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "low")

class SkillHit(BaseModel):
    skill: str
    evidence: str
    confidence: float
    onet_element_id: str | None   # "optional" = nullable, still required, no default

class SkillReport(BaseModel):
    summary: str
    skills: list[SkillHit]

async def grade_transcript(transcript: str) -> SkillReport:
    last: Exception | None = None
    for model in MODELS:
        try:
            r = await client.responses.parse(
                model=model,
                instructions="Identify workplace skills the student demonstrated. Be specific.",
                input=transcript,
                text_format=SkillReport,
                reasoning={"effort": EFFORT},      # no temperature/top_p
                max_output_tokens=4000,            # reasoning tokens count here too
            )
            if r.output_parsed is None:            # refusal or incomplete
                raise RuntimeError(f"unparsed: status={r.status}")
            return r.output_parsed
        except (NotFoundError, BadRequestError, RateLimitError, APIConnectionError, InternalServerError, RuntimeError) as e:
            last = e                               # try the fallback model
    raise last  # type: ignore[misc]

# Chat Completions variant
# c = await client.chat.completions.parse(model=MODELS[0], messages=[...], response_format=SkillReport, reasoning_effort="none")
# report = c.choices[0].message.parsed
```

---

## 2. LangGraph 1.2.17 (VERIFIED against wheel source)

Imports:
```python
import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END, add_messages, MessagesState
from langgraph.types import Send, Command, interrupt, Interrupt, StreamMode, Durability
from langgraph.config import get_stream_writer, get_config
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver              # pkg: langgraph-checkpoint-sqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver     # needs aiosqlite (auto-installed)
```

Key facts:
- `StateGraph(state_schema, context_schema=None, *, input_schema=None, output_schema=None)`. `config_schema` is deprecated in favor of `context_schema`.
- `add_conditional_edges(source, path, path_map: dict | list[str] | None)`. `path` can return a node name, a list of names, or `Send` objects.
- `Send(node, arg, *, timeout=None)`. `arg` is the input state for that one invocation, and it can use a different schema from the main graph.
- `Command(graph=None, update=None, resume=None, goto=())`.
- `interrupt(value, *, response_schema=None)`:
  - it **needs a checkpointer**
  - on resume, the node **re-runs from its start**
  - several `interrupt()` calls in one node are matched to resume values by order
  - `response_schema` (Pydantic, TypedDict, or dataclass) validates the resume value, and `interrupt()` returns the validated object
- Resume by calling `graph.invoke(Command(resume=value), config)` (or stream/astream) with the **same `thread_id`**.
- An interrupt shows up in `stream_mode="updates"` as `{"__interrupt__": (Interrupt(value=..., id=...),)}`.
- `invoke(..., version="v2")` returns `GraphOutput(value=..., interrupts=(...))`. With the default `version="v1"`, the result dict has the `"__interrupt__"` key.
- `stream`/`astream(input, config, *, context=None, stream_mode=None, output_keys=None, interrupt_before=None, interrupt_after=None, durability=None, subgraphs=False, debug=None, version="v1")`:
  - `StreamMode` is `"values" | "updates" | "checkpoints" | "tasks" | "debug" | "messages" | "custom"`.
  - With v1, a single mode yields plain data. A list of modes yields `(mode, data)` tuples. `subgraphs=True` adds a namespace to each item.
  - With **`version="v2"`**, every item is a dict `{"type": <mode>, "ns": tuple, "data": ...}`. This is the easiest shape to forward as SSE.
  - `updates` data is `{node_name: update}` and may contain `__interrupt__`.
  - `tasks` sends a start event `{id, name, input, triggers}` and a result event `{id, name, error, interrupts, result}`.
  - `messages` only captures LangChain chat-model tokens. We call the OpenAI SDK directly, so push our own deltas with `get_stream_writer()` and `stream_mode="custom"`.
  - `durability` is `"sync"`, `"async"` (default), or `"exit"`. `checkpoint_during` is deprecated.
- `SqliteSaver.from_conn_string(path)` is a **sync context manager** that opens sqlite3 with `check_same_thread=False`. The sync saver's async methods point you to `AsyncSqliteSaver`, so use **`AsyncSqliteSaver.from_conn_string(path)`** (an async context manager) with `ainvoke`/`astream`.

```python
class DayState(TypedDict):
    student_id: str
    tasks: list[str]
    results: Annotated[list[dict], operator.add]   # reducer: parallel branches append
    approved: bool | None

class TaskIn(TypedDict):
    task: str

def plan(s: DayState) -> dict:
    return {"tasks": ["reply to client email", "triage 3 tickets", "standup update"]}

def fan_out(s: DayState) -> list[Send]:                 # parallel map step
    return [Send("run_task", {"task": t}) for t in s["tasks"]]

def run_task(s: TaskIn) -> dict:
    get_stream_writer()({"kind": "progress", "task": s["task"]})   # -> stream_mode="custom"
    return {"results": [{"task": s["task"], "score": 3}]}

def review(s: DayState) -> dict:
    # anything above this line re-runs on resume: keep it idempotent
    ok = interrupt({"ask": "Submit your workday?", "results": s["results"]})
    return {"approved": bool(ok)}

def after_review(s: DayState) -> str:
    return "finish" if s["approved"] else "plan"

b = StateGraph(DayState)
b.add_node("plan", plan); b.add_node("run_task", run_task)
b.add_node("review", review); b.add_node("finish", lambda s: {})
b.add_edge(START, "plan")
b.add_conditional_edges("plan", fan_out, ["run_task"])
b.add_edge("run_task", "review")                         # runs once after all parallel tasks
b.add_conditional_edges("review", after_review, {"finish": "finish", "plan": "plan"})
b.add_edge("finish", END)

# sync smoke test (data/ folder must exist; sqlite will not create folders)
with SqliteSaver.from_conn_string("data/foothold.sqlite") as saver:
    g = b.compile(checkpointer=saver)
    cfg = {"configurable": {"thread_id": "sim-1"}}
    for part in g.stream({"student_id": "s1", "tasks": [], "results": []}, cfg,
                         stream_mode=["updates", "custom"], version="v2"):
        print(part["type"], part["data"])                # last update carries "__interrupt__"
    for part in g.stream(Command(resume=True), cfg, stream_mode="updates", version="v2"):
        print(part["type"], part["data"])
```

---

## 3. FastAPI Server-Sent Events

**Recommendation: use FastAPI's built-in SSE** (`fastapi.sse`, FastAPI >= 0.135.0, and we pin 0.162.0). It needs no extra dependency. VERIFIED from the docs page `https://fastapi.tiangolo.com/tutorial/server-sent-events/` and the 0.162.0 source.
- Set `response_class=EventSourceResponse` and `yield` items from an async (or sync) generator endpoint.
- **Any HTTP method works, POST included.**
- Plain objects are JSON-encoded into `data:`. `ServerSentEvent(data=..., event=..., id=..., retry=..., comment=...)` gives full control.
- **Every `data` value is JSON-encoded, even strings**, so `"hi"` arrives on the wire with quotes. Use `raw_data=` for unencoded text. `data` and `raw_data` cannot be combined.
- Automatic behavior:
  - sends a `: ping` comment every **15 s** when the stream is idle
  - sets `Cache-Control: no-cache` and `X-Accel-Buffering: no`
  - pulls items in a producer task, with cancellation checkpoints
- For reconnects, read the `Last-Event-ID` header: `last_event_id: Annotated[str | None, Header()] = None`.
- Don't mix packages. sse-starlette also exports classes named `EventSourceResponse` and `ServerSentEvent`.

```python
from collections.abc import AsyncIterable
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.sse import EventSourceResponse, ServerSentEvent
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from pydantic import BaseModel

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSqliteSaver.from_conn_string("data/foothold.sqlite") as saver:
        app.state.graph = b.compile(checkpointer=saver)      # builder from section 2
        yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
                   allow_methods=["*"], allow_headers=["*"])

class TurnIn(BaseModel):
    thread_id: str
    student_id: str | None = None
    resume: bool | dict | str | None = None

@app.post("/api/sim/stream", response_class=EventSourceResponse)
async def sim_stream(body: TurnIn, request: Request) -> AsyncIterable[ServerSentEvent]:
    g = request.app.state.graph
    cfg = {"configurable": {"thread_id": body.thread_id}}
    inp = Command(resume=body.resume) if body.resume is not None else {
        "student_id": body.student_id, "tasks": [], "results": []}
    async for part in g.astream(inp, cfg, stream_mode=["updates", "custom"], version="v2"):
        yield ServerSentEvent(event=part["type"], data=jsonable_encoder(part["data"]))
    yield ServerSentEvent(event="done", data={"thread_id": body.thread_id})
```

Browser client. `EventSource` only does GET, so use fetch streaming for POST:
```ts
export async function streamSSE(url: string, body: unknown, onEvent: (ev: string, data: any) => void, signal?: AbortSignal) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
  const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += value;
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, i); buf = buf.slice(i + 2);
      let ev = "message"; const data: string[] = [];
      for (const line of frame.split("\n")) {
        if (line.startsWith(":")) continue;                 // keep-alive ping
        if (line.startsWith("event:")) ev = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
      }
      if (data.length) onEvent(ev, JSON.parse(data.join("\n")));
    }
  }
}
```

Fallbacks:
- `sse-starlette==3.5.1`: `from sse_starlette import EventSourceResponse, ServerSentEvent, JSONServerSentEvent`, then `return EventSourceResponse(gen(), ping=15, send_timeout=30, shutdown_grace_period=2)`. The constructor also takes `sep`, `ping_message_factory`, `client_close_handler_callable`, and `shutdown_event`. It hooks uvicorn's `should_exit` for shutdown. VERIFIED in source.
- A plain `StreamingResponse(media_type="text/event-stream")` works, but you must format frames and send pings yourself. Not recommended.

Windows caveats:
- VERIFIED, uvicorn 0.54.0 `loops/asyncio.py`: on win32 uvicorn uses `ProactorEventLoop`, **but with `--reload` or `--workers` it switches to `SelectorEventLoop`**. Asyncio subprocess APIs don't work under the selector loop on Windows, so don't call `asyncio.create_subprocess_*` in handlers. Also avoid `--workers` with SQLite checkpoints.
- VERIFIED flag: open SSE streams can hold up reload and shutdown, so run with `--timeout-graceful-shutdown 2`:
  `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 2`
- INFERENCE (not tested here): uvicorn binds `127.0.0.1` by default, but Node may resolve `localhost` to `::1` first. In server-side code (Next route handlers or server actions) call `http://127.0.0.1:8000`.
- UNVERIFIED (not tested): proxying SSE through Next.js `rewrites` may buffer or compress the stream. Have the browser call FastAPI directly, with CORS as above, and don't add `GZipMiddleware` to the API.
- Run OR-Tools solves and torch inference inside `await asyncio.to_thread(...)` so they don't block the event loop. SSE pings are sent by the same loop.

---

## 4. OR-Tools CP-SAT 9.15 (VERIFIED)

- Install: `python -m pip install "ortools==9.15.6755"`. The cp312 win_amd64 wheel exists.
- Import: `from ortools.sat.python import cp_model`. Create `cp_model.CpModel()` and `cp_model.CpSolver()`.
- Methods are **snake_case** in the docs and the current `stable` source. CamelCase `Solve` still exists. The methods include:
  - variables: `new_int_var(lb, ub, name)`, `new_bool_var(name)`, `new_interval_var`
  - constraints: `add(expr)`, `.only_enforce_if(lit)`, `add_exactly_one`, `add_bool_or`, `add_implication`, `add_max_equality`, `add_no_overlap`, `add_cumulative`, `add_hint`
  - objective: `minimize`, `maximize`
  - solving and results: `solver.solve(model[, callback])`, `value`, `boolean_value`, `objective_value`, `wall_time`, `status_name(status)`
- Statuses: `cp_model.OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `MODEL_INVALID`, `UNKNOWN`.
- Parameters, from `sat_parameters.proto` on the `stable` branch:
  - `solver.parameters.max_time_in_seconds = 2.0` (default is inf)
  - `solver.parameters.num_workers = 8`: `0` (the default) uses all cores and `1` means no parallelism. `num_search_workers` is the **deprecated** name
  - `random_seed` (default 1), `log_search_progress` (default False), `enumerate_all_solutions`
- CP-SAT is integer-only. INFERENCE: scale dollars and hours to ints.

```python
from ortools.sat.python import cp_model

def pick_pathway(options: list[dict], budget: int, max_months: int, min_wage_cents: int):
    # options: [{"id": "cert-hvac", "kind": "certificate", "cost": 3200, "months": 9, "wage": 2650, "fit": 82}, ...]
    m = cp_model.CpModel()
    x = {o["id"]: m.new_bool_var(o["id"]) for o in options}
    m.add_exactly_one(x.values())
    m.add(sum(o["cost"] * x[o["id"]] for o in options) <= budget)
    m.add(sum(o["months"] * x[o["id"]] for o in options) <= max_months)
    m.add(sum(o["wage"] * x[o["id"]] for o in options) >= min_wage_cents)
    m.maximize(sum(o["fit"] * x[o["id"]] for o in options))
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = 2.0
    s.parameters.num_workers = 8
    st = s.solve(m)                                  # in FastAPI: await asyncio.to_thread(s.solve, m)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"choice": [k for k, v in x.items() if s.boolean_value(v)], "score": s.objective_value,
                "status": s.status_name(st)}
    return {"choice": [], "status": s.status_name(st)}   # e.g. INFEASIBLE -> relax constraints in UI
```

---

## 5. PyTorch (CPU) and PyG

### 5.1 torch (VERIFIED)
- On pytorch.org/get-started/locally (Stable **2.14.1**, Python 3.10-3.14), the selector for **Windows + Pip + CPU** gives `pip3 install torch torchvision`, with **no index URL**. So on Windows the PyPI wheel is the CPU build. Linux CPU is the case that needs `--index-url https://download.pytorch.org/whl/cpu`.
- Our command, with no torchvision needed: `python -m pip install "torch==2.14.1"`.
- Explicit-CPU alternative: `python -m pip install "torch==2.14.1" --index-url https://download.pytorch.org/whl/cpu`. VERIFIED that `torch-2.14.1+cpu-cp312-cp312-win_amd64.whl` is on that index. I did not check whether that index also mirrors all of torch's dependencies, so prefer the plain PyPI command.

### 5.2 torch_geometric 2.8.1 (VERIFIED)
- It is a pure-Python wheel (`py3-none-any`, 1.3 MB). Its dependencies are aiohttp, fsspec, jinja2, numpy, psutil>=5.8.0, pyparsing, requests, tqdm, and xxhash. xxhash 4.0.2 ships cp312 win_amd64, and the rest are standard. INFERENCE: it installs cleanly on Windows CPU.
- The PyG docs say that from 2.3 on, nothing beyond PyTorch is required, and that pyg-lib, torch-scatter, and torch-sparse are optional. Their extension-wheel table stops at **torch 2.12.\***, so there are **no extension wheels for torch 2.14**. Don't install them.
- The `SAGEConv` and `HeteroConv` sources import only torch and torch_geometric internals, so they work without the extensions. `SAGEConv(in_channels: int | (int, int), out_channels, aggr="mean", normalize=False, root_weight=True, project=False, bias=True)`. Use `-1` for lazy input size.
- **`NeighborLoader` and the samplers need pyg-lib or torch-sparse**, so do full-batch training on our small graph.
- `T.ToUndirected()` adds reverse edge types named `rev_<relation>`. `torch_geometric.utils.negative_sampling` exists.

```python
import torch, torch_geometric.transforms as T
from torch_geometric.data import HeteroData
from torch_geometric.nn import HeteroConv, SAGEConv

data = HeteroData()
data["student"].x = torch.randn(200, 24)
data["course"].x = torch.randn(60, 32)
src, dst = torch.randint(0, 200, (900,)), torch.randint(0, 60, (900,))
data["student", "took", "course"].edge_index = torch.stack([src, dst])
data = T.ToUndirected()(data)            # adds ("course", "rev_took", "student")

def layer(h):  # SAGEConv works on bipartite edges (no self-loops)
    return HeteroConv({("student", "took", "course"): SAGEConv((-1, -1), h),
                       ("course", "rev_took", "student"): SAGEConv((-1, -1), h)}, aggr="sum")

class Rec(torch.nn.Module):
    def __init__(self, h=64):
        super().__init__(); self.c1, self.c2 = layer(h), layer(h)
    def forward(self, x, ei):
        x = {k: v.relu() for k, v in self.c1(x, ei).items()}
        return self.c2(x, ei)

model = Rec()
with torch.no_grad():                    # materialize lazy (-1) params BEFORE making the optimizer
    model(data.x_dict, data.edge_index_dict)
opt = torch.optim.Adam(model.parameters(), lr=1e-2)
# score(student i, course j) = (z["student"][i] * z["course"][j]).sum(); train with BCE on edges vs negative_sampling
```

---

## 6. Next.js 16.4.3 front end

### 6.1 create-next-app (VERIFIED)
- `npx create-next-app@latest` installs **16.4.3**.
- Documented flags: `--ts|--js`, `--tailwind`, `--react-compiler`, `--cache-components`, `--eslint|--biome|--no-linter`, `--app`, `--api`, `--src-dir`, `--turbopack|--webpack`, `--import-alias <alias>`, `--empty`, `--use-npm|--use-pnpm|--use-yarn|--use-bun`, `-e/--example`, `--example-path`, `--reset-preferences`, `--skip-install`, `--disable-git`, `--agents-md`, `--agent-feedback|--no-agent-feedback`, `--yes`, plus `--no-*` to negate any of them.
- The recommended defaults are TypeScript, ESLint, Tailwind, App Router, **Cache Components**, and AGENTS.md. There is no React Compiler and no `src/`. Turbopack is the default.
- `web/` already exists, with `src/app/` and an `@/*` alias.

### 6.2 What the scaffold contains (VERIFIED by reading `web/` and the create-next-app 16.4.3 source)
- Tailwind v4 is wired through the **`@tailwindcss/turbopack` loader** in `next.config.ts` (`turbopack.rules["*.css"].loaders = ["@tailwindcss/turbopack"]`). There is **no `postcss.config.mjs`**. The create-next-app source picks `@tailwindcss/turbopack` for Turbopack and `@tailwindcss/postcss` plus `postcss.config.mjs` for Webpack.
  - Don't add a PostCSS config.
  - INFERENCE: `next dev --webpack` or `next build --webpack` would skip Tailwind unless you switch to `@tailwindcss/postcss`.
- `next.config.ts` sets `cacheComponents: true` and `partialPrefetching: true`. Per the docs, when Cache Components is on:
  - data fetching is dynamic by default, and you cache with `"use cache"`, `cacheLife`, or `cacheTag`
  - Partial Prerendering is the default
  - **no `runtime` export is allowed** in route segment config
  - navigation keeps the previous routes mounted inside React `<Activity mode="hidden">`, so **effects are cleaned up on hide and re-run on show**. Close fetch/SSE streams in `useEffect` cleanup with an `AbortController`.
  - INFERENCE: wrap components that read request data in `<Suspense>`.
- Layouts use the global helper type `LayoutProps<"/">`.
- `globals.css` has `@import "tailwindcss";` and `@theme inline {...}`. The `body` rule hard-codes `font-family: Arial, Helvetica, sans-serif;`. Remove that line, or set it to `var(--font-sans)`, or the next/font setup won't apply.

### 6.3 Fonts: `next/font/google` exports all three (VERIFIED in next@16.4.3 `font-data.json` and `index.d.ts`)
| export | weights | variable axes | styles | subsets |
|---|---|---|---|---|
| `Mona_Sans` | 200-900 + `variable` | `wght` 200-900, `wdth` 75-125 (pass `axes: ["wdth"]`) | normal, italic | latin, latin-ext, vietnamese |
| `Hubot_Sans` | 200-900 + `variable` | `wght` 200-900, `wdth` 75-125 | normal, italic | latin, latin-ext, vietnamese |
| `Martian_Mono` | 100-800 + `variable` | `wght` 100-800, `wdth` 75-112.5 | normal only | cyrillic, cyrillic-ext, latin, latin-ext |

The options object is optional for all three, because they are variable fonts.
```tsx
// src/app/layout.tsx
import { Mona_Sans, Hubot_Sans, Martian_Mono } from "next/font/google";
const mona = Mona_Sans({ subsets: ["latin"], variable: "--font-mona-sans", axes: ["wdth"], display: "swap" });
const hubot = Hubot_Sans({ subsets: ["latin"], variable: "--font-hubot-sans", axes: ["wdth"], display: "swap" });
const martian = Martian_Mono({ subsets: ["latin"], variable: "--font-martian-mono", display: "swap" });
// <html className={`${mona.variable} ${hubot.variable} ${martian.variable} h-full antialiased`}>
```
```css
/* globals.css */
@theme inline {
  --font-sans: var(--font-mona-sans);
  --font-heading: var(--font-hubot-sans);   /* -> font-heading utility */
  --font-mono: var(--font-martian-mono);
}
```

### 6.4 shadcn CLI 4.22.1 (VERIFIED in the npm tarball)
- `init` (alias `create`) takes `[components...]` and these options:
  - `-t, --template <next|start|vite|react-router|laravel|astro>`
  - `-b, --base <base|radix|aria>`: the component library
  - `-p, --preset [name]`
  - `-d, --defaults`: equivalent to `--template=next --preset=base-nova`
  - `-y, --yes` (default **true**), `-f, --force`, `-c, --cwd <dir>`, `-n, --name`, `-s, --silent`
  - `--monorepo` / `--no-monorepo`, `--css-variables` / `--no-css-variables` (default on), `--rtl` / `--no-rtl`, `--pointer` / `--no-pointer`, `--reinstall` / `--no-reinstall`
- Style presets in the CLI: nova (Lucide / Geist), vega (Lucide / Inter), maia (Hugeicons / Figtree), lyra (Phosphor / JetBrains Mono), mira (Hugeicons / Inter), luma (Lucide / Inter), sera (Lucide / Noto Sans + Playfair Display), rhea (Lucide / Inter).
- For Tailwind v4, the CLI only checks that a Tailwind CSS file exists (`src/app/globals.css` with `@import "tailwindcss"`). The 4.22.1 dist has no PostCSS-config requirement.
- Non-interactive commands, run inside `web/`:
```bash
npx shadcn@4.22.1 init --defaults --yes          # next template, base-nova preset (Base UI library)
# Radix instead of Base UI: `--base radix` is a real option; the matching preset name format is UNVERIFIED
#   (defaults use "base-nova", so likely "radix-nova") -> check with: npx shadcn@4.22.1 init --help
npx shadcn@4.22.1 add button card dialog tabs badge progress sonner --yes   # add: -y -o(--overwrite) -a(--all) -p(--path) -s --dry-run
```
  - `add` options: `-y, --yes`, `-o, --overwrite`, `-c, --cwd`, `-a, --all`, `-p, --path`, `-s, --silent`, `--dry-run`, `--diff [path]`, `--view [path]`.
  - UNVERIFIED: which component names exist in the registry. I did not query it.
  - The official Next.js install page shows `shadcn@latest init -t next` for a new project, `shadcn@latest init` for an existing one, and `shadcn@latest add card`.

### 6.5 Motion 14.6.0 (VERIFIED)
- Install with `npm i motion@14.6.0`. The peer deps are react and react-dom `^18 || ^19`, and the docs ask for React 18.2 or newer.
- In a `"use client"` file: `import { motion, AnimatePresence, useReducedMotion } from "motion/react"`. `motion/react` re-exports all of framer-motion.
- In a Server Component file: `import * as motion from "motion/react-client"`.
- The package also exports `motion/react-m`, `motion/react-mini`, `motion/mini`, and `motion/debug`.

### 6.6 Force-directed graph: react-force-graph-2d 1.29.2 (VERIFIED README and npm)
- Import with `import ForceGraph2D from "react-force-graph-2d"`. It renders to canvas, and `width`/`height` default to the **window** size, so it must run client-only.
- **`dynamic(..., { ssr: false })` is not allowed in Server Components.** The Next docs say to put it inside a Client Component.
- Robust pattern: put the graph, and its `ref`, in its own client file. Then lazy-load *that file* with `ssr:false`, so the ref never has to pass through `next/dynamic`. INFERENCE: this avoids ref-forwarding doubts.
- Props: `graphData={{nodes, links}}`, `nodeId` (default `"id"`), `nodeLabel`, `nodeVal`, `nodeColor`, `nodeAutoColorBy`, `nodeCanvasObject`, `nodeCanvasObjectMode`, `linkColor`, `linkWidth`, `linkDirectionalArrowLength`, `linkDirectionalParticles`, `backgroundColor`, `width`, `height`, `warmupTicks` (0), `cooldownTicks` (Infinity), `onEngineStop`, `onNodeClick`, `onNodeHover`, `enableNodeDrag` (true).
- Ref methods: `zoomToFit(ms?, px?, filterFn?)`, `centerAt(x?, y?, ms?)`, `zoom(k?, ms?)`, `d3Force(name, fn?)`, `d3ReheatSimulation()`, `emitParticle(link)`, `pauseAnimation()`, `resumeAnimation()`, `screen2GraphCoords`, `graph2ScreenCoords`.
```tsx
// src/components/graph/SkillGraphCanvas.tsx
"use client";
import { useRef } from "react";
import ForceGraph2D from "react-force-graph-2d";
export default function SkillGraphCanvas({ data, width, height }: { data: { nodes: any[]; links: any[] }; width: number; height: number }) {
  const fg = useRef<any>(null);
  return <ForceGraph2D ref={fg} graphData={data} width={width} height={height} nodeAutoColorBy="group"
    nodeLabel="name" cooldownTicks={120} onEngineStop={() => fg.current?.zoomToFit(400, 40)} />;
}
// src/components/graph/SkillGraph.tsx
"use client";
import dynamic from "next/dynamic";
export const SkillGraph = dynamic(() => import("./SkillGraphCanvas"), { ssr: false, loading: () => <div className="h-96 animate-pulse" /> });
```

---

## 7. Sources (all fetched 2026-10-24)
- OpenAI models: https://developers.openai.com/api/docs/models (redirect target of https://platform.openai.com/docs/models). Model pages: https://developers.openai.com/api/docs/models/gpt-6-luna, .../gpt-5.6-luna, .../gpt-5.4-mini, .../gpt-5.4-nano, .../gpt-6.1-sol
- OpenAI GPT-6 guide (parameter rules): https://developers.openai.com/api/docs/guides/latest-model ; Structured Outputs: https://developers.openai.com/api/docs/guides/structured-outputs
- openai-python 3.37.0 wheel (PyPI): `openai/resources/responses/responses.py`, `openai/resources/chat/completions/completions.py`, `openai/types/shared/reasoning_effort.py`, `openai/_exceptions.py`
- LangGraph docs: https://docs.langchain.com/oss/python/langgraph/graph-api , .../interrupts , .../streaming , .../persistence ; wheels langgraph 1.2.17, langgraph-checkpoint 4.3.0, langgraph-checkpoint-sqlite 3.1.2 (`langgraph/types.py`, `langgraph/pregel/main.py`, `langgraph/graph/state.py`, `langgraph/checkpoint/sqlite/{__init__,aio}.py`)
- FastAPI SSE: https://fastapi.tiangolo.com/tutorial/server-sent-events/ ; fastapi 0.162.0 wheel (`fastapi/sse.py`, `fastapi/routing.py`); sse-starlette 3.5.1 wheel; uvicorn 0.54.0 wheel (`uvicorn/main.py`, `uvicorn/loops/asyncio.py`)
- OR-Tools: https://developers.google.com/optimization/cp/cp_solver ; https://raw.githubusercontent.com/google/or-tools/stable/ortools/sat/sat_parameters.proto ; https://raw.githubusercontent.com/google/or-tools/stable/ortools/sat/python/cp_model.py ; PyPI JSON https://pypi.org/pypi/ortools/json
- PyTorch: https://pytorch.org/get-started/locally/ ; https://download.pytorch.org/whl/cpu/torch/ ; PyPI JSON https://pypi.org/pypi/torch/json
- PyG: https://pytorch-geometric.readthedocs.io/en/latest/install/installation.html ; torch_geometric 2.8.1 wheel
- Next.js: https://nextjs.org/docs/app/api-reference/cli/create-next-app ; https://nextjs.org/docs/app/guides/lazy-loading ; https://nextjs.org/docs/app/api-reference/config/next-config-js/cacheComponents ; https://cdn.jsdelivr.net/npm/next@16.4.3/dist/compiled/@next/font/dist/google/index.d.ts ; https://unpkg.com/next@16.4.3/dist/compiled/@next/font/dist/google/font-data.json ; create-next-app 16.4.3 tarball
- shadcn: https://ui.shadcn.com/docs/installation/next ; https://ui.shadcn.com/docs/cli ; shadcn 4.22.1 tarball (`dist/index.js`)
- Motion: https://motion.dev/docs/react-installation ; `npm view motion@14.6.0 exports peerDependencies` ; https://cdn.jsdelivr.net/npm/motion@14.6.0/dist/react.d.ts
- react-force-graph: https://raw.githubusercontent.com/vasturiano/react-force-graph/master/README.md ; `npm view react-force-graph-2d@1.29.2`
