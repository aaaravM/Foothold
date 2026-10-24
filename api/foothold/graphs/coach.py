"""Coach graph (SHEET 05, brief 5.4): peer-support listening partner + EQ practice.

Peer support and practice, not therapy. The coach is software: it never diagnoses,
never gives medical or legal advice, never claims confidentiality or professional status.

Nodes, in order (``kind="coach"`` runs all of them; ``kind="post"`` stops after moderate):

  safety_check            foothold.safety.detect_crisis FIRST. Crisis -> the calm, verified
                          988 message (CONTRACTS section 12) and END: no probing questions,
                          no model call, nothing stored or logged.
  moderate                group posts: safety.moderate_post (held posts are never shown to
                          others). Coach turns: contact details (phone, email, street address,
                          app handles) are redacted before anything reaches the model or memory.
  retrieve_memory         opt-in and session-scoped: earlier turns of THIS session only, from an
                          in-process store (never written to disk, 2 h TTL, Forget clears it).
  respond                 listening mode or EQ-practice mode via foothold.llm (text) with a
                          deterministic mock built from the message.
  verify                  replaces sentences that diagnose, give medical or legal advice, claim
                          confidentiality, or claim to be a therapist / counselor / lawyer.
  log_consented_progress  only with consent: saves the turn to session memory (memory opt-in)
                          and a non-personal progress row (mode + turn count, never the text).

No checkpointer on purpose: coach conversations can be personal, so graph state is not
persisted to api/.runtime/checkpoints.db. The graph has no human interrupts, so nothing
needs resuming; the only memory is the opt-in, in-process session store below.

Also exported for routes/circle.py: :func:`crisis_payload`, :func:`verify_text`,
:func:`eq_heuristic` (transparent rubric scoring used as the EQ feedback mock) and
:data:`MEMORY` (session store with ``forget``).
"""

from __future__ import annotations

import re
import threading
import time
from collections import deque
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from foothold import db, llm, safety
from foothold.sse import note, trace_node

GRAPH_NAME = "coach"
MODES = ("listening", "eq_practice")
Mode = Literal["listening", "eq_practice"]
MODE_LABEL = {"listening": "listening mode", "eq_practice": "EQ practice mode"}

MAX_COACH_CHARS = 2000
REPLY_MAX_CHARS = 1100

# ---------------------------------------------------------------------------
# Crisis copy: the VERIFIED 988 sentence (docs/research/stats.md, id lifeline_988,
# retrieved 2026-10-24) plus the 911 line CONTRACTS section 12 allows. It deliberately
# leaves out "confidential": Foothold never makes that claim in its own voice.
# ---------------------------------------------------------------------------

LIFELINE_988 = {
    "id": "lifeline_988",
    "text": (
        "You don't have to go through this alone. Call or text 988, or chat at chat.988lifeline.org, "
        "to reach the 988 Suicide & Crisis Lifeline. It's free and available 24/7. En español: marque 988 "
        "y luego presione 2, o envíe AYUDA al 988 por mensaje de texto. You can also reach out to someone "
        "you trust."
    ),
    "source": "988 Suicide & Crisis Lifeline",
    "url": "https://988lifeline.org/",
    "chat_url": "https://chat.988lifeline.org/",
    "es_url": "https://988lifeline.org/es/inicio/",
    "retrieved": "2026-10-24",
    "status": "REAL",
}
EMERGENCY_LINE = "If you're in immediate danger, call 911."


def crisis_payload() -> dict[str, Any]:
    """Calm 988 panel content. Statements only: no questions, no diagnosis."""
    return {
        "crisis": True,
        "message": f"{LIFELINE_988['text']} {EMERGENCY_LINE}",
        "lifeline": LIFELINE_988["text"],
        "emergency": EMERGENCY_LINE,
        "resources": [
            {"id": "call_988", "label": "Call 988", "href": "tel:988"},
            {"id": "text_988", "label": "Text 988", "href": "sms:988"},
            {"id": "chat_988", "label": "Chat at chat.988lifeline.org", "href": LIFELINE_988["chat_url"]},
            {"id": "call_911", "label": "Call 911 if you're in immediate danger", "href": "tel:911"},
        ],
        "source": {
            "label": LIFELINE_988["source"],
            "url": LIFELINE_988["url"],
            "es_url": LIFELINE_988["es_url"],
            "retrieved": LIFELINE_988["retrieved"],
            "status": LIFELINE_988["status"],
        },
        "note": "The coach stopped here for this message. It won't ask questions or keep practicing right now.",
    }


# ---------------------------------------------------------------------------
# Opt-in, session-scoped memory (in-process only)
# ---------------------------------------------------------------------------

MEMORY_TTL_S = 2 * 3600
MEMORY_MAX_TURNS = 6
MEMORY_MAX_SESSIONS = 512
MEMORY_TURN_CHARS = 600


class SessionMemory:
    """Last few turns per (account, session). Never persisted; expires after 2 h idle."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[tuple[str, str], dict[str, Any]] = {}

    def _prune(self, now: float) -> None:
        for key in [k for k, v in self._data.items() if now - v["updated"] > MEMORY_TTL_S]:
            self._data.pop(key, None)
        if len(self._data) > MEMORY_MAX_SESSIONS:
            for key, _ in sorted(self._data.items(), key=lambda kv: kv[1]["updated"])[: len(self._data) - MEMORY_MAX_SESSIONS]:
                self._data.pop(key, None)

    def get(self, account_id: str, session_id: str) -> list[dict[str, str]]:
        now = time.time()
        with self._lock:
            self._prune(now)
            entry = self._data.get((account_id, session_id))
            return [dict(t) for t in entry["turns"]] if entry else []

    def append(self, account_id: str, session_id: str, person: str, coach: str) -> int:
        now = time.time()
        with self._lock:
            self._prune(now)
            entry = self._data.setdefault((account_id, session_id), {"turns": deque(maxlen=MEMORY_MAX_TURNS), "updated": now})
            entry["turns"].append({"person": person[:MEMORY_TURN_CHARS], "coach": coach[:MEMORY_TURN_CHARS]})
            entry["updated"] = now
            return len(entry["turns"])

    def forget(self, account_id: str, session_id: str) -> bool:
        with self._lock:
            return self._data.pop((account_id, session_id), None) is not None

    def turns(self, account_id: str, session_id: str) -> int:
        return len(self.get(account_id, session_id))

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


MEMORY = SessionMemory()

# ---------------------------------------------------------------------------
# Contact-detail redaction (coach turns). Uses safety's moderation patterns when
# available so posts and coach turns agree; minimal fallbacks otherwise.
# ---------------------------------------------------------------------------


def _pattern(name: str, fallback: str | None) -> re.Pattern[str] | None:
    p = getattr(safety, name, None)
    if isinstance(p, re.Pattern):
        return p
    return re.compile(fallback, re.I) if fallback else None


_REDACTORS: list[tuple[str, re.Pattern[str] | None, str]] = [
    ("email", _pattern("_EMAIL", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"), "[email removed]"),
    ("email", _pattern("_EMAIL_OBFUSCATED", None), "[email removed]"),
    ("phone", _pattern("_PHONE", r"(?<![\w-])(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}(?![\w-])"), "[phone removed]"),
    ("address", _pattern("_ADDRESS", None), "[address removed]"),
    ("handle", _pattern("_CONTACT_HANDLE", None), "[handle removed]"),
]


def redact_contact_details(text: str) -> tuple[str, list[str]]:
    kinds: list[str] = []
    for kind, pattern, label in _REDACTORS:
        if pattern is None:
            continue
        new, n = pattern.subn(label, text)
        if n:
            text = new
            if kind not in kinds:
                kinds.append(kind)
    return text, kinds


# ---------------------------------------------------------------------------
# verify: strip / replace medical, legal, confidentiality and professional claims
# ---------------------------------------------------------------------------

_CONDITIONS = (
    r"(?:clinical |major |severe |mild |chronic |high[- ]functioning )?"
    r"(?:depression|depressive disorder|anxiety disorder|generalized anxiety|social anxiety|panic disorder|ptsd|c-?ptsd|"
    r"adhd|add|ocd|bipolar(?: disorder)?|borderline(?: personality)?(?: disorder)?|schizophreni\w*|autism|asperger\w*|"
    r"an? eating disorder|anorexia|bulimia|insomnia|a personality disorder|a mental (?:illness|disorder)|"
    r"a disorder|a (?:mental )?health condition|burnout syndrome|trauma response)"
)
_MEDS = (
    r"(?:medications?|meds|pills|antidepressants?|ssris?|snris?|benzos?|xanax|zoloft|prozac|lexapro|wellbutrin|"
    r"adderall|ritalin|melatonin|ibuprofen|advil|tylenol|acetaminophen|benadryl|nyquil|cbd|edibles|sleeping pills?|"
    r"supplements?|ashwagandha)"
)
_VERIFY_RULES: dict[str, list[re.Pattern[str]]] = {
    "medical": [
        re.compile(
            rf"\byou(?:'re| are)?\s+(?:might |may |probably |likely |definitely |clearly |seem to |could )?"
            rf"(?:have|be suffering from|are suffering from|suffer from|be showing signs of|are showing (?:signs|symptoms) of|"
            rf"show (?:signs|symptoms) of|be dealing with|are dealing with)\s+{_CONDITIONS}\b",
            re.I,
        ),
        re.compile(rf"\b(?:sounds|seems|looks) like (?:you(?:'ve| have| might have| may have)? )?{_CONDITIONS}\b", re.I),
        re.compile(rf"\bthat(?:'s| is) (?:a |an )?(?:classic |common )?(?:sign|symptom)s? of\b", re.I),
        re.compile(r"\b(?:i(?:'d| would)? diagnose|my diagnosis|you(?:'re| are) (?:clinically )?(?:depressed|bipolar|autistic|traumatized))\b", re.I),
        re.compile(
            rf"\b(?:you should|you could|you need to|try|start|stop|consider|increase|decrease|double|skip|quit)\s+"
            rf"(?:taking |using |your |some |a )?(?:\w+ )?{_MEDS}\b",
            re.I,
        ),
        re.compile(rf"\byou (?:need|should get|should be on|should go on)\s+(?:some )?{_MEDS}\b", re.I),
        re.compile(r"\b\d+(?:\.\d+)?\s?(?:mg|mcg|milligrams?|micrograms?)\b", re.I),
    ],
    "legal": [
        re.compile(
            r"\b(?:you should|you can|you could|you need to|go ahead and|definitely)\s+(?:\w+ )?(?:sue|file (?:a )?(?:lawsuit|legal claim|"
            r"wage claim|claim|complaint|charges|report)|press charges|take (?:them|him|her|it|your (?:boss|employer|landlord|school)) to court|"
            r"get a restraining order|report (?:them|him|her|it) to (?:the )?(?:labor (?:board|commissioner)|eeoc|crd|dfeh|osha|police))\b",
            re.I,
        ),
        re.compile(
            r"\b(?:that(?:'s| is| was)|it(?:'s| is| was)|this is|what they did is|they(?:'re| are)) (?:definitely |clearly |totally |probably |likely )?"
            r"(?:illegal|unlawful|against the law|a crime|criminal|wrongful termination|retaliation under the law|"
            r"discrimination under the law|a (?:labor|civil rights|osha) violation|a violation of (?:the law|labor law|your rights))\b",
            re.I,
        ),
        re.compile(r"\byou (?:have|'ve got|got) (?:a |the |every )?(?:legal right|right to sue|(?:strong |good )?(?:legal )?case|grounds to sue|grounds for a lawsuit)\b", re.I),
        re.compile(r"\b(?:they|he|she|your (?:boss|employer|manager|supervisor|landlord|school)) (?:can'?t|cannot|can not|aren'?t allowed to|is not allowed to|isn'?t allowed to) legally\b", re.I),
        re.compile(r"\b(?:legally|by law|under (?:california|federal|state|labor) law),? (?:they|you|your|he|she|employers?)\b", re.I),
        re.compile(r"\b(?:entitled to|owed) (?:back pay|overtime pay|compensation|damages|a settlement)\b", re.I),
    ],
    "confidentiality": [
        re.compile(
            r"\b(?:this|this chat|this conversation|our (?:chat|conversation|talk)|everything you (?:say|share|tell me|write)|"
            r"what you (?:say|share|tell me|write)|anything you (?:say|share|tell me|write)|your messages?)\b[^.!?]{0,40}?"
            r"\b(?:is|are|stays?|will stay|remains?|will remain|will be|is kept|are kept)\s+(?:completely |totally |100% |strictly |fully )?"
            r"(?:confidential|private|secret|anonymous|between (?:you and me|us)|just between us|safe with me)\b",
            re.I,
        ),
        re.compile(r"\bi (?:won'?t|will not|wont|never|promise not to) (?:tell|share|report|repeat|show)\b", re.I),
        re.compile(r"\b(?:no ?one|nobody|noone) (?:else )?(?:will|can|is going to) (?:ever )?(?:see|read|know|find out)\b", re.I),
        re.compile(r"\b(?:fully |completely |totally )?confidential\b", re.I),
    ],
    "professional": [
        re.compile(
            r"\bi(?:'m| am) (?:a |an |your )?(?:licensed |trained |certified )?(?:therapist|counselor|counsellor|psychologist|psychiatrist|"
            r"doctor|physician|nurse|lawyer|attorney|social worker|clinician|mental health professional)\b",
            re.I,
        ),
        re.compile(r"\bas (?:a|your) (?:therapist|counselor|counsellor|psychologist|doctor|lawyer|attorney|clinician)\b", re.I),
        re.compile(r"\b(?:this|what we(?:'re| are) doing) is (?:therapy|treatment|counseling|counselling|clinical)\b", re.I),
    ],
}
# Sentences that *deny* a claim are fine ("I can't give medical advice", "This isn't therapy").
_NEGATED = re.compile(
    r"\b(?:can'?t|cannot|can not|won'?t|will not|isn'?t|is not|aren'?t|are not|not able to|unable to|not a|not an|not your|"
    r"no substitute|not (?:therapy|treatment|counseling|medical|legal|confidential|private)|i'm not|i am not|never (?:diagnose|give))\b",
    re.I,
)
REPLACEMENT = {
    "medical": "I can't diagnose anything or give medical advice; a doctor, nurse, or clinic can help with that part.",
    "legal": "I can't give legal advice; a legal aid clinic or a lawyer can help with questions about your rights.",
    "confidentiality": "Foothold can't promise confidentiality, so share only what you're comfortable sharing.",
    "professional": "I'm a practice tool, not a therapist, counselor, or lawyer.",
}
VERIFY_CHECKS = list(_VERIFY_RULES)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[\"'A-Z0-9(])")


def _claim_kind(sentence: str) -> str | None:
    for kind, patterns in _VERIFY_RULES.items():
        if any(p.search(sentence) for p in patterns):
            if _NEGATED.search(sentence):
                continue
            return kind
    return None


def verify_text(text: str) -> tuple[str, dict[str, Any]]:
    """Replace claim sentences; returns ``(text, {checked, replaced:[{kind}], changed})``.

    Line structure is kept (EQ practice replies use labeled lines). Each replacement
    sentence appears at most once per reply.
    """
    replaced: list[dict[str, str]] = []
    used: set[str] = set()
    out_lines: list[str] = []
    for line in str(text or "").splitlines():
        if not line.strip():
            out_lines.append(line)
            continue
        parts = _SENTENCE_SPLIT.split(line.strip())
        kept: list[str] = []
        for sentence in parts:
            kind = _claim_kind(sentence)
            if kind is None:
                kept.append(sentence)
                continue
            replaced.append({"kind": kind})
            if kind not in used:
                used.add(kind)
                kept.append(REPLACEMENT[kind])
        out_lines.append(" ".join(kept))
    cleaned = "\n".join(out_lines).strip()
    return cleaned, {"checked": VERIFY_CHECKS, "replaced": replaced, "changed": bool(replaced)}


def _verify_summary(info: dict[str, Any]) -> str:
    if not info.get("replaced"):
        return "no medical, legal or confidentiality claims"
    counts: dict[str, int] = {}
    for r in info["replaced"]:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1
    return "replaced " + ", ".join(f"{n} {k} claim{'s' if n > 1 else ''}" for k, n in counts.items())


# ---------------------------------------------------------------------------
# EQ rubric: transparent heuristic (mock for the EQ feedback endpoint and the
# practice-mode reply). Marker labels are returned as evidence, never user text.
# ---------------------------------------------------------------------------

EQ_DIMENSIONS: list[dict[str, Any]] = [
    {
        "id": "listening",
        "label": "Listening",
        "anchors": {
            1: "Doesn't show what was heard.",
            2: "Acknowledges vaguely.",
            3: "Reflects the main point back.",
            4: "Reflects the point and checks understanding.",
        },
    },
    {
        "id": "empathy",
        "label": "Empathy",
        "anchors": {
            1: "Dismisses or skips the feeling.",
            2: "Polite but flat.",
            3: "Names or validates the feeling.",
            4: "Validates the feeling and shows why it makes sense.",
        },
    },
    {
        "id": "assertiveness",
        "label": "Assertiveness",
        "anchors": {
            1: "Passive, or aggressive.",
            2: "Own need is unclear.",
            3: "States own need clearly and respectfully.",
            4: "Clear need plus a specific, respectful request.",
        },
    },
    {
        "id": "repair",
        "label": "Repair",
        "anchors": {
            1: "Blames or escalates.",
            2: "No repair attempt.",
            3: "Owns a part or offers a fix.",
            4: "Owns a part and proposes a concrete next step.",
        },
    },
]
EQ_IDS = [d["id"] for d in EQ_DIMENSIONS]

_EQ_MARKERS: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    "listening": [
        ("reflects (\"sounds like\", \"it seems\")", re.compile(r"\b(?:sounds like|it seems|seems like|i hear (?:you|that)|i'm hearing|i am hearing)\b", re.I)),
        ("refers to what they said", re.compile(r"\byou(?:'re| are)? (?:said|saying|mentioned|told me|feel|felt|were|got)\b", re.I)),
        ("checks understanding", re.compile(r"\b(?:if i (?:understand|heard|got that)|so what i'?m hearing|did i get that|is that right|am i right|let me make sure)\b", re.I)),
        ("asks to understand", re.compile(r"\b(?:what happened|tell me (?:more|what)|help me understand|walk me through|what do you need|what would help|how can i help)\b|\?", re.I)),
    ],
    "empathy": [
        ("names a feeling", re.compile(r"\b(?:frustrat\w*|stress\w*|upset|worried|overwhelm\w*|tired|exhausted|annoyed|disappointed|nervous|scared|hurt|angry|hard|tough|rough|unfair)\b", re.I)),
        ("validates", re.compile(r"\b(?:makes sense|that'?s fair|fair enough|i get (?:it|that|why)|i understand|i can see|i can tell|no wonder|i'd feel|i would feel|i'd be|anyone would)\b", re.I)),
        ("appreciates", re.compile(r"\b(?:thank you|thanks|i appreciate|appreciate (?:you|it|that|the))\b", re.I)),
        ("sorry for what they went through", re.compile(r"\bsorry (?:you|that|this|to hear|for (?:the|your))\b", re.I)),
    ],
    "assertiveness": [
        ("I-statement", re.compile(r"\bi (?:feel|felt|need|want|would like|'d like|prefer|think|noticed)\b|\bi'd like\b", re.I)),
        ("clear request", re.compile(r"\b(?:can we|could we|could you|would you|will you|let'?s|please|i'm asking|i am asking)\b", re.I)),
        ("states a limit", re.compile(r"\b(?:i can'?t|i cannot|i'm not able|i am not able|i won'?t be able|that doesn'?t work for me|i need to|i have to)\b", re.I)),
        ("specific time or detail", re.compile(r"\b(?:by|before|after|on|at) (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|tonight|today|lunch|break|the end of (?:the )?(?:day|shift|week))\b|\b\d{1,2}(?::\d{2})?\s?(?:am|pm|a\.m\.|p\.m\.)\b", re.I)),
    ],
    "repair": [
        ("owns a part", re.compile(r"\b(?:my (?:bad|mistake|fault|part)|i should have|i shouldn'?t have|i was wrong|i messed up|i dropped the ball|i apologi[sz]e|i'?m sorry i|i am sorry i|sorry i|sorry for (?:my|being|not))\b", re.I)),
        ("proposes a next step", re.compile(r"\b(?:next time|going forward|from now on|how about|what if we|let'?s try|i'?ll|i will|can we try|to fix|make (?:it|this) right|figure (?:it|this) out|plan)\b", re.I)),
        ("checks back", re.compile(r"\b(?:does that work|would that help|is that okay|is that ok|how does that sound|what do you think|work for you|sound good)\b", re.I)),
    ],
}
_ESCALATION = re.compile(
    r"\b(?:you always|you never|whatever|shut up|not my problem|your fault|deal with it|i don'?t care|calm down|get over it|"
    r"stupid|idiot|ridiculous|so what|who cares)\b",
    re.I,
)

_EQ_NOTES: dict[str, dict[int, str]] = {
    "listening": {
        1: "Start by showing you heard them: repeat their main point back in a few words.",
        2: "You touched on what they said; reflect it more directly before answering.",
        3: "You reflected their main point back.",
        4: "You reflected their point and checked that you understood it.",
    },
    "empathy": {
        1: "Name how they might feel before moving to the problem.",
        2: "You stayed polite; adding one line that names their feeling would land warmer.",
        3: "You named or validated how they feel.",
        4: "You validated the feeling and showed why it makes sense.",
    },
    "assertiveness": {
        1: "Say what you need with an I-statement, calmly and without blame.",
        2: "Your own need is in there; say it plainly and add one specific ask.",
        3: "You stated your need clearly and respectfully.",
        4: "Clear need plus a specific, respectful request.",
    },
    "repair": {
        1: "Lower the heat: drop blame words and offer one way forward.",
        2: "Offer a fix or own a small part to move things forward.",
        3: "You owned a part or offered a fix.",
        4: "You owned a part and proposed a concrete next step.",
    },
}
_EQ_SAMPLE_LINE = {
    "listening": "\"So the main thing is the delay left you covering for everyone. Did I get that right?\"",
    "empathy": "\"That sounds really frustrating, and it makes sense you're upset.\"",
    "assertiveness": "\"I need a heads-up before shift changes. Can we agree on a text by noon?\"",
    "repair": "\"I dropped the ball on that. Next time I'll flag it before break. Does that work?\"",
}


def eq_heuristic(response: str) -> dict[str, Any]:
    """Transparent rubric scoring: distinct marker types matched per skill -> 1..4.

    score = 1 + min(3, markers matched); blame/escalation words cost empathy and repair
    two points and assertiveness one; replies under 6 words are capped at 2.
    Returns ``{scores, notes, basis, strength, try_next, escalation}``.
    """
    text = str(response or "")
    words = len(re.findall(r"[A-Za-z']+", text))
    escalation = bool(_ESCALATION.search(text))
    scores: dict[str, int] = {}
    basis: dict[str, list[str]] = {}
    for dim in EQ_IDS:
        hits = [label for label, pattern in _EQ_MARKERS[dim] if pattern.search(text)]
        score = 1 + min(3, len(hits))
        if escalation:
            score -= 2 if dim in ("empathy", "repair") else (1 if dim == "assertiveness" else 0)
        if words < 6:
            score = min(score, 2)
        scores[dim] = max(1, min(4, score))
        basis[dim] = hits
    if escalation:
        basis["repair"] = basis["repair"] + ["blame or escalation words lowered empathy and repair"]
    best = max(EQ_IDS, key=lambda d: (scores[d], -EQ_IDS.index(d)))
    worst = min(EQ_IDS, key=lambda d: (scores[d], EQ_IDS.index(d)))
    strength = (
        _EQ_NOTES[best][scores[best]] if scores[best] >= 3 else "You showed up for a hard conversation; that's the first step."
    )
    try_next = f"{_EQ_NOTES[worst][min(scores[worst], 2)]} For example: {_EQ_SAMPLE_LINE[worst]}"
    if scores[worst] >= 4:
        try_next = "Keep the same shape and say it out loud once before the real conversation."
    return {
        "scores": scores,
        "notes": {d: _EQ_NOTES[d][scores[d]] for d in EQ_IDS},
        "basis": basis,
        "strength": strength,
        "try_next": try_next,
        "escalation": escalation,
        "words": words,
    }


# ---------------------------------------------------------------------------
# Prompts and deterministic mock replies
# ---------------------------------------------------------------------------

LISTENING_SYSTEM = (
    "You are the Foothold coach: a peer-support listening partner for people in California's Central Valley who are "
    "working, studying, caregiving, or changing careers. You are software, not a therapist, counselor, doctor, or lawyer, "
    "and this is peer support, not therapy.\n"
    "Do: reflect back what you heard in plain, warm words; name the feeling tentatively (\"sounds like...\"); notice "
    "effort and strengths; if it fits, offer one small, practical next step; ask at most one short open question.\n"
    "Never: diagnose or name conditions; give medical, medication, or legal advice; promise confidentiality or privacy; "
    "claim to be human or a professional; lecture; use lists, headings, or emojis.\n"
    "If health or legal questions come up, suggest a doctor, clinic, or legal aid in general terms.\n"
    "Reply in 2 to 4 short sentences.\n" + safety.UNTRUSTED_NOTE
)

PRACTICE_SYSTEM = (
    "You are the Foothold practice partner for emotional-intelligence skills at work and school: listening, empathy, "
    "assertiveness, and repair. This is practice, not treatment, and you are software, not a therapist.\n"
    "The person writes what they would say in a hard conversation (with a coworker, lead, instructor, or family member) "
    "or describes the situation. Reply in exactly three short lines:\n"
    "What worked: one specific strength in their wording.\n"
    "Try: one concrete adjustment tied to listening, empathy, assertiveness, or repair.\n"
    "You could say: one sample first-person line in quotes, under 30 words.\n"
    "Never diagnose, give medical or legal advice, or promise confidentiality. No emojis.\n" + safety.UNTRUSTED_NOTE
)

_FEELINGS: list[tuple[tuple[str, ...], str]] = [
    (("overwhelm", "too much", "drowning", "swamped", "buried", "so much"), "like a lot is landing on you at once"),
    (("exhausted", "tired", "worn out", "burned out", "burnt out", "no sleep", "drained", "wiped"), "exhausting"),
    (("stress", "pressure", "tense", "stretched"), "stressful"),
    (("nervous", "anxious", "scared", "afraid", "worried", "worry", "freaking out", "dread"), "nerve-racking"),
    (("frustrat", "angry", "mad", "furious", "annoyed", "fed up", "unfair"), "frustrating"),
    (("lonely", "alone", "isolated", "no one to talk", "nobody to talk", "left out"), "lonely"),
    (("sad", "down", "bummed", "upset", "hurt", "discouraged"), "really hard"),
    (("excited", "proud", "stoked", "glad", "happy", "relieved"), "like something good is happening"),
    (("confused", "lost", "don't know", "dont know", "not sure", "unsure", "stuck"), "confusing"),
]
_TOPICS: list[tuple[tuple[str, ...], str, str]] = [
    (("shift", "overtime", "schedule", "hours", "graveyard", "night"), "juggling your hours",
     "Which part of the schedule feels least workable right now?"),
    (("boss", "supervisor", "manager", "foreman", "lead "), "how things are going with your lead",
     "What would you most want them to understand?"),
    (("coworker", "co-worker", "crew", "team", "partner on the line"), "how things are going with your crew",
     "What happened right before it got tense?"),
    (("class", "school", "college", "course", "exam", "test", "homework", "fafsa", "instructor", "professor"),
     "keeping school moving", "Which piece of school is weighing on you most this week?"),
    (("money", "rent", "bills", "paycheck", "afford", "cost", "tuition", "gas"), "money pressure",
     "What's one cost that's hardest to plan around?"),
    (("kid", "kids", "family", "mom", "dad", "daughter", "son", "parents", "abuela", "grandma"),
     "taking care of family on top of everything", "Who else, if anyone, helps carry the family side?"),
    (("interview", "application", "apply", "resume", "hiring", "job offer"), "the job search",
     "What's the next step you're facing in the search?"),
    (("career", "switch", "start over", "trade", "apprentice", "certificate", "new field"), "a big career change",
     "What's pulling you toward the change?"),
]


def _first_match(text: str, table: list[tuple[Any, ...]]) -> tuple[Any, ...] | None:
    low = f" {text.lower()} "
    for row in table:
        if any(k in low for k in row[0]):
            return row
    return None


def mock_listening(text: str, prior_turns: int = 0) -> str:
    feeling = _first_match(text, _FEELINGS)
    topic = _first_match(text, _TOPICS)
    parts: list[str] = []
    if prior_turns:
        parts.append("Thanks for coming back to this.")
    if feeling and feeling[1].startswith("like"):
        parts.append(f"That sounds {feeling[1]}.")
    elif feeling:
        parts.append(f"That sounds {feeling[1]}.")
    else:
        parts.append("Thanks for putting that into words.")
    if topic:
        parts.append(f"It sounds like {topic[1]} is taking a lot of your energy right now.")
        parts.append(topic[2])
    else:
        parts.append("It sounds like there's a lot going on, and it makes sense to slow down and sort it out.")
        parts.append("What feels most important to talk through first?")
    return " ".join(parts)


def mock_practice(text: str, scenario: dict[str, Any] | None = None) -> str:
    h = eq_heuristic(text)
    best = max(EQ_IDS, key=lambda d: (h["scores"][d], -EQ_IDS.index(d)))
    worst = min(EQ_IDS, key=lambda d: (h["scores"][d], EQ_IDS.index(d)))
    worked = _EQ_NOTES[best][h["scores"][best]] if h["scores"][best] >= 3 else "You put your side into words, which is the hard part."
    tip = _EQ_NOTES[worst][min(h["scores"][worst], 2)]
    return f"What worked: {worked}\nTry: {tip}\nYou could say: {_EQ_SAMPLE_LINE[worst]}"


def _tidy_reply(text: str) -> str:
    t = str(text or "").replace("\r\n", "\n").strip()
    t = re.sub(r"^#+\s*", "", t, flags=re.M)  # no markdown headings
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)  # no bold markers
    t = re.sub(r"\n{3,}", "\n\n", t)
    if len(t) > REPLY_MAX_CHARS:
        cut = t[:REPLY_MAX_CHARS]
        t = cut[: max(cut.rfind(". "), cut.rfind("\n"), 200) + 1].rstrip()
    return t


def _user_prompt(mode: str, text: str, history: list[dict[str, str]], scenario: dict[str, Any] | None) -> str:
    lines = [f"Mode: {'listening' if mode == 'listening' else 'EQ practice'}"]
    if scenario:
        title = safety.sanitize_untrusted(str(scenario.get("title") or ""), "scenario", 160)["text"]
        situation = safety.sanitize_untrusted(str(scenario.get("situation") or ""), "scenario", 700)["text"]
        line = safety.sanitize_untrusted(str(scenario.get("line") or ""), "scenario", 300)["text"]
        lines.append(f"Practice scenario (Foothold's synthetic scenario set): {title}. {situation}")
        if line:
            lines.append(f'The other person says: "{line}"')
    if history:
        convo = "\n".join(f"Person: {t['person']}\nCoach: {t['coach']}" for t in history)
        lines.append("Earlier in this session (the person opted in to session memory; most recent last):")
        lines.append(safety.wrap_untrusted(convo, "session_memory", 3600))
    lines.append("Message:")
    lines.append(safety.wrap_untrusted(text, "coach_message", MAX_COACH_CHARS))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


class CoachState(TypedDict, total=False):
    kind: Literal["coach", "post"]
    mode: str
    text: str
    account_id: str
    persona_id: str
    session_id: str
    memory_opt_in: bool
    log_consent: bool
    scenario: dict[str, Any] | None
    crisis: bool
    moderation: dict[str, Any] | None
    clean_text: str
    redactions: list[str]
    history: list[dict[str, str]]
    draft: str
    llm_source: str
    reply: str
    verify: dict[str, Any]
    memory_saved: bool
    memory_turns: int
    progress_logged: bool


def safety_check(state: CoachState) -> dict[str, Any]:
    hit = safety.detect_crisis(state.get("text") or "")
    if hit["crisis"]:
        note(summary="crisis signal · 988 message shown, turn ended" if state.get("kind", "coach") == "coach"
             else "crisis signal · 988 message shown to the poster")
        return {"crisis": True}
    note(summary="no crisis signal")
    return {"crisis": False}


def _after_safety(state: CoachState) -> str:
    if state.get("crisis") and state.get("kind", "coach") == "coach":
        return "end"
    return "moderate"


def moderate(state: CoachState) -> dict[str, Any]:
    text = state.get("text") or ""
    if state.get("kind") == "post":
        result = safety.moderate_post(text)
        reasons = list(result.get("reasons") or [])
        if result.get("crisis") and "crisis" not in reasons:
            reasons.insert(0, "crisis")
        status = "held" if reasons else "approved"
        moderation = {"status": status, "reasons": reasons, "note": safety.hold_message(reasons)}
        note(summary="approved · visible to the circle" if status == "approved" else f"held · {', '.join(reasons)} · only the poster sees it")
        return {"moderation": moderation, "crisis": bool(state.get("crisis") or result.get("crisis"))}
    clean, kinds = redact_contact_details(text)
    note(summary=f"redacted {', '.join(kinds)} before the model" if kinds else "no contact details to redact")
    return {"clean_text": clean, "redactions": kinds}


def _after_moderate(state: CoachState) -> str:
    return "end" if state.get("kind") == "post" else "retrieve_memory"


def retrieve_memory(state: CoachState) -> dict[str, Any]:
    if not state.get("memory_opt_in"):
        note(summary="memory off · this message stands alone")
        return {"history": []}
    history = MEMORY.get(state.get("account_id") or "", state.get("session_id") or "")
    note(summary=f"memory on · {len(history)} earlier turn{'s' if len(history) != 1 else ''} from this session")
    return {"history": history}


async def respond(state: CoachState) -> dict[str, Any]:
    mode = state.get("mode") if state.get("mode") in MODES else "listening"
    text = state.get("clean_text") or state.get("text") or ""
    history = state.get("history") or []
    scenario = state.get("scenario") if mode == "eq_practice" else None
    system = LISTENING_SYSTEM if mode == "listening" else PRACTICE_SYSTEM
    user = _user_prompt(mode, text, history, scenario)

    def mock() -> str:
        return mock_listening(text, len(history)) if mode == "listening" else mock_practice(text, scenario)

    reply, meta = await llm.atext(f"circle.coach.{mode}", system, user, mock=mock)
    reply = _tidy_reply(reply) or mock()
    note(summary=f"{MODE_LABEL[mode]} · {len(reply.split())} words")
    return {"draft": reply, "llm_source": meta["source"]}


def verify(state: CoachState) -> dict[str, Any]:
    cleaned, info = verify_text(state.get("draft") or "")
    if not cleaned:
        cleaned = mock_listening(state.get("clean_text") or "") if state.get("mode") != "eq_practice" else mock_practice(state.get("clean_text") or "")
        cleaned, info2 = verify_text(cleaned)
        info["replaced"] = info["replaced"] + info2["replaced"]
    note(summary=_verify_summary(info))
    return {"reply": cleaned, "verify": info}


def log_consented_progress(state: CoachState) -> dict[str, Any]:
    account_id = state.get("account_id") or ""
    session_id = state.get("session_id") or ""
    memory_saved = False
    turns = 0
    if state.get("memory_opt_in") and account_id and session_id:
        turns = MEMORY.append(account_id, session_id, state.get("clean_text") or "", state.get("reply") or "")
        memory_saved = True
    progress_logged = False
    if state.get("log_consent") and state.get("persona_id"):
        try:
            db.insert(
                "progress_log",
                {
                    "learner_id": state["persona_id"],
                    "kind": "circle_coach",
                    "payload_json": {"mode": state.get("mode"), "session_turns": turns or None, "source": "coach"},
                },
            )
            progress_logged = True
        except Exception:  # noqa: BLE001 - logging progress must never break the reply
            progress_logged = False
    parts = ["memory: saved (this session only)" if memory_saved else "memory: off"]
    parts.append("progress: logged, no text" if progress_logged else "progress: consent off, nothing logged")
    note(summary=" · ".join(parts))
    return {"memory_saved": memory_saved, "memory_turns": turns, "progress_logged": progress_logged}


def build_graph() -> Any:
    builder = StateGraph(CoachState)
    builder.add_node("safety_check", safety_check)
    builder.add_node("moderate", moderate)
    builder.add_node("retrieve_memory", retrieve_memory)
    builder.add_node("respond", respond)
    builder.add_node("verify", verify)
    builder.add_node("log_consented_progress", log_consented_progress)
    builder.add_edge(START, "safety_check")
    builder.add_conditional_edges("safety_check", _after_safety, {"end": END, "moderate": "moderate"})
    builder.add_conditional_edges("moderate", _after_moderate, {"end": END, "retrieve_memory": "retrieve_memory"})
    builder.add_edge("retrieve_memory", "respond")
    builder.add_edge("respond", "verify")
    builder.add_edge("verify", "log_consented_progress")
    builder.add_edge("log_consented_progress", END)
    return builder.compile()  # no checkpointer: see module docstring


GRAPH = build_graph()

COACH_NODES = [
    trace_node("safety_check", "Safety check", "logic"),
    trace_node("moderate", "Redact contact details", "logic"),
    trace_node("retrieve_memory", "Session memory (opt-in)", "logic"),
    trace_node("respond", "Respond", "llm"),
    trace_node("verify", "Verify: no medical or legal claims", "logic"),
    trace_node("log_consented_progress", "Log with consent", "logic"),
]
POST_NODES = [
    trace_node("safety_check", "Safety check", "logic"),
    trace_node("moderate", "Moderate post", "logic"),
]


def project(node: str, update: dict[str, Any]) -> dict[str, Any] | None:
    """UI-safe state patches. The unverified draft is never sent."""
    if node == "safety_check":
        return {"crisis": True, "crisis_payload": crisis_payload()} if update.get("crisis") else {"crisis": False}
    if node == "moderate":
        if "moderation" in update:
            return {"moderation": update["moderation"]}
        return {"redactions": update.get("redactions") or []}
    if node == "retrieve_memory":
        return {"memory": {"turns_used": len(update.get("history") or [])}}
    if node == "verify":
        return {"reply": update.get("reply"), "verify": update.get("verify")}
    if node == "log_consented_progress":
        return {
            "memory_saved": bool(update.get("memory_saved")),
            "memory_turns": int(update.get("memory_turns") or 0),
            "progress_logged": bool(update.get("progress_logged")),
        }
    return None


def result(values: dict[str, Any]) -> dict[str, Any]:
    if values.get("crisis"):
        return crisis_payload()
    return {
        "crisis": False,
        "mode": values.get("mode"),
        "reply": values.get("reply") or "",
        "verify": values.get("verify") or {"checked": VERIFY_CHECKS, "replaced": [], "changed": False},
        "redactions": values.get("redactions") or [],
        "memory": {
            "enabled": bool(values.get("memory_opt_in")),
            "turns_used": len(values.get("history") or []),
            "saved": bool(values.get("memory_saved")),
            "turns_stored": int(values.get("memory_turns") or 0),
        },
        "progress_logged": bool(values.get("progress_logged")),
        "llm": values.get("llm_source"),
    }


__all__ = [
    "COACH_NODES",
    "CoachState",
    "EQ_DIMENSIONS",
    "EQ_IDS",
    "GRAPH",
    "GRAPH_NAME",
    "LIFELINE_988",
    "MEMORY",
    "MODES",
    "POST_NODES",
    "crisis_payload",
    "eq_heuristic",
    "mock_listening",
    "mock_practice",
    "project",
    "redact_contact_details",
    "result",
    "verify_text",
]
