"""Career Sim: one 07:00-17:00 workday as a LangGraph StateGraph (brief 5.1, CONTRACTS section 6).

Flow::

    START -> select_event -> present_and_wait --Send x3--> coworker (parallel) -> score_choice
          -> update_state --(stress >= 75 and no crunch yet)--> inject_crunch -> present_and_wait
                          --(fewer than 5 events today)-------> select_event
                          --(otherwise)-----------------------> report -> verify -> summarize -> END

* ``select_event``: adaptive runs ask :mod:`foothold.selector` for the remaining event with
  the highest expected information gain about the career posterior; chosen-career runs play
  that career's events (plus shared ones) in clock order and still report the gain.
* ``present_and_wait``: ``interrupt()`` with the event payload (choices without their hidden
  deltas). Resume with ``Command(resume=choice_id)``.
* ``coworker``: one Send task per coworker (3), each with that coworker's hidden mood and style,
  returning a structured ``{reaction, mood_delta, line}`` via ``llm.astructured``. The mock uses
  the event's ``coworker_hints`` plus mood rules.
* ``score_choice``: the LLM tags the chosen option with trait deltas (structured, validated
  against traits.json); blended 0.7 x precomputed + 0.3 x LLM (mock = precomputed).
* ``update_state``: clamps stats, updates moods, posterior and trait estimate via the selector.
* ``report``: career_fit top-3 (+ model / trained flag), local wage and outlook from careers.json
  with provenance, matching programs; ``verify`` checks every factual claim with
  :mod:`foothold.verifier`; ``summarize`` writes prose whose numbers come only from verified
  claims (the LLM writes placeholders, never digits).

When ``foothold.selector`` / ``foothold.career_fit`` are not importable yet the run still works:
events are taken in clock order (gain reported as unavailable), the trait estimate is a labeled
running sum of choice deltas, and the report says the career-fit model is not available yet.
No number is invented to fill the gap.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import logging
import math
import operator
import re
from datetime import datetime, timezone
from typing import Annotated, Any, Callable, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt
from pydantic import BaseModel

from .. import data, llm, verifier
from ..sse import trace_node
from ..trace import note

log = logging.getLogger("foothold.sim")

GRAPH_NAME = "sim"
STAT_IDS: tuple[str, ...] = ("safety", "output", "team_trust", "stress")
START_STATS: dict[str, int] = {"safety": 70, "output": 50, "team_trust": 50, "stress": 20}
EVENTS_PER_DAY = 5
CRUNCH_STRESS = 75
DAY_START = "07:00"
DAY_END = "17:00"
LAST_SLOT = "16:45"
BLEND_PRE = 0.7
BLEND_LLM = 0.3
MOOD_BASE = {"upbeat": 72, "calm": 64, "steady": 60, "tired": 46, "skeptical": 44, "tense": 36}

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class SimState(TypedDict, total=False):
    learner_id: str
    career_id: str | None
    mode: str  # "career" | "adaptive"
    started_at: str
    clock: str
    stats: dict[str, int]
    moods: dict[str, int]  # coworker_id -> 0..100 (hidden from the player as a number until reacted)
    trait_estimate: dict[str, float]
    trait_method: str
    posterior: dict[str, float] | None
    selector_state: dict[str, Any]
    history: Annotated[list[dict[str, Any]], operator.add]
    played: Annotated[list[str], operator.add]
    reactions: Annotated[list[dict[str, Any]], operator.add]
    current_event: dict[str, Any] | None
    selection: dict[str, Any] | None
    last_choice: dict[str, Any] | None
    scored: dict[str, Any] | None
    crunch_used: bool
    report: dict[str, Any] | None
    verification: dict[str, Any] | None
    summary: dict[str, Any] | None


class CoworkerTask(TypedDict, total=False):
    coworker: dict[str, Any]
    mood: int
    event: dict[str, Any]
    choice: dict[str, Any]
    hint: str | None
    _trace_id: str


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _to_min(clock: str) -> int:
    try:
        h, m = clock.split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 7 * 60


def _to_clock(minutes: int) -> str:
    minutes = max(0, min(minutes, 23 * 60 + 59))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _stable_pick(options: list[str], *parts: str) -> str:
    h = int(hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:8], 16)
    return options[h % len(options)]


def mood_label(m: int) -> str:
    if m >= 85:
        return "energized"
    if m >= 70:
        return "good"
    if m >= 55:
        return "steady"
    if m >= 40:
        return "guarded"
    if m >= 25:
        return "tense"
    return "frustrated"


def traits_meta() -> list[dict[str, Any]]:
    return [t for t in data.traits() if isinstance(t, dict) and t.get("id")]


def trait_ids() -> list[str]:
    return data.traits_order()


def valid_event(ev: Any) -> bool:
    if not isinstance(ev, dict) or not ev.get("event_id") or not ev.get("text"):
        return False
    choices = ev.get("choices")
    return isinstance(choices, list) and len(choices) >= 2 and all(
        isinstance(c, dict) and c.get("choice_id") and c.get("text") for c in choices
    )


def all_events() -> list[dict[str, Any]]:
    return [e for e in data.events_list() if valid_event(e)]


def events_available() -> bool:
    return any(not e.get("crunch") for e in all_events())


def coworkers_for(career_id: str | None) -> list[dict[str, Any]]:
    career = data.get_career(career_id) if career_id else None
    cws = (career or {}).get("coworkers") or []
    return [c for c in cws if isinstance(c, dict) and c.get("id")][:3]


def all_coworkers() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for c in data.careers():
        for cw in (c or {}).get("coworkers") or []:
            if isinstance(cw, dict) and cw.get("id"):
                out[cw["id"]] = {**cw, "career_id": c.get("id")}
    return out


def initial_mood(cw: dict[str, Any]) -> int:
    base = cw.get("base_mood")
    if isinstance(base, (int, float)):
        return int(_clamp(base, 0, 100))
    return MOOD_BASE.get(str(base or "").lower(), 55)


def public_choice(c: dict[str, Any]) -> dict[str, Any]:
    return {"choice_id": c["choice_id"], "text": c["text"]}


def public_coworker(cw: dict[str, Any], mood: int) -> dict[str, Any]:
    return {
        "id": cw["id"], "name": cw.get("name"), "role": cw.get("role"), "style": cw.get("style"),
        "pronouns": cw.get("pronouns"), "base_mood": cw.get("base_mood"), "mood": mood, "mood_label": mood_label(mood),
        "fictional": True,
    }


def leading_career(state: SimState) -> str | None:
    post = state.get("posterior") or {}
    if post:
        return max(post.items(), key=lambda kv: kv[1])[0]
    hist = state.get("history") or []
    return hist[-1].get("workplace") if hist else None


def workplace_for(ev: dict[str, Any], state: SimState) -> str | None:
    cid = state.get("career_id")
    ids = [c for c in (ev.get("career_ids") or []) if isinstance(c, str)]
    if cid and (cid in ids or not ids):
        return cid
    if ids:
        return ids[0]
    return leading_career(state) or (data.career_ids() or [None])[0]


# ---------------------------------------------------------------------------
# Selector / career-fit adapters (foothold.selector, foothold.career_fit are built by the ML slice)
# ---------------------------------------------------------------------------


def _module(name: str) -> Any | None:
    try:
        return importlib.import_module(name)
    except Exception as exc:  # missing or failing module -> graceful fallback
        log.debug("%s unavailable (%s)", name, type(exc).__name__)
        return None


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "tolist"):
        return obj.tolist()
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


class SelectorAdapter:
    """Uniform view over foothold.selector (or the labeled fallback when it is missing)."""

    FALLBACK_METHOD = "running sum of choice trait deltas (selector not available yet)"

    def __init__(self) -> None:
        self.mod = _module("foothold.selector")

    @property
    def available(self) -> bool:
        return self.mod is not None and all(
            hasattr(self.mod, fn) for fn in ("initial_state", "expected_information_gain", "update", "summarize")
        )

    # -- state ---------------------------------------------------------------
    def initial(self, career_ids: list[str]) -> dict[str, Any]:
        if self.available:
            return _jsonable(self.mod.initial_state(career_ids=career_ids))
        return {"fallback": True, "sums": {t: 0.0 for t in trait_ids()}, "n": 0}

    def summary(self, sel: dict[str, Any]) -> tuple[dict[str, float], dict[str, float] | None, str]:
        """(trait_estimate 0..1, posterior or None, method)."""
        if self.available and not sel.get("fallback"):
            s = self.mod.summarize(sel)
            traits = {k: float(v) for k, v in (s.get("trait_estimate") or {}).items()}
            post = {k: float(v) for k, v in (s.get("posterior") or {}).items()} or None
            return traits, post, str(s.get("method") or "Bayesian player model (foothold.selector)")
        sums = sel.get("sums") or {}
        traits = {t: round(0.5 + 0.5 * math.tanh(float(sums.get(t, 0.0)) / 2.0), 4) for t in trait_ids()}
        return traits, None, self.FALLBACK_METHOD

    def gain(self, sel: dict[str, Any], event: dict[str, Any]) -> float | None:
        if self.available and not sel.get("fallback"):
            try:
                return float(self.mod.expected_information_gain(sel, event))
            except Exception as exc:
                log.warning("selector gain failed (%s)", type(exc).__name__)
        return None

    def pick(self, sel: dict[str, Any], candidates: list[dict[str, Any]], *, ordered: bool) -> tuple[dict[str, Any], float | None, str]:
        """Chosen-career runs (``ordered``) take candidates in clock order; adaptive runs maximize gain."""
        if ordered or not candidates:
            ev = candidates[0]
            return ev, self.gain(sel, ev), "clock order (chosen career)"
        if self.available and not sel.get("fallback"):
            scored = [(self.gain(sel, ev), ev) for ev in candidates]
            scored = [(g, ev) for g, ev in scored if g is not None]
            if scored:
                g, ev = max(scored, key=lambda t: (t[0], -_to_min(t[1].get("clock", "07:00"))))
                return ev, g, "max expected information gain"
        return candidates[0], None, "clock order (selector not available yet)"

    def update(self, sel: dict[str, Any], event: dict[str, Any], choice_id: str, deltas: dict[str, float]) -> dict[str, Any]:
        if self.available and not sel.get("fallback"):
            return _jsonable(self.mod.update(sel, event, choice_id, trait_deltas=deltas))
        sums = dict(sel.get("sums") or {})
        for t, d in deltas.items():
            sums[t] = float(sums.get(t, 0.0)) + float(d)
        return {"fallback": True, "sums": sums, "n": int(sel.get("n", 0)) + 1}


class CareerFitAdapter:
    def __init__(self) -> None:
        self.mod = _module("foothold.career_fit")

    def predict(self, traits: dict[str, float]) -> dict[str, Any] | None:
        """``{top: [{career_id, probability}], model, trained}`` or None when the model is missing."""
        if self.mod is None or not hasattr(self.mod, "predict"):
            return None
        try:
            out = self.mod.predict(traits, k=3)
        except TypeError:
            out = self.mod.predict(traits)
        except Exception as exc:
            log.warning("career_fit.predict failed (%s)", type(exc).__name__)
            return None
        return _jsonable(out) if isinstance(out, dict) else None


def selector() -> SelectorAdapter:
    return SelectorAdapter()


def career_fit() -> CareerFitAdapter:
    return CareerFitAdapter()


# ---------------------------------------------------------------------------
# LLM schemas + mocks
# ---------------------------------------------------------------------------

Reaction = Literal["approves", "relieved", "neutral", "uneasy", "frustrated"]


class CoworkerReaction(BaseModel):
    reaction: Reaction
    mood_delta: int
    line: str


def _trait_literal() -> Any:
    ids = tuple(trait_ids())
    return Literal[ids] if ids else str  # type: ignore[valid-type]


class TraitDelta(BaseModel):
    trait_id: str
    delta: float


class TraitTagging(BaseModel):
    deltas: list[TraitDelta]
    rationale: str


def _tagging_schema() -> type[BaseModel]:
    """TraitTagging with trait_id constrained to the traits.json ids (enum in strict mode)."""
    lit = _trait_literal()

    class TraitDeltaStrict(BaseModel):
        trait_id: lit  # type: ignore[valid-type]
        delta: float

    class TraitTaggingStrict(BaseModel):
        deltas: list[TraitDeltaStrict]
        rationale: str

    TraitTaggingStrict.__name__ = "TraitTagging"
    return TraitTaggingStrict


class ReportSummary(BaseModel):
    paragraph: str


_POS = ("appreciat", "relieved", "respect", "trust", "grateful", "impressed", "approv", "glad", "happy", "proud",
        "likes", "values", "thank", "pleased", "good call", "reassur", "confident", "admire", "calm")
_NEG = ("annoy", "frustrat", "worr", "angry", "upset", "rushed", "disappoint", "irritat", "concern", "uneas", "resent",
        "hate", "nervous", "tense", "skeptic", "dislike", "bother", "doubt", "blindsid", "undercut", "left out", "stress")
_STRONG_NEG = ("angry", "frustrat", "resent", "furious", "hate", "blindsid")

LINES: dict[str, list[str]] = {
    "approves": ["Good call. That's the right way to do it.", "Thanks for handling that. I noticed.",
                 "That's what I'd have done.", "Okay, that actually helps me out."],
    "relieved": ["Whew. Glad someone caught that.", "Thank you. That takes a weight off.", "Okay, now we can breathe."],
    "neutral": ["Alright. Let's see how it plays out.", "Fine by me. Keep it moving.", "Noted."],
    "uneasy": ["Hm. I'm not sure about that.", "If this comes back on us, we talk.", "I'd have done it differently."],
    "frustrated": ["That makes my afternoon a lot harder.", "You could have asked me first.",
                   "That's going to cost us later."],
}


def mock_reaction(task: CoworkerTask) -> CoworkerReaction:
    """Deterministic reaction from the event's coworker_hints + mood rules (no LLM)."""
    cw = task.get("coworker") or {}
    hint = (task.get("hint") or "").lower()
    choice = task.get("choice") or {}
    stat = choice.get("stat_deltas") or {}
    trust = int(stat.get("team_trust", 0) or 0)
    score = sum(w in hint for w in _POS) - sum(w in hint for w in _NEG)
    if score > 0:
        reaction: str = "relieved" if "relieved" in hint else "approves"
        delta = 6 + max(min(trust // 3, 3), 0)
    elif score < 0:
        reaction = "frustrated" if any(w in hint for w in _STRONG_NEG) else "uneasy"
        delta = -6 + min(max(trust // 3, -3), 0)
    else:
        reaction = "neutral"
        delta = (trust > 0) - (trust < 0)
    style = str(cw.get("style") or "").lower()
    if "safety" in style and int(stat.get("safety", 0) or 0) < 0:
        delta -= 3
        if reaction in ("approves", "neutral"):
            reaction = "uneasy"
    mood = int(task.get("mood", 55))
    if mood < 40 and delta > 0:
        delta = max(delta - 2, 1)  # a tense coworker warms up slowly
    delta = int(_clamp(delta, -15, 15))
    ev = task.get("event") or {}
    line = _stable_pick(LINES[reaction], str(ev.get("event_id")), str(choice.get("choice_id")), str(cw.get("id")))
    return CoworkerReaction(reaction=reaction, mood_delta=delta, line=line)  # type: ignore[arg-type]


def precomputed_deltas(choice: dict[str, Any]) -> dict[str, float]:
    valid = set(trait_ids())
    out: dict[str, float] = {}
    for t, d in (choice.get("trait_deltas") or {}).items():
        if t in valid and isinstance(d, (int, float)):
            out[t] = float(_clamp(float(d), -1.0, 1.0))
    return out


def validate_tagging(obj: Any) -> dict[str, float]:
    """Keep known trait ids, clamp to [-1, 1], at most 4 (largest magnitude)."""
    valid = set(trait_ids())
    out: dict[str, float] = {}
    for item in getattr(obj, "deltas", None) or []:
        tid = getattr(item, "trait_id", None)
        d = getattr(item, "delta", None)
        if tid in valid and isinstance(d, (int, float)) and math.isfinite(float(d)):
            out[str(tid)] = float(_clamp(float(d), -1.0, 1.0))
    top = sorted(out.items(), key=lambda kv: -abs(kv[1]))[:4]
    return dict(top)


def blend(pre: dict[str, float], tagged: dict[str, float]) -> dict[str, float]:
    keys = set(pre) | set(tagged)
    return {k: round(BLEND_PRE * pre.get(k, 0.0) + BLEND_LLM * tagged.get(k, 0.0), 4) for k in sorted(keys)}


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def _candidates(state: SimState) -> list[dict[str, Any]]:
    played = set(state.get("played") or [])
    cid = state.get("career_id")
    evs = [e for e in all_events() if not e.get("crunch") and e["event_id"] not in played]
    if cid:
        evs = [e for e in evs if cid in (e.get("career_ids") or [])]
    return sorted(evs, key=lambda e: (_to_min(str(e.get("clock", DAY_START))), e["event_id"]))


def _display_clock(state: SimState, ev: dict[str, Any], *, crunch: bool = False) -> str:
    prev = _to_min(state.get("clock") or DAY_START)
    first = not (state.get("history") or [])
    own = _to_min(str(ev.get("clock") or DAY_START))
    if crunch:
        t = prev + 20
    elif first:
        t = max(own, _to_min(DAY_START))
    else:
        t = max(own, prev + 25)
    return _to_clock(min(t, _to_min(LAST_SLOT)))


def _event_view(ev: dict[str, Any], state: SimState, clock: str) -> dict[str, Any]:
    return {**ev, "_workplace": workplace_for(ev, state), "_clock": clock}


def select_event(state: SimState) -> dict[str, Any]:
    cands = _candidates(state)
    if not cands:
        note(summary="no events left · ending the day")
        return {"current_event": None, "selection": None}
    sel = state.get("selector_state") or {}
    ev, gain, method = selector().pick(sel, cands, ordered=bool(state.get("career_id")))
    clock = _display_clock(state, ev)
    selection = {"event_id": ev["event_id"], "gain_bits": None if gain is None else round(gain, 3), "method": method,
                 "candidates": len(cands)}
    gtxt = f"gain {gain:.2f} bits" if gain is not None else "gain n/a"
    note(summary=f"picked event {ev['event_id']} · {gtxt}")
    return {"current_event": _event_view(ev, state, clock), "selection": selection, "clock": clock}


def inject_crunch(state: SimState) -> dict[str, Any]:
    played = set(state.get("played") or [])
    work = state.get("career_id") or leading_career(state)
    crunch = [e for e in all_events() if e.get("crunch") and e["event_id"] not in played]
    fitting = [e for e in crunch if not e.get("career_ids") or (work and work in e.get("career_ids"))]
    pool = sorted(fitting or crunch, key=lambda e: (_to_min(str(e.get("clock", DAY_START))), e["event_id"]))
    if not pool:
        note(summary="stress high · no crunch event available")
        return {"crunch_used": True, "current_event": None}
    ev = pool[0]
    clock = _display_clock(state, ev, crunch=True)
    note(summary=f"stress {state.get('stats', {}).get('stress')} ≥ {CRUNCH_STRESS} · crunch {ev['event_id']}")
    selection = {"event_id": ev["event_id"], "gain_bits": None, "method": f"crunch (stress ≥ {CRUNCH_STRESS})", "candidates": len(pool)}
    return {"current_event": _event_view(ev, state, clock), "selection": selection, "clock": clock, "crunch_used": True}


def interrupt_payload(state: SimState) -> dict[str, Any]:
    ev = state.get("current_event") or {}
    work = ev.get("_workplace")
    moods = state.get("moods") or {}
    cws = coworkers_for(work)
    regular_played = sum(1 for h in (state.get("history") or []) if not h.get("crunch"))
    return {
        "event": {
            "event_id": ev.get("event_id"), "title": ev.get("title"), "text": ev.get("text"), "clock": ev.get("_clock"),
            "crunch": bool(ev.get("crunch")), "status": ev.get("status"), "career_ids": ev.get("career_ids") or [],
            "workplace": work, "choices": [public_choice(c) for c in ev.get("choices") or []],
        },
        "index": regular_played + (0 if ev.get("crunch") else 1),
        "total": EVENTS_PER_DAY,
        "clock": ev.get("_clock"),
        "stats": state.get("stats") or dict(START_STATS),
        "coworkers": [public_coworker(c, int(moods.get(c["id"], initial_mood(c)))) for c in cws],
        "selection": state.get("selection"),
        "mode": state.get("mode"),
        "career_id": state.get("career_id"),
    }


def present_and_wait(state: SimState) -> dict[str, Any]:
    payload = interrupt_payload(state)
    ev = state.get("current_event") or {}
    by_id = {c["choice_id"]: c for c in ev.get("choices") or []}
    answer = interrupt(payload)
    while str(answer) not in by_id:  # route validates first; this guards direct graph use
        answer = interrupt({**payload, "error": "Pick one of the listed choices."})
    choice = by_id[str(answer)]
    note(summary=f"chose {choice['choice_id']} on {ev.get('event_id')}")
    return {"last_choice": {"event_id": ev.get("event_id"), **choice}}


def fan_out(state: SimState) -> list[Send] | str:
    ev = state.get("current_event") or {}
    choice = state.get("last_choice") or {}
    moods = state.get("moods") or {}
    hints = choice.get("coworker_hints") or {}
    sends = []
    for cw in coworkers_for(ev.get("_workplace")):
        sends.append(Send("coworker", {
            "coworker": cw, "mood": int(moods.get(cw["id"], initial_mood(cw))),
            "event": {"event_id": ev.get("event_id"), "title": ev.get("title"), "text": ev.get("text")},
            "choice": {"choice_id": choice.get("choice_id"), "text": choice.get("text"),
                       "stat_deltas": choice.get("stat_deltas") or {}},
            "hint": hints.get(cw["id"]),
            "_trace_id": f"coworker:{cw['id']}",
        }))
    return sends or "score_choice"


COWORKER_SYSTEM = (
    "You write one short in-character reaction for a FICTIONAL coworker in Foothold, a workplace "
    "simulation that lets people in California's Central Valley try a job for a day. Keep it "
    "workplace-appropriate: no profanity, no slurs, no romance, no medical or legal advice, no real people. "
    "The coworker reacts to the player's choice. Use the 'tendency' note as the main signal, and the "
    "coworker's style and current mood for tone. mood_delta is an integer from -15 to 15 (positive means the "
    "coworker feels better about working with the player). line is one or two sentences, at most 140 "
    "characters, spoken by the coworker, without quotation marks."
)


async def coworker(task: CoworkerTask) -> dict[str, Any]:
    cw = task.get("coworker") or {}
    ev = task.get("event") or {}
    choice = task.get("choice") or {}
    mood = int(task.get("mood", 55))
    user = json.dumps({
        "coworker": {"name": cw.get("name"), "role": cw.get("role"), "style": cw.get("style"), "mood": mood_label(mood)},
        "scene": {"title": ev.get("title"), "text": ev.get("text")},
        "player_choice": choice.get("text"),
        "tendency": task.get("hint") or "no strong opinion either way",
    }, ensure_ascii=False, sort_keys=True)
    obj, meta = await llm.astructured(f"sim_coworker", COWORKER_SYSTEM, user, CoworkerReaction, mock=lambda: mock_reaction(task))
    delta = int(_clamp(int(obj.mood_delta), -15, 15))
    line = " ".join(str(obj.line).replace('"', "").split())[:160] or _stable_pick(LINES[obj.reaction], cw.get("id", ""))
    name = str(cw.get("name") or cw.get("id") or "coworker").split()[0]
    note(summary=f"{name}: {obj.reaction} ({delta:+d})")
    return {"reactions": [{
        "event_id": ev.get("event_id"), "coworker_id": cw.get("id"), "name": cw.get("name"),
        "reaction": obj.reaction, "mood_delta": delta, "line": line, "llm": meta["source"],
    }]}


SCORE_SYSTEM = (
    "You tag which O*NET work styles a choice in a workplace scenario expresses. Return 2 to 4 traits "
    "from the provided list (use the ids exactly) with a signed strength from -1 to 1: positive means the "
    "choice shows more of that work style, negative means less. Judge only the choice in its scenario. "
    "rationale: one short sentence."
)


async def score_choice(state: SimState) -> dict[str, Any]:
    ev = state.get("current_event") or {}
    choice = state.get("last_choice") or {}
    pre = precomputed_deltas(choice)
    schema = _tagging_schema()
    user = json.dumps({
        "traits": [{"id": t["id"], "name": t.get("name")} for t in traits_meta()],
        "scenario": {"title": ev.get("title"), "text": ev.get("text")},
        "choice": choice.get("text"),
    }, ensure_ascii=False, sort_keys=True)

    def mock() -> Any:
        return {"deltas": [{"trait_id": k, "delta": v} for k, v in pre.items()], "rationale": "precomputed deltas"}

    obj, meta = await llm.astructured("sim_score_choice", SCORE_SYSTEM, user, schema, mock=mock)
    tagged = validate_tagging(obj) if meta["source"] != "mock" else dict(pre)
    blended = blend(pre, tagged)
    top = sorted(blended.items(), key=lambda kv: -abs(kv[1]))[:2]
    note(summary=", ".join(f"{k.replace('_', ' ')} {v:+.2f}" for k, v in top) or "no trait signal")
    return {"scored": {"event_id": ev.get("event_id"), "choice_id": choice.get("choice_id"), "precomputed": pre,
                       "llm": tagged, "blended": blended, "source": meta["source"],
                       "weights": {"precomputed": BLEND_PRE, "llm": BLEND_LLM}}}


def update_state(state: SimState) -> dict[str, Any]:
    ev = state.get("current_event") or {}
    choice = state.get("last_choice") or {}
    scored = state.get("scored") or {}
    stats = dict(state.get("stats") or START_STATS)
    deltas = {k: int(v) for k, v in (choice.get("stat_deltas") or {}).items() if k in STAT_IDS and isinstance(v, (int, float))}
    for k in STAT_IDS:
        stats[k] = int(_clamp(stats.get(k, START_STATS[k]) + deltas.get(k, 0), 0, 100))

    moods = dict(state.get("moods") or {})
    reacts = [r for r in (state.get("reactions") or []) if r.get("event_id") == ev.get("event_id")]
    cws = {c["id"]: c for c in coworkers_for(ev.get("_workplace"))}
    for r in reacts:
        cid = r.get("coworker_id")
        if cid:
            base = moods.get(cid, initial_mood(cws.get(cid, {})))
            moods[cid] = int(_clamp(base + int(r.get("mood_delta", 0)), 0, 100))

    sel_adapter = selector()
    sel = sel_adapter.update(state.get("selector_state") or {}, ev, str(choice.get("choice_id")), scored.get("blended") or {})
    traits, post, method = sel_adapter.summary(sel)

    entry = {
        "event_id": ev.get("event_id"), "title": ev.get("title"), "clock": ev.get("_clock"), "crunch": bool(ev.get("crunch")),
        "workplace": ev.get("_workplace"), "choice_id": choice.get("choice_id"), "choice_text": choice.get("text"),
        "stat_deltas": deltas, "trait_deltas": scored.get("blended") or {},
        "reactions": [{k: r.get(k) for k in ("coworker_id", "name", "reaction", "mood_delta", "line")} for r in reacts],
        "gain_bits": (state.get("selection") or {}).get("gain_bits"),
    }
    lead = max(post.items(), key=lambda kv: kv[1]) if post else None
    note(summary=f"stress {stats['stress']} · trust {stats['team_trust']}" + (f" · lead {lead[0]} {lead[1]:.2f}" if lead else ""))
    return {
        "stats": stats, "moods": moods, "selector_state": sel, "trait_estimate": traits, "posterior": post,
        "trait_method": method, "history": [entry], "played": [ev.get("event_id")],
    }


def route_after_update(state: SimState) -> str:
    stats = state.get("stats") or {}
    if stats.get("stress", 0) >= CRUNCH_STRESS and not state.get("crunch_used"):
        if any(e.get("crunch") and e["event_id"] not in set(state.get("played") or []) for e in all_events()):
            return "inject_crunch"
    regular = sum(1 for h in (state.get("history") or []) if not h.get("crunch"))
    if regular < EVENTS_PER_DAY and _candidates(state):
        return "select_event"
    return "report"


def route_after_select(state: SimState) -> str:
    return "present_and_wait" if state.get("current_event") else "report"


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _source(source_id: str | None) -> dict[str, Any] | None:
    if not source_id:
        return None
    s = data.get_source(source_id)
    if not s:
        return {"id": source_id}
    return {k: s.get(k) for k in ("id", "title", "url", "publisher", "retrieved", "status")}


def _prov(status: Any) -> str:
    s = str(status or "").split()[0].upper() if status else ""
    if s in ("REAL", "SAMPLE", "SYNTHETIC", "FICTIONAL"):
        return s
    if s == "DERIVED":
        return "REAL"
    return "SAMPLE"


def _career_facts(cid: str) -> dict[str, Any]:
    c = data.get_career(cid) or {}
    wage = c.get("wage") if isinstance(c.get("wage"), dict) else None
    outlook = c.get("outlook") if isinstance(c.get("outlook"), dict) else None
    progs = []
    seen_routes: set[str] = set()
    for p in data.programs_for(cid):
        if not isinstance(p, dict):
            continue
        rt = str(p.get("route_type") or "")
        if rt in seen_routes and len(progs) >= 2:
            continue
        seen_routes.add(rt)
        cost = verifier.program_total_cost(p)
        weeks = verifier.program_duration_weeks(p)
        progs.append({
            "id": p.get("id"), "name": p.get("name"), "provider": p.get("provider"), "credential": p.get("credential"),
            "route_type": rt, "url": p.get("url"), "status": _prov(p.get("status")), "source": _source(p.get("source_id")),
            "total_cost_usd": cost, "duration_weeks": None if weeks is None else round(weeks, 1),
        })
        if len(progs) >= 3:
            break
    return {
        "career_id": cid, "title": c.get("title"), "onet_soc": c.get("onet_soc"), "onet_title": c.get("onet_title"),
        "onet_url": c.get("onet_url"), "summary": c.get("summary"), "path_types": c.get("path_types") or [],
        "wage": None if wage is None else {**wage, "status": _prov(wage.get("status")), "source": _source(wage.get("source_id"))},
        "outlook": None if outlook is None else {**outlook, "status": _prov(outlook.get("status")), "source": _source(outlook.get("source_id"))},
        "programs": progs,
    }


def _claims_for(facts: dict[str, Any]) -> list[dict[str, Any]]:
    cid = facts["career_id"]
    out: list[dict[str, Any]] = []
    w = facts.get("wage") or {}
    for field, unit in (("median_annual", "usd_per_year"), ("median_hourly", "usd_per_hour"),
                        ("p25_annual", "usd_per_year"), ("p75_annual", "usd_per_year")):
        if isinstance(w.get(field), (int, float)):
            out.append({"key": f"{cid}.wage.{field}", "kind": "wage", "value": w[field], "unit": unit, "entity_id": cid,
                        "source_id": w.get("source_id"), "field": field})
    o = facts.get("outlook") or {}
    for field, unit in (("growth_pct", "percent"), ("annual_openings", "openings_per_year")):
        if isinstance(o.get(field), (int, float)):
            out.append({"key": f"{cid}.outlook.{field}", "kind": "outlook", "value": o[field], "unit": unit, "entity_id": cid,
                        "source_id": o.get("source_id"), "field": field})
    for p in facts.get("programs") or []:
        src = (p.get("source") or {}).get("id")
        if isinstance(p.get("total_cost_usd"), (int, float)):
            out.append({"key": f"{cid}.program.{p['id']}.cost", "kind": "cost", "value": p["total_cost_usd"], "unit": "usd",
                        "entity_id": p["id"], "source_id": src, "field": None})
        if isinstance(p.get("duration_weeks"), (int, float)):
            out.append({"key": f"{cid}.program.{p['id']}.weeks", "kind": "duration", "value": p["duration_weeks"], "unit": "weeks",
                        "entity_id": p["id"], "source_id": src, "field": None})
    return out


def _metrics_block() -> dict[str, Any] | None:
    m = data.metrics().get("career_fit")
    return m if isinstance(m, dict) else None


PROB_BASIS_CAREERS = "share among the 8 Foothold careers (career-fit model output renormalized over these 8)"
PROB_BASIS_OVERALL = "share among all O*NET occupations the career-fit model scores (not renormalized)"


def cosine_top3(traits: dict[str, float]) -> list[dict[str, Any]]:
    """Untrained baseline: cosine between centred trait estimate and centred career work styles."""
    ids = trait_ids()
    u = [float(traits.get(t, 0.5)) - 0.5 for t in ids]
    rows = []
    for c in data.careers():
        ws = (c or {}).get("work_styles") or {}
        if not ws:
            continue
        mean = sum(float(ws.get(t, 0.5)) for t in ids) / max(1, len(ids))
        v = [float(ws.get(t, mean)) - mean for t in ids]
        nu = math.sqrt(sum(x * x for x in u)) or 1e-9
        nv = math.sqrt(sum(x * x for x in v)) or 1e-9
        rows.append((sum(a * b for a, b in zip(u, v)) / (nu * nv), c["id"]))
    if not rows:
        return []
    exps = [math.exp(4.0 * s) for s, _ in rows]
    tot = sum(exps)
    ranked = sorted(zip(rows, exps), key=lambda r: -r[0][0])[:3]
    return [{"rank": i + 1, "career_id": cid, "title": (data.get_career(cid) or {}).get("title"),
             "probability": round(e / tot, 4), "similarity": round(s, 4)} for i, ((s, cid), e) in enumerate(ranked)]


async def report(state: SimState) -> dict[str, Any]:
    traits = dict(state.get("trait_estimate") or {})
    if not traits:
        traits, _, _ = selector().summary(state.get("selector_state") or {})
    fit = await asyncio.to_thread(career_fit().predict, traits)
    model: dict[str, Any]
    top: list[dict[str, Any]] = []
    basis: str
    p_overall_basis: str | None = None
    if fit and fit.get("top"):
        is_mlp = fit.get("model") == "mlp"
        basis = (PROB_BASIS_CAREERS if is_mlp
                 else "ranking score (softmax of cosine similarity), not a calibrated probability")
        p_overall_basis = PROB_BASIS_OVERALL if is_mlp else None
        for i, row in enumerate(fit["top"][:3]):
            cid = row.get("career_id")
            if cid in data.career_ids():
                po = row.get("p_overall")
                top.append({"rank": i + 1, "career_id": cid, "title": (data.get_career(cid) or {}).get("title"),
                            "probability": round(float(row.get("probability", 0.0)), 4),
                            "p_overall": round(float(po), 4) if isinstance(po, (int, float)) else None,
                            "probability_basis": basis})
        model = {"source": "career_fit", "name": fit.get("model"), "trained": bool(fit.get("trained")),
                 "note": fit.get("note"), "metrics": _metrics_block()}
    elif state.get("posterior"):
        basis = "selector posterior over the 8 Foothold careers"
        post = state["posterior"] or {}
        ranked = sorted(post.items(), key=lambda kv: -kv[1])[:3]
        top = [{"rank": i + 1, "career_id": cid, "title": (data.get_career(cid) or {}).get("title"), "probability": round(p, 4),
                "p_overall": None, "probability_basis": basis}
               for i, (cid, p) in enumerate(ranked)]
        model = {"source": "selector_posterior", "name": "Bayesian player model", "trained": False,
                 "note": "career-fit model not available yet; showing the selector's posterior", "metrics": None}
    else:
        basis = "ranking score (softmax of cosine similarity), not a calibrated probability"
        top = [{**t, "p_overall": None, "probability_basis": basis} for t in cosine_top3(traits)]
        model = {"source": "cosine_fallback", "name": "cosine similarity to O*NET work styles", "trained": False,
                 "note": "career-fit model not available yet; ranked by cosine similarity between your trait estimate "
                         "and each career's O*NET work-style profile", "metrics": None}
    sel_post = state.get("posterior") or {}
    selector_posterior = None
    if sel_post:
        ranked_post = sorted(sel_post.items(), key=lambda kv: -float(kv[1]))
        selector_posterior = {
            "basis": "Bayesian selector posterior over the 8 Foothold careers, from your choices in this run",
            "top": [{"rank": i + 1, "career_id": cid, "title": (data.get_career(cid) or {}).get("title"),
                     "probability": round(float(p), 4)} for i, (cid, p) in enumerate(ranked_post[:3])],
            "posterior": {cid: round(float(p), 4) for cid, p in ranked_post},
        }

    focus = [t["career_id"] for t in top]
    if state.get("career_id") and state["career_id"] not in focus:
        focus.append(state["career_id"])
    facts = {cid: _career_facts(cid) for cid in focus if cid}
    tmeta = traits_meta()
    rep = {
        "mode": state.get("mode"), "career_id": state.get("career_id"), "stats": state.get("stats") or dict(START_STATS),
        "traits": [{"id": t["id"], "name": t.get("name"), "group": t.get("group"), "value": round(float(traits.get(t["id"], 0.5)), 4)}
                   for t in tmeta],
        "trait_method": state.get("trait_method") or SelectorAdapter.FALLBACK_METHOD,
        "top_careers": top, "model": model, "careers": facts,
        "probability_basis": basis, "p_overall_basis": p_overall_basis, "selector_posterior": selector_posterior,
        "history": state.get("history") or [], "events_played": len(state.get("history") or []),
        "crunch_used": bool(state.get("crunch_used")), "moods": state.get("moods") or {},
    }
    label = f"top-3 via {model['name']}" if model.get("name") else "career-fit model not available yet"
    if model.get("source") == "career_fit":
        label += " (trained)" if model.get("trained") else " (untrained baseline)"
    note(summary=label)
    return {"report": rep}


def verify(state: SimState) -> dict[str, Any]:
    rep = dict(state.get("report") or {})
    claims = [c for f in (rep.get("careers") or {}).values() for c in _claims_for(f)]
    keyed = {c["key"]: c for c in claims}
    results = {c["key"]: verifier.verify_claim({k: v for k, v in c.items() if k != "key"}) for c in claims}
    status_by_key = {k: r.status for k, r in results.items()}
    ok_keys = {k for k, s in status_by_key.items() if s == "verified"}
    counts = {"checked": len(results), "verified": len(ok_keys),
              "dropped": sum(1 for s in status_by_key.values() if s == "mismatch"),
              "flagged": sum(1 for s in status_by_key.values() if s == "unverifiable")}
    # strip anything that did not verify from the displayed facts
    careers = {}
    for cid, f in (rep.get("careers") or {}).items():
        f = json.loads(json.dumps(f))
        for block, fields in (("wage", ("median_annual", "median_hourly", "p25_annual", "p75_annual")),
                              ("outlook", ("growth_pct", "annual_openings"))):
            b = f.get(block)
            if isinstance(b, dict):
                b["verified"] = {}
                for fld in fields:
                    key = f"{cid}.{block}.{fld}"
                    if key in keyed:
                        b["verified"][fld] = key in ok_keys
                        if key not in ok_keys:
                            b[fld] = None
        for p in f.get("programs") or []:
            for fld, suffix in (("total_cost_usd", "cost"), ("duration_weeks", "weeks")):
                key = f"{cid}.program.{p['id']}.{suffix}"
                if key in keyed and key not in ok_keys:
                    p[fld] = None
        careers[cid] = f
    rep["careers"] = careers
    verification = {
        "counts": counts,
        "dropped": [{"key": k, "reason": r.reason} for k, r in results.items() if r.status == "mismatch"][:20],
        "flagged": [{"key": k, "reason": r.reason} for k, r in results.items() if r.status == "unverifiable"][:20],
        "verified_keys": sorted(ok_keys),
        "tolerances": {u: {"abs": a, "rel": r} for u, (a, r) in verifier.TOLERANCES.items()},
    }
    rep["verification"] = verification
    n = counts
    note(summary=f"{n['checked']} claims: {n['verified']} verified, {n['dropped']} dropped, {n['flagged']} flagged")
    return {"report": rep, "verification": verification}


def _fmt_money(v: float, unit: str) -> str:
    return f"${v:,.2f}" if unit == "usd_per_hour" else f"${v:,.0f}"


def summary_values(rep: dict[str, Any]) -> dict[str, str]:
    """Placeholder -> formatted value, only from verified claims and the run's own state."""
    vals: dict[str, str] = {}
    top = rep.get("top_careers") or []
    for i, t in enumerate(top[:3]):
        vals[f"top{i + 1}_pct"] = f"{round(100 * float(t['probability']))}%"
    verified = set((rep.get("verification") or {}).get("verified_keys") or [])
    if top:
        cid = top[0]["career_id"]
        f = (rep.get("careers") or {}).get(cid) or {}
        w = f.get("wage") or {}
        o = f.get("outlook") or {}
        if f"{cid}.wage.median_annual" in verified and w.get("median_annual") is not None:
            vals["top1_wage_annual"] = _fmt_money(float(w["median_annual"]), "usd_per_year")
        if f"{cid}.wage.median_hourly" in verified and w.get("median_hourly") is not None:
            vals["top1_wage_hourly"] = _fmt_money(float(w["median_hourly"]), "usd_per_hour")
        if f"{cid}.outlook.growth_pct" in verified and o.get("growth_pct") is not None:
            vals["top1_growth"] = f"{float(o['growth_pct']):g}%"
        if f"{cid}.outlook.annual_openings" in verified and o.get("annual_openings") is not None:
            vals["top1_openings"] = f"{int(round(float(o['annual_openings']))):,}"
    stats = rep.get("stats") or {}
    for k in STAT_IDS:
        if isinstance(stats.get(k), (int, float)):
            vals[k] = str(int(stats[k]))
    return vals


PLACEHOLDER_MEANING = {
    "top1_pct": "model probability for the best-fit career", "top2_pct": "probability for the second career",
    "top3_pct": "probability for the third career", "top1_wage_annual": "median annual pay, best-fit career, local area",
    "top1_wage_hourly": "median hourly pay, best-fit career", "top1_growth": "projected 10-year job growth, best-fit career",
    "top1_openings": "average openings per year, best-fit career", "safety": "end-of-day safety score (0-100)",
    "output": "end-of-day output score", "team_trust": "end-of-day team trust score", "stress": "end-of-day stress score",
}

SUMMARY_SYSTEM = (
    "You write the end-of-day debrief for Foothold's workday simulation. 3 or 4 sentences, second person, "
    "warm and concrete, no hype words. NEVER write digits or numbers yourself: whenever you mention a number, "
    "use one of the provided placeholders exactly as written, in curly braces, e.g. {top1_pct}. Only use the "
    "placeholders listed. Do not promise jobs or outcomes. Mention that these are practice signals, not a verdict."
)


def mock_summary(rep: dict[str, Any], vals: dict[str, str]) -> str:
    top = rep.get("top_careers") or []
    parts = []
    hist = rep.get("history") or []
    parts.append(f"You worked through {len(hist)} moments today" + (" including a crunch" if rep.get("crunch_used") else "")
                 + ", ending with safety at {safety}, team trust at {team_trust} and stress at {stress}.")
    if top:
        t1 = top[0].get("title") or top[0]["career_id"]
        s = f"Your choices lined up most with {t1} ({{top1_pct}})"
        if len(top) > 1:
            s += f", then {top[1].get('title')} ({{top2_pct}})"
        parts.append(s + ".")
        if "top1_wage_annual" in vals:
            parts.append(f"Locally, the median pay for {t1} is {{top1_wage_annual}} a year"
                         + (", with projected growth of {top1_growth} over ten years." if "top1_growth" in vals else "."))
    else:
        parts.append("The career-fit model is not available yet, so this debrief covers your choices only.")
    parts.append("Treat this as a practice signal, not a verdict.")
    return " ".join(parts)


async def summarize(state: SimState) -> dict[str, Any]:
    rep = dict(state.get("report") or {})
    vals = summary_values(rep)
    allowed = sorted(vals)
    top = rep.get("top_careers") or []
    traits = sorted(rep.get("traits") or [], key=lambda t: -float(t.get("value", 0)))[:3]
    user = json.dumps({
        "placeholders": {k: PLACEHOLDER_MEANING.get(k, k) for k in allowed},
        "top_careers": [t.get("title") for t in top],
        "strongest_work_styles": [t.get("name") for t in traits],
        "crunch_happened": bool(rep.get("crunch_used")),
        "moments": [h.get("title") for h in rep.get("history") or []],
    }, ensure_ascii=False, sort_keys=True)
    fallback = mock_summary(rep, vals)
    obj, meta = await llm.astructured("sim_summary", SUMMARY_SYSTEM, user, ReportSummary, mock=lambda: {"paragraph": fallback})
    template = str(obj.paragraph)
    problems = verifier.placeholder_problems(template, allowed)
    source = meta["source"]
    if problems:
        template, source = fallback, "mock"
    text = verifier.fill_template(template, vals)
    leftovers = verifier.unbacked_numbers(text, list(vals.values()))
    if leftovers:  # belt and braces: never show a number we did not put there
        text, source = verifier.fill_template(fallback, vals), "mock"
    summary = {"text": text, "source": source, "numbers_from": "verified claims and this run's state only",
               "rejected_draft": bool(problems), "placeholders_used": sorted(set(re.findall(r"\{([a-z0-9_]+)\}", template)) & set(allowed))}
    rep["summary"] = summary
    note(summary="numbers only from verified claims" + (" · draft rejected, template used" if problems else ""))
    return {"report": rep, "summary": summary}


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


def build_graph(checkpointer: Any) -> Any:
    b = StateGraph(SimState)
    b.add_node("select_event", select_event)
    b.add_node("present_and_wait", present_and_wait)
    b.add_node("coworker", coworker, input_schema=CoworkerTask)
    b.add_node("score_choice", score_choice)
    b.add_node("update_state", update_state)
    b.add_node("inject_crunch", inject_crunch)
    b.add_node("report", report)
    b.add_node("verify", verify)
    b.add_node("summarize", summarize)

    b.add_edge(START, "select_event")
    b.add_conditional_edges("select_event", route_after_select, ["present_and_wait", "report"])
    b.add_conditional_edges("present_and_wait", fan_out, ["coworker", "score_choice"])
    b.add_edge("coworker", "score_choice")
    b.add_edge("score_choice", "update_state")
    b.add_conditional_edges("update_state", route_after_update, ["inject_crunch", "select_event", "report"])
    b.add_conditional_edges("inject_crunch", route_after_select, ["present_and_wait", "report"])
    b.add_edge("report", "verify")
    b.add_edge("verify", "summarize")
    b.add_edge("summarize", END)
    return b.compile(checkpointer=checkpointer)


_graph: Any = None


def get_graph() -> Any:
    """Process-wide graph on the shared SQLite checkpointer (api/.runtime/checkpoints.db)."""
    global _graph
    if _graph is None:
        from ..checkpoint import get_checkpointer

        _graph = build_graph(get_checkpointer())
    return _graph


def initial_state(learner_id: str, career_id: str | None) -> SimState:
    cids = data.career_ids()
    sel = selector()
    sel_state = sel.initial(cids)
    traits, post, method = sel.summary(sel_state)
    moods = {cid: initial_mood(cw) for cid, cw in all_coworkers().items()}
    return {
        "learner_id": learner_id, "career_id": career_id, "mode": "career" if career_id else "adaptive",
        "started_at": _now_iso(), "clock": DAY_START, "stats": dict(START_STATS), "moods": moods,
        "trait_estimate": traits, "trait_method": method, "posterior": post, "selector_state": sel_state,
        "history": [], "played": [], "reactions": [], "current_event": None, "selection": None,
        "last_choice": None, "scored": None, "crunch_used": False, "report": None, "verification": None, "summary": None,
    }


def trace_nodes(coworkers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nodes = [
        trace_node("select_event", "Pick next event", "model"),
        trace_node("present_and_wait", "Your choice", "human"),
        *[trace_node(f"coworker:{c['id']}", str(c.get("name") or c["id"]), "llm", group="coworkers_react") for c in coworkers],
        trace_node("score_choice", "Tag work styles", "llm"),
        trace_node("update_state", "Update player model", "model"),
        trace_node("inject_crunch", "Crunch check", "logic"),
        trace_node("report", "Career fit", "model"),
        trace_node("verify", "Verify facts", "logic"),
        trace_node("summarize", "Write debrief", "llm"),
    ]
    return [dict(n) for n in nodes]


def node_id(name: str, inp: Any) -> str | None:
    if name == "coworker" and isinstance(inp, dict):
        cw = inp.get("coworker") or {}
        return f"coworker:{cw.get('id')}" if cw.get("id") else None
    return None


def project(name: str, update: dict[str, Any]) -> dict[str, Any] | None:
    """UI-safe partial state for each finished node (CONTRACTS section 6 ``state`` events)."""
    if name == "select_event" or name == "inject_crunch":
        return {"selection": update.get("selection"), "clock": update.get("clock")}
    if name == "present_and_wait":
        lc = update.get("last_choice") or {}
        return {"choice": {"event_id": lc.get("event_id"), "choice_id": lc.get("choice_id"), "text": lc.get("text")}}
    if name == "coworker":
        return {"reactions": update.get("reactions") or []}
    if name == "score_choice":
        s = update.get("scored") or {}
        return {"scored": {"blended": s.get("blended"), "source": s.get("source"), "event_id": s.get("event_id")}}
    if name == "update_state":
        hist = update.get("history") or []
        return {"stats": update.get("stats"), "moods": update.get("moods"), "trait_estimate": update.get("trait_estimate"),
                "posterior": update.get("posterior"), "trait_method": update.get("trait_method"),
                "last": hist[-1] if hist else None}
    if name == "verify":
        return {"verification": (update.get("verification") or {}).get("counts")}
    return None


def public_state(values: dict[str, Any]) -> dict[str, Any]:
    """What GET /state returns (no hidden deltas for unplayed choices, no selector internals)."""
    return {
        "mode": values.get("mode"), "career_id": values.get("career_id"), "clock": values.get("clock"),
        "stats": values.get("stats"), "moods": values.get("moods"), "trait_estimate": values.get("trait_estimate"),
        "trait_method": values.get("trait_method"), "posterior": values.get("posterior"),
        "history": values.get("history") or [], "crunch_used": bool(values.get("crunch_used")),
        "started_at": values.get("started_at"),
    }


__all__ = [
    "CRUNCH_STRESS", "EVENTS_PER_DAY", "GRAPH_NAME", "START_STATS", "SimState", "build_graph", "events_available",
    "get_graph", "initial_state", "interrupt_payload", "node_id", "project", "public_state", "trace_nodes",
]
