"""Searchable index of every O*NET 31.0 occupation with complete Work Styles data ("any career").

Built at first use from ``data/raw/onet/occupation_data.csv`` + ``work_styles.csv`` with the SAME
normalization as ``occupations.json`` (data/build_processed.py): for each of the 21 traits, the
percentile rank of the occupation's Work Styles Impact (WI) across all occupations that have all
21 elements with both WI and DR, ``(n_below + 0.5 * n_equal) / N``.

* :func:`search` - token / prefix matching on titles (+ a few common synonyms), core careers first
  on ties. Empty query -> the 8 core careers.
* :func:`get` - one record by O*NET-SOC code; :func:`find_title` - best match for a free title.
* :func:`cosine_rank` - cosine between a 0..1 trait estimate and every occupation (both centred at
  0.5): similarity for one occupation plus its rank among all of them.

Records: ``{onet_soc, title, description, work_styles: {trait: 0..1}, distinctive: [trait ids by DR],
career_id | None, in_fit_classes: bool}``. REAL O*NET data (CC BY 4.0), modified by Foothold.
"""

from __future__ import annotations

import bisect
import csv
import functools
import math
import re
from typing import Any

from foothold import config, data

RAW = config.DATA_DIR / "raw" / "onet"

SYNONYMS: dict[str, list[str]] = {
    "dental": ["dentist", "dental"], "dentist": ["dentist", "dental"], "teeth": ["dental", "dentist"],
    "nurse": ["nurse", "nursing"], "nursing": ["nurse", "nursing"], "cna": ["nursing assistant"],
    "doctor": ["physician", "surgeon"], "medic": ["paramedic", "emergency medical"], "emt": ["emergency medical"],
    "cop": ["police"], "police": ["police", "patrol"], "firefighter": ["firefighter", "fire"],
    "mechanic": ["mechanic", "technician", "repairer"], "car": ["automotive"], "auto": ["automotive"],
    "trucker": ["truck driver"], "truck": ["truck"], "driver": ["driver"], "forklift": ["industrial truck"],
    "programmer": ["programmer", "software developer"], "coder": ["programmer", "software developer"],
    "developer": ["developer"], "software": ["software"], "it": ["computer", "network"], "tech": ["technician"],
    "chef": ["chef", "cook"], "cook": ["cook", "chef"], "baker": ["baker"], "barista": ["barista"],
    "teacher": ["teacher"], "tutor": ["tutor", "teacher"], "lawyer": ["lawyer"], "attorney": ["lawyer"],
    "vet": ["veterinar"], "pharmacy": ["pharmac"], "pharmacist": ["pharmac"], "plumber": ["plumber"],
    "electric": ["electrician", "electrical"], "hvac": ["heating", "air conditioning"], "welding": ["welder"],
    "farm": ["farm", "agricultural"], "farmer": ["farm", "agricultural"], "ag": ["agricultural"],
    "construction": ["construction"], "carpenter": ["carpenter"], "warehouse": ["laborers and freight", "stock"],
    "logistics": ["logistic"], "accountant": ["accountant"], "bookkeeper": ["bookkeeping"],
    "designer": ["designer"], "artist": ["artist"], "therapist": ["therapist"], "counselor": ["counselor"],
    "social": ["social worker"], "hair": ["hairdresser", "barber"], "barber": ["barber"], "robot": ["robotics"],
}

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(str(text or "").lower())


def _read(name: str) -> list[dict[str, str]]:
    with open(RAW / name, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _pct(sorted_vals: list[float], x: float) -> float:
    lo = bisect.bisect_left(sorted_vals, x)
    hi = bisect.bisect_right(sorted_vals, x)
    return (lo + 0.5 * (hi - lo)) / len(sorted_vals)


@functools.lru_cache(maxsize=1)
def _index() -> dict[str, Any]:
    traits = [t for t in data.traits() if isinstance(t, dict) and t.get("id") and t.get("onet_element_id")]
    elem_to_trait = {t["onet_element_id"]: t["id"] for t in traits}
    tids = [t["id"] for t in traits]
    occ = {r["O*NET-SOC Code"]: (r["Title"], r.get("Description") or "") for r in _read("occupation_data.csv")}
    ws: dict[str, dict[str, dict[str, float]]] = {}
    for r in _read("work_styles.csv"):
        tid = elem_to_trait.get(r["Element ID"])
        if not tid:
            continue
        try:
            ws.setdefault(r["O*NET-SOC Code"], {}).setdefault(tid, {})[r["Scale ID"]] = float(r["Data Value"])
        except (TypeError, ValueError):
            continue
    universe = sorted(s for s, d in ws.items() if s in occ and all(t in d and "WI" in d[t] and "DR" in d[t] for t in tids))
    wi_sorted = {t: sorted(ws[s][t]["WI"] for s in universe) for t in tids}
    career_of = {c.get("onet_soc"): c.get("id") for c in data.careers() if isinstance(c, dict) and c.get("onet_soc")}
    classes = {o.get("onet_soc") for o in data.occupation_list() if isinstance(o, dict)}
    records: dict[str, dict[str, Any]] = {}
    for s in universe:
        title, desc = occ[s]
        d = ws[s]
        records[s] = {
            "onet_soc": s, "title": title, "description": desc,
            "work_styles": {t: round(_pct(wi_sorted[t], d[t]["WI"]), 4) for t in tids},
            "distinctive": [t for t in sorted(tids, key=lambda t: -d[t]["DR"]) if d[t]["DR"] > 0],
            "career_id": career_of.get(s), "in_fit_classes": s in classes,
            "_tokens": _tokens(title), "_title_l": title.lower(), "_desc_l": desc.lower(),
        }
    return {"records": records, "trait_ids": tids}


def size() -> int:
    return len(_index()["records"])


def public(rec: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in rec.items() if not k.startswith("_")}


def get(onet_soc: str | None) -> dict[str, Any] | None:
    rec = _index()["records"].get(str(onet_soc or "").strip())
    return public(rec) if rec else None


def _score(rec: dict[str, Any], terms: list[list[str]], raw: str) -> float:
    s = 0.0
    if len(raw) >= 4 and raw in rec["_title_l"]:
        s += 4.0 if rec["_title_l"].startswith(raw) else 2.5
    for alts in terms:
        best = 0.0
        for a in alts:
            if " " in a:
                best = max(best, 2.5 if a in rec["_title_l"] else 0.0)
                continue
            for tok in rec["_tokens"]:
                if tok == a:
                    best = max(best, 3.0)
                elif tok.startswith(a) and len(a) >= 3:
                    best = max(best, 2.0)
            if best < 1.0 and len(a) >= 4 and a in rec["_title_l"]:
                best = max(best, 1.2)
            if best == 0.0 and len(a) >= 4 and re.search(rf"\b{re.escape(a)}", rec["_desc_l"]):
                best = 0.3
        if best == 0.0:
            return 0.0  # every query term must match somewhere
        s += best
    return s


def search(q: str, limit: int = 8) -> list[dict[str, Any]]:
    """[{onet_soc, title, career_id | None}] best first."""
    limit = max(1, min(int(limit or 8), 25))
    recs = _index()["records"]
    toks = [t for t in _tokens(q) if t not in ("a", "an", "the", "of", "and", "job", "jobs", "work", "career")][:6]
    if not toks:
        core = [r for r in recs.values() if r.get("career_id")]
        order = {cid: i for i, cid in enumerate(data.career_ids())}
        core.sort(key=lambda r: order.get(r["career_id"], 99))
        return [{"onet_soc": r["onet_soc"], "title": r["title"], "career_id": r["career_id"]} for r in core[:limit]]
    terms = [[t, *SYNONYMS.get(t, [])] for t in toks]
    raw = " ".join(toks)
    scored = []
    for r in recs.values():
        sc = _score(r, terms, raw)
        if sc > 0:
            scored.append((sc + (1.5 if r.get("career_id") else 0.0), r))
    scored.sort(key=lambda t: (-t[0], len(t[1]["title"]), t[1]["onet_soc"]))
    return [{"onet_soc": r["onet_soc"], "title": r["title"], "career_id": r.get("career_id")} for _, r in scored[:limit]]


def find_title(title: str) -> dict[str, Any] | None:
    hits = search(title, 1)
    return get(hits[0]["onet_soc"]) if hits else None


def _centred_cos(u: list[float], v: list[float]) -> float:
    nu = math.sqrt(sum(x * x for x in u)) or 1e-9
    nv = math.sqrt(sum(x * x for x in v)) or 1e-9
    return sum(a * b for a, b in zip(u, v)) / (nu * nv)


def cosine_rank(traits: dict[str, float], onet_soc: str) -> dict[str, Any] | None:
    """``{similarity, rank, of}``: cosine of (traits - 0.5) vs (work styles - 0.5), and the rank of
    ``onet_soc`` among every indexed occupation (1 = closest)."""
    idx = _index()
    tids = idx["trait_ids"]
    if onet_soc not in idx["records"]:
        return None
    u = [float(traits.get(t, 0.5)) - 0.5 for t in tids]
    sims = {s: _centred_cos(u, [r["work_styles"][t] - 0.5 for t in tids]) for s, r in idx["records"].items()}
    mine = sims[onet_soc]
    rank = 1 + sum(1 for v in sims.values() if v > mine)
    return {"similarity": round(mine, 4), "rank": rank, "of": len(sims)}
