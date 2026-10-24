#!/usr/bin/env python3
"""Build wages.json, programs.json, personas.json and merge wage/outlook into careers.json.

Inputs (read by the research sweep, 2026-10-24):
    data/raw/wages/wages.json            CA EDD OEWS 2026 Q1 (Stockton-Lodi MSA) + EDD long-term projections
    data/raw/programs/programs_raw.json  Program Pathways Mapper reads (Delta College, Modesto JC), fees, SJETI
Outputs:
    data/processed/wages.json, programs.json, personas.json, sources/programs.json
    data/processed/careers.json          ONLY the "wage" and "outlook" fields are replaced

Provenance rules (CONTRACTS section 12): values the research read -> REAL; values computed from read
numbers (DERIVED) -> REAL with a "derived from" note; anything Foothold made up for planning (course
titles inside a program, section times, books, hours per week) -> SAMPLE with a verify URL.
Program-level status is REAL when the program name, URL and unit total were read from the mapper page;
its steps and sections are always SAMPLE schedules (the mapper shows no section times).

Run: $FOOTHOLD_PY data/build_programs.py
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
RETRIEVED = "2026-10-24"
FEE_PER_UNIT = 46  # REAL: https://www.deltacollege.edu/admission-aid/tuition-fees
BOOKS_PER_COURSE = 80  # SAMPLE placeholder (no official books figure read)
OEWS_URL = "https://data.ca.gov/dataset/oews"
PROJ_URL = "https://data.ca.gov/dataset/long-term-occupational-employment-projections"
DELTA = "San Joaquin Delta College"
MJC = "Modesto Junior College"
CAMPUS = {DELTA: "Delta College, Stockton", MJC: "MJC West Campus, Modesto"}

CAREER_SOC = {
    "logistics_lead": "53-1047", "registered_nurse": "29-1141", "diesel_mechanic": "49-3031", "welder": "51-4121",
    "electrician": "47-2111", "software_dev": "15-1252", "farm_ops_manager": "11-9013", "robotics_tech": "17-3024",
}
WAGE_NOTES = {
    "logistics_lead": "O*NET profile is 11-3071 (Transportation, Storage, and Distribution Managers); the local wage "
                      "shown is OEWS 53-1047 (First-Line Supervisors of Transportation and Material Moving Workers), "
                      "the closer match for a warehouse lead role in Stockton-Lodi.",
    "farm_ops_manager": "Small sample: OEWS estimates 100 jobs locally (relative standard error of the mean wage 5.5%). "
                        "OEWS covers wage-and-salary managers only, not self-employed farmers.",
    "robotics_tech": "No Stockton-Lodi row for 17-3024 in EDD OEWS 2026 Q1. Shown: Sacramento-Roseville-Folsom MSA "
                     "(not local; about 40 jobs, RSE 3.2%). California statewide median: $40.31/h, $83,833/yr.",
}


def rd(p: Path):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def wr(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


# ---------------------------------------------------------------- wages
def wage_block(w: dict, note: str | None) -> dict:
    out = {
        "median_hourly": w["hourly"]["median"], "median_annual": round(w["annual"]["median"]),
        "p25_annual": round(w["annual"]["p25"]), "p75_annual": round(w["annual"]["p75"]),
        "p25_hourly": w["hourly"]["p25"], "p75_hourly": w["hourly"]["p75"],
        "area": w["area"], "period": "2026 Q1 (CA EDD OEWS; employment = May 2025 estimate)",
        "soc": w["soc"], "employment": w.get("employment"), "source_id": "edd_oews_2026q1", "status": "REAL",
        "verify_url": OEWS_URL,
    }
    if note:
        out["note"] = note
    return out


def outlook_block(p: dict | None, note: str | None) -> dict | None:
    if not p:
        return None
    out = {
        "growth_pct": p["pct_change"], "annual_openings": p["annual_openings_avg_DERIVED"], "period": p["period"],
        "area": p["area"], "total_openings_10yr": p["total_openings_10yr"], "source_id": "edd_projections",
        "status": "REAL", "verify_url": PROJ_URL,
        "note": "annual_openings derived from EDD: 10-year total openings / 10." + (f" {note}" if note else ""),
    }
    return out


def build_wages() -> tuple[dict, dict]:
    raw = rd(RAW / "wages" / "wages.json")
    occ = {o["soc"]: o for o in raw["occupations"]}
    per_career = {}
    for cid, soc in CAREER_SOC.items():
        o = occ[soc]
        if o.get("wages"):
            wage = wage_block(o["wages"], WAGE_NOTES.get(cid))
        else:
            fb = next(f for f in o["wages_fallbacks"] if "Sacramento" in f["area"])
            wage = wage_block(fb, WAGE_NOTES.get(cid))
            wage["fallback"] = True
        if o.get("projections_local"):
            outlook = outlook_block(o["projections_local"], None)
        else:
            outlook = outlook_block(o["projections_california"],
                                    "No Stockton-Lodi projection for this occupation; California statewide shown.")
        per_career[cid] = {"wage": wage, "outlook": outlook}
    related = {}
    for soc in ("13-1081", "49-3042", "49-3041", "53-7062"):
        o = occ[soc]
        note = None
        if soc == "49-3041":
            note = "Small sample: OEWS estimates 250 jobs locally (RSE 2.8%)."
        related[soc] = {"title": o["title"], "foothold_role": o["foothold_role"],
                        "wage": wage_block(o["wages"], note),
                        "outlook": outlook_block(o.get("projections_local"), None)}
    out = {
        "schema": "foothold.wages.processed.v1", "retrieved": RETRIEVED, "status": "REAL",
        "source": "CA EDD OEWS, 2026 Q1 (Stockton-Lodi MSA); EDD long-term projections 2023-2033 (local) / 2024-2034 (CA)",
        "notes": raw["notes"],
        "all_occupations": wage_block(raw["all_occupations_baseline"], None),
        "warehouse_baseline": {"soc": "53-7062", **related["53-7062"],
                               "note": "Baseline for warehouse pickers facing automation (Dev's starting point)."},
        "careers": per_career,
        "related": related,
    }
    return out, per_career


# ---------------------------------------------------------------- sections + steps
PATTERNS = {
    "day": [{"days": ["Mon", "Wed"], "start": "09:00", "end": "10:50", "modality": "in_person"},
            {"days": ["Tue", "Thu"], "start": "11:00", "end": "12:50", "modality": "in_person"}],
    "evening": [{"days": ["Tue", "Thu"], "start": "18:00", "end": "20:50", "modality": "in_person"},
                {"days": ["Mon", "Wed"], "start": "18:30", "end": "21:20", "modality": "in_person"}],
    "online": [{"days": [], "start": "00:00", "end": "23:59", "modality": "online", "asynchronous": True}],
    "hybrid": [{"days": ["Sat"], "start": "08:00", "end": "12:50", "modality": "hybrid"}],
    "lab_day": [{"days": ["Mon", "Wed"], "start": "07:30", "end": "11:20", "modality": "in_person"}],
    "lab_eve": [{"days": ["Tue", "Thu"], "start": "17:30", "end": "21:20", "modality": "in_person"}],
    "lab_sat": [{"days": ["Sat"], "start": "07:30", "end": "15:20", "modality": "in_person"}],
}
MIXES = {  # 2-4 sections per course
    "academic": ["day", "evening", "online"],
    "academic_day": ["day", "online"],
    "lab": ["lab_day", "lab_eve"],
    "lab_sat": ["lab_day", "lab_sat"],
    "evening_only": ["evening"],
    "day_only": ["day"],
    "online_hybrid": ["online", "hybrid"],
}


def sections(step_id: str, mix: str, provider: str) -> list[dict]:
    pats = []
    for key in MIXES[mix]:
        opts = PATTERNS[key]
        h = int(hashlib.sha1(f"{step_id}:{key}".encode()).hexdigest(), 16)
        pats.append(opts[h % len(opts)])
    if mix == "evening_only":  # tight case: two evening sections, no day or online option
        pats = PATTERNS["evening"]
    out = []
    for i, p in enumerate(pats):
        sec = {"id": f"{step_id}-s{i + 1}", **{k: (list(v) if isinstance(v, list) else v) for k, v in p.items()}}
        if p["modality"] != "online":
            sec["campus"] = CAMPUS.get(provider, provider)
        out.append(sec)
    return out


def course(sid, title, units, provider, mix="academic", prereqs=(), weeks=16, terms=None, note=None, books=True):
    fee = round(units * FEE_PER_UNIT, 2)
    bk = BOOKS_PER_COURSE if books else 0
    st = {
        "id": sid, "title": title, "kind": "course", "units": units,
        "hours_per_week": round(units * 2.0, 1), "weeks": weeks, "cost_usd": round(fee + bk, 2),
        "cost_breakdown": {"enrollment_fee_usd": fee, "enrollment_fee_status": "REAL",
                           "enrollment_fee_note": f"derived: {units} units x ${FEE_PER_UNIT}/unit (Delta College fee page)",
                           "books_usd": bk, "books_status": "SAMPLE"},
        "prereqs": list(prereqs), "sections": sections(sid, mix, provider), "status": "SAMPLE",
        "hours_basis": "SAMPLE: 2 h/week per unit (class + study)",
    }
    if terms:
        st["terms_offered"] = terms
    if note:
        st["note"] = note
    return st


def block(sid, title, hours, weeks, cost=0, prereqs=(), note=None, status="SAMPLE"):
    st = {"id": sid, "title": title, "kind": "block", "hours_per_week": hours, "weeks": weeks, "cost_usd": cost,
          "prereqs": list(prereqs), "sections": [], "status": status}
    if note:
        st["note"] = note
    return st


def job(sid, title, hours, weeks, wage, prereqs=(), note=None, wage_status="REAL", status="SAMPLE"):
    st = {"id": sid, "title": title, "kind": "job", "hours_per_week": hours, "weeks": weeks, "cost_usd": 0,
          "prereqs": list(prereqs), "sections": [], "paid_wage_hourly": wage, "paid_wage_status": wage_status,
          "status": status}
    if note:
        st["note"] = note
    return st


def chain(prefix, provider, titles_units, mix="academic", total=None, terms_map=None, extra_prereqs=None):
    """Courses in term order. Each (title, units, term) step requires the first course of the previous term.
    If total is given, the last course absorbs rounding so units sum to the REAL mapper total."""
    steps, by_term, last_part = [], {}, {}
    if total is not None:
        s = sum(u for _, u, _ in titles_units)
        last_t, last_u, last_term = titles_units[-1]
        titles_units = titles_units[:-1] + [(last_t, round(last_u + (total - s), 1), last_term)]
    for i, (title, units, term) in enumerate(titles_units):
        base = f"{prefix}{i + 1:02d}"
        n = max(1, math.ceil(units / 5)) if units > 5 else 1  # SAMPLE split of big blocks into <= 5-unit parts
        part_units = [round(units / n, 1)] * n
        part_units[-1] = round(units - sum(part_units[:-1]), 1)
        pre = [last_part[by_term[term - 1][0]]] if term - 1 in by_term else []
        if extra_prereqs and base in extra_prereqs:
            pre = [last_part.get(x, x) for x in extra_prereqs[base]]
        m = mix(i, title) if callable(mix) else mix
        prev = None
        for k, pu in enumerate(part_units):
            sid = base if k == 0 else f"{base}{chr(ord('a') + k)}"
            t = title if n == 1 else f"{title} (part {k + 1} of {n})"
            steps.append(course(sid, t, pu, provider, m, pre if k == 0 else [prev],
                                terms=(terms_map or {}).get(base)))
            prev = sid
        last_part[base] = prev
        by_term.setdefault(term, []).append(base)
    return steps


def program(pid, career, route, name, provider, credential, url, status, source_id, steps, **extra):
    p = {"id": pid, "career_id": career, "route_type": route, "name": name, "provider": provider,
         "credential": credential, "url": url, "status": status, "source_id": source_id,
         "schedule_status": "SAMPLE", "schedule_note": "Course titles, sections, times and weekly hours are SAMPLE "
         "planning placeholders; check the college schedule of classes. Unit total and program name are from the "
         "mapper page when status is REAL.", "steps": steps}
    p.update(extra)
    p["total_units"] = round(sum(s.get("units") or 0 for s in steps), 1) or None
    p["total_cost_usd"] = round(sum(s["cost_usd"] for s in steps), 2)
    return p


def build_programs(w: dict) -> list[dict]:
    W = w["careers"]
    R = w["related"]
    progs = []
    trade_mix = lambda i, t: "lab_sat" if i % 3 == 2 else "lab"  # noqa: E731

    # logistics_lead
    progs.append(program(
        "delta_logistics_supervisor_coa", "logistics_lead", "certificate",
        "Logistics and Transportation Supervisor Certificate of Achievement", DELTA, "Certificate of Achievement",
        "https://programmap.deltacollege.edu/program/logistics-and-transportation-supervisor/", "REAL",
        "ccc_program_mappers",
        chain("lts", DELTA, [("Introduction to Logistics and Transportation", 3, 1), ("Warehouse Operations", 3, 1),
                             ("Business Communication", 3, 1), ("Supervision Fundamentals", 3, 1),
                             ("Transportation Management", 3, 2), ("Inventory and Materials Management", 3, 2),
                             ("Logistics Software and Spreadsheets", 3, 2), ("Safety and Compliance (OSHA)", 3, 2)],
              mix=lambda i, t: "evening_only" if "Supervision" in t else "academic", total=24),
        mapper_units="24 units", mapper_terms="2 terms", catalog_year="2025-2026"))
    progs.append(program(
        "delta_business_admin_ast", "logistics_lead", "cc_transfer",
        "Business Administration for Transfer 2.0 Associate in Science for Transfer (toward CSU Stanislaus)", DELTA,
        "Associate in Science for Transfer", "https://programmap.deltacollege.edu/program/business-administration-for-transfer-2-0/",
        "REAL", "ccc_program_mappers",
        chain("bat", DELTA, [("English Composition", 4, 1), ("Financial Accounting", 4, 1), ("GE: Social Science", 3, 1),
                             ("Statistics", 4, 2), ("Managerial Accounting", 4, 2), ("GE: Humanities", 3, 2),
                             ("Microeconomics", 3, 3), ("Business Law", 3, 3), ("Critical Thinking and Writing", 3, 3),
                             ("Macroeconomics", 3, 4), ("Introduction to Business", 3, 4), ("GE: Science with lab", 4, 4),
                             ("GE and electives (remaining units)", 15, 5)], total=60),
        mapper_units="60-64 units", mapper_terms="4 terms", catalog_year="2025-2026",
        transfer_target={"name": "California State University, Stanislaus (Turlock)", "term": "Fall 2026",
                         "tuition_fee_per_semester_usd": 3419.0, "total_per_semester_usd": 4815.0, "status": "REAL",
                         "source_url": "https://www.csustan.edu/tuition-fees/fee-schedules-deadlines#fall-26"}))
    wb = R["53-7062"]["wage"]
    progs.append(program(
        "direct_logistics_lead", "logistics_lead", "direct_to_work",
        "Warehouse associate to lead (on-the-job route)", "Local warehouse employers", "Forklift certification + promotion",
        "https://www.onetonline.org/link/summary/53-1047.00", "SAMPLE", "foothold_program_samples",
        [block("dl01", "Forklift operator certification (employer-provided)", 8, 1, 0,
               note="SAMPLE: often provided by the employer; verify with the employer."),
         job("dl02", "Warehouse associate (hand laborer / material mover)", 40, 52, wb["median_hourly"], ["dl01"],
             note="Wage = Stockton-Lodi median for 53-7062 (CA EDD OEWS 2026 Q1)."),
         course("dl03", "Inventory systems and spreadsheets (free online course)", 0, "Online", "online_hybrid",
                ["dl02"], weeks=8, books=False),
         job("dl04", "Shift lead / first-line supervisor", 40, 52, W["logistics_lead"]["wage"]["p25_hourly"],
             ["dl02", "dl03"], note="Wage = 25th percentile for 53-1047 in Stockton-Lodi (entry-level supervisor).")]))

    # registered_nurse
    rn = [course("rn01", "Intermediate Algebra (prerequisite)", 4, DELTA, "academic"),
          course("rn02", "English Composition", 4, DELTA, "academic"),
          course("rn03", "Human Anatomy (with lab)", 4, DELTA, "lab", ["rn01"],
                 note="Tight case: anatomy before physiology before microbiology."),
          course("rn04", "Human Physiology (with lab)", 4, DELTA, "lab", ["rn03"]),
          course("rn05", "Microbiology (with lab)", 5, DELTA, "lab", ["rn04"], terms=["fall"],
                 note="SAMPLE: modeled as offered once a year (fall only)."),
          course("rn06", "Psychology / Sociology / Communication (GE)", 9, DELTA, "academic"),
          course("rn07", "Nutrition and Lifespan Development", 6, DELTA, "academic_day"),
          course("rn08", "GE and additional courses (remaining units)", 11.5, DELTA, "online_hybrid"),
          block("rn09", "Apply to the Nursing R.N. program (selective admission)", 3, 8, 0,
                ["rn02", "rn05", "rn06"], note="SAMPLE: admission is competitive; see the program page."),
          course("rn10", "Nursing semester 1: Fundamentals", 9, DELTA, "day_only", ["rn09"]),
          course("rn11", "Nursing semester 2: Medical-Surgical I", 9, DELTA, "day_only", ["rn10"]),
          course("rn12", "Nursing semester 3: Maternal/Child and Mental Health", 9, DELTA, "day_only", ["rn11"]),
          course("rn13", "Nursing semester 4: Medical-Surgical II and Leadership", 9.5, DELTA, "day_only", ["rn12"]),
          block("rn14", "NCLEX-RN exam preparation and licensure", 10, 8, 0, ["rn13"])]
    progs.append(program(
        "delta_nursing_rn_as", "registered_nurse", "cc_transfer",
        "Nursing R.N. Associate in Science (pre-nursing prerequisites + major courses)", DELTA,
        "Associate in Science (RN licensure eligible)", "https://programmap.deltacollege.edu/program/nursing-r-n/",
        "REAL", "ccc_program_mappers", rn, mapper_units="47-50 units prerequisites/additional + 36.5 units major",
        mapper_terms="4 terms (major)", catalog_year="2025-2026",
        note="Unit totals from the mapper (47 + 36.5). Route type cc_transfer = community-college degree route; "
             "an RN-to-BSN at a CSU can follow."))
    progs.append(program(
        "delta_nurse_assistant_cert", "registered_nurse", "certificate",
        "Nurse Assistant and Home Health Aide Certificate of Completion (Noncredit)", DELTA,
        "Certificate of Completion (noncredit)", "https://programmap.deltacollege.edu/program/nurse-assistant-and-home-health-aide/",
        "REAL", "ccc_program_mappers",
        [course("na01", "Nurse Assistant theory and clinical (noncredit)", 0, DELTA, "day_only", weeks=12, books=True),
         course("na02", "Home Health Aide (noncredit)", 0, DELTA, "evening_only", ["na01"], weeks=4),
         block("na03", "State nurse assistant certification exam", 4, 2, 0, ["na01"],
               note="SAMPLE: exam fee not verified."),
         job("na04", "Certified nursing assistant (while completing RN prerequisites)", 24, 52, None, ["na03"],
             note="No local OEWS wage read for CNAs; wage unknown (verify).", wage_status="SAMPLE")],
        note="Noncredit certificate: no unit card on the mapper page; no enrollment fee assumed (verify). "
             "A stepping stone toward the RN route."))
    progs[-1]["steps"][-1].pop("paid_wage_hourly")

    # diesel_mechanic
    progs.append(program(
        "delta_diesel_equipment_coa", "diesel_mechanic", "certificate",
        "Diesel Equipment Technician Certificate of Achievement", DELTA, "Certificate of Achievement",
        "https://programmap.deltacollege.edu/program/diesel-equipment-technician/", "REAL", "ccc_program_mappers",
        chain("det", DELTA, [("Shop Safety and Basic Hand Tools", 2, 1), ("Diesel Engine Fundamentals", 5, 1),
                             ("Electrical Systems I", 4, 2), ("Hydraulics I", 4, 2), ("Air Brake Systems", 4, 3),
                             ("Diesel Engine Diagnostics", 5, 3), ("Power Trains and Drive Lines", 5, 4),
                             ("Electrical Systems II", 4, 4), ("Preventive Maintenance and Inspection", 4, 5),
                             ("Fuel Systems and Emissions", 5.5, 5)], mix=trade_mix, total=42.5,
              terms_map={"det06": ["spring"]}),
        mapper_units="42.5 units", mapper_terms="5 terms", catalog_year="2025-2026"))
    progs.append(program(
        "delta_ag_mechanics_coa", "diesel_mechanic", "certificate",
        "Agriculture Mechanics Certificate of Achievement", DELTA, "Certificate of Achievement",
        "https://programmap.deltacollege.edu/program/agriculture-mechanics/", "REAL", "ccc_program_mappers",
        chain("agm", DELTA, [("Agricultural Power and Machinery", 4, 1), ("Ag Welding and Fabrication", 4, 1),
                             ("Small Engines and Equipment Service", 4, 2), ("Hydraulics for Farm Equipment", 4.5, 2)],
              mix=lambda i, t: "lab_sat" if i % 2 else "lab", total=16.5),
        mapper_units="16.5 units", mapper_terms="2 terms", catalog_year="2025-2026",
        note="Farm-equipment mechanic route (OEWS 49-3041; Stockton-Lodi median $25.58/h, small sample)."))
    progs.append(program(
        "mjc_mechanized_ag_coa", "diesel_mechanic", "certificate",
        "Mechanized Agriculture Technician Certificate of Achievement", MJC, "Certificate of Achievement",
        "https://programmap.mjc.edu/program/mechanized-agriculture-technician/", "REAL", "ccc_program_mappers",
        chain("mat", MJC, [("Agricultural Equipment Safety", 2, 1), ("Diesel Power for Agriculture", 5, 1),
                           ("Ag Electrical Systems", 4, 1), ("Ag Hydraulics", 5, 2), ("Precision Ag Technology", 4, 2),
                           ("Ag Power Trains", 5, 3), ("Equipment Service Management", 5, 3)],
              mix=trade_mix, total=30, terms_map={"mat05": ["fall"]}),
        mapper_units="30 units", mapper_terms="3 terms", catalog_year="2026-2027"))
    progs.append(program(
        "delta_cat_dealer_apprenticeship", "diesel_mechanic", "apprenticeship",
        "Caterpillar Dealer Service Technician Apprenticeship Associate in Science", DELTA,
        "Associate in Science (apprenticeship)",
        "https://programmap.deltacollege.edu/program/caterpillar-dealer-service-technician-apprenticeship/", "REAL",
        "ccc_program_mappers",
        [block("cat01", "Apply and get sponsored by a participating dealer", 3, 8, 0,
               note="SAMPLE: dealer sponsorship required; check the program page."),
         ],
        mapper_units="81 units", mapper_terms="5 terms", catalog_year="2025-2026"))
    cat_courses = chain("catc", DELTA, [("Dealer Orientation and Safety", 4, 1), ("Engines I", 8, 1),
                                        ("Electrical I", 8, 2), ("Hydraulics", 8, 2), ("Power Trains", 8, 3),
                                        ("Engines II and Fuel Systems", 8, 3), ("Electronics and Diagnostics", 8, 4),
                                        ("Machine Systems", 8, 4), ("GE courses for the degree", 21, 5)],
                        mix="lab", total=81)
    cat_courses[0]["prereqs"] = ["cat01"]
    cat_courses[1]["prereqs"] = ["cat01"]
    progs[-1]["steps"] += cat_courses + [
        job("cat02", "Paid dealership work rotations (alternating with school terms)", 40, 52, None, ["cat01"],
            note="Paid wage not read; see the program page.", wage_status="SAMPLE")]
    progs[-1]["steps"][-1].pop("paid_wage_hourly")
    progs[-1]["total_units"] = 81
    progs[-1]["total_cost_usd"] = round(sum(s["cost_usd"] for s in progs[-1]["steps"]), 2)
    dw = W["diesel_mechanic"]["wage"]
    progs.append(program(
        "direct_diesel_shop", "diesel_mechanic", "direct_to_work",
        "Shop helper / lube technician to diesel technician (on-the-job route)", "Local truck and equipment shops",
        "ASE entry-level certification (optional)", "https://www.ase.com/", "SAMPLE", "foothold_program_samples",
        [job("dd01", "Shop helper / lube technician", 40, 52, dw["p25_hourly"],
             note="Wage = 25th percentile for 49-3031 in Stockton-Lodi (entry-level reference)."),
         course("dd02", "Air brakes and DOT inspection basics (short course)", 0, "Online", "online_hybrid", ["dd01"],
                weeks=6, books=False),
         block("dd03", "ASE entry-level certification test", 4, 4, 0, ["dd02"],
               note="SAMPLE: test fee not verified."),
         job("dd04", "Diesel technician", 40, 52, dw["median_hourly"], ["dd03"],
             note="Wage = Stockton-Lodi median for 49-3031 (CA EDD OEWS 2026 Q1).")]))

    # welder
    progs.append(program(
        "delta_smaw_coa", "welder", "certificate",
        "Oxy-Fuel Processes and Shielded Metal Arc Welding (SMAW) Certificate of Achievement", DELTA,
        "Certificate of Achievement",
        "https://programmap.deltacollege.edu/program/oxy-fuel-processes-and-shielded-metal-arc-welding-smaw/", "REAL",
        "ccc_program_mappers",
        chain("smw", DELTA, [("Welding Safety and Oxy-Fuel Processes", 4, 1), ("SMAW I", 4, 1),
                             ("Blueprint Reading for Welders", 3, 1), ("SMAW II", 4, 2), ("SMAW Certification Prep", 5, 2)],
              mix=lambda i, t: "evening_only" if "Certification" in t else "lab", total=20),
        mapper_units="20 units", mapper_terms="2 terms", catalog_year="2025-2026"))
    progs.append(program(
        "delta_welding_tech_coa", "welder", "certificate",
        "Welding Technology Certificate of Achievement", DELTA, "Certificate of Achievement",
        "https://programmap.deltacollege.edu/program/welding-technology/", "REAL", "ccc_program_mappers",
        chain("wtc", DELTA, [("Welding Safety and Oxy-Fuel", 4, 1), ("SMAW I", 4, 1), ("Blueprint Reading", 3, 1),
                             ("GMAW and FCAW", 4, 2), ("SMAW II", 4, 2), ("Metallurgy", 3, 2), ("GTAW (TIG) I", 4, 3),
                             ("Fabrication", 4, 3), ("Pipe Welding", 4, 3), ("Welding Certification Prep", 8.5, 3)],
              mix=trade_mix, total=42.5, terms_map={"wtc09": ["spring"]}),
        mapper_units="42.5 units", mapper_terms="3 terms", catalog_year="2025-2026"))
    ww = W["welder"]["wage"]
    progs.append(program(
        "direct_welder_helper", "welder", "direct_to_work",
        "Welder helper to certified welder (on-the-job route)", "Local fabrication shops", "AWS D1.1 structural test",
        "https://www.aws.org/certification/", "SAMPLE", "foothold_program_samples",
        [job("dw01", "Welder helper / fabrication shop", 40, 26, ww["p25_hourly"],
             note="Wage = 25th percentile for 51-4121 in Stockton-Lodi."),
         block("dw02", "Practice for the structural plate test (open lab)", 6, 12, 150, ["dw01"],
               note="SAMPLE cost."),
         block("dw03", "AWS D1.1 structural welding test", 8, 1, 0, ["dw02"], note="SAMPLE: test fee not verified."),
         job("dw04", "Certified welder", 40, 52, ww["median_hourly"], ["dw03"],
             note="Wage = Stockton-Lodi median for 51-4121.")]))

    # electrician
    progs.append(program(
        "delta_electrical_trainee_coa", "electrician", "certificate",
        "Electrical Technology - General Electrician Trainee Certificate of Achievement", DELTA,
        "Certificate of Achievement",
        "https://programmap.deltacollege.edu/program/electrical-technology-general-electrician-trainee/", "REAL",
        "ccc_program_mappers",
        chain("elt", DELTA, [("DC/AC Electrical Theory", 4, 1), ("Electrical Safety and Lockout/Tagout", 3, 1),
                             ("Residential Wiring", 4, 1), ("National Electrical Code I", 3, 2),
                             ("Conduit Bending and Raceways", 4, 2), ("Commercial Wiring", 4, 2),
                             ("Motors and Controls", 4, 3), ("National Electrical Code II", 3, 3),
                             ("Blueprint Reading for Electricians", 3, 3), ("Programmable Logic Controllers", 4, 4),
                             ("Electrical Troubleshooting", 4, 4), ("Code Calculations and Exam Prep", 3, 4)],
              mix=lambda i, t: "evening_only" if "Code" in t else "lab", total=43, terms_map={"elt10": ["spring"]}),
        mapper_units="43 units", mapper_terms="4 terms", catalog_year="2025-2026"))
    progs.append(program(
        "sjeti_inside_wireman", "electrician", "apprenticeship",
        "Electrician-Inside Wireman Apprenticeship (San Joaquin & Calaveras Counties Electrical JATC)",
        "San Joaquin & Calaveras Counties Electrical J.A.T.C. (SJETI)", "Journeyman inside wireman (DAS registered)",
        "https://sjeti.org/", "REAL", "sjeti_apprenticeship",
        [course("sj01", "One semester of college algebra, C or better (entry requirement)", 4, DELTA, "academic",
                note="Entry requirement (REAL): one year of HS algebra or one semester of college algebra, C or better. "
                     "Section times SAMPLE."),
         block("sj02", "Apply, written aptitude test and oral exam", 4, 12, 0, ["sj01"],
               note="REAL: written test, oral exam and drug screen (cost borne by JATC). Timeline SAMPLE.",
               status="REAL"),
         job("sj03", "Year 1 apprentice: paid on-the-job training", 40, 52, 21.35, ["sj02"],
             note="Starting wage $21.35/h read from the DIR/SJETI listing; it rises on the JATC schedule.",
             status="REAL"),
         course("sj04", "Related training classes (about 200 h per year, tuition-free)", 0, "SJETI", "evening_only",
                ["sj02"], weeks=40, books=False,
                note="REAL: ~200 h/year related training, tuition-free. Evening schedule SAMPLE."),
         job("sj05", "Years 2-5 apprentice (wage rises per JATC schedule)", 40, 208, 21.35, ["sj03", "sj04"],
             note="Shown at the starting wage (the only rate read); later steps pay more. Verify at sjeti.org.",
             status="REAL")],
        length_months=60, tuition="tuition-free (per sjeti.org)", min_age=18,
        verify_url="https://www.dir.ca.gov/databases/das/results_aigdetail.asp?varOccId=9810"))
    progs[-1]["steps"][3]["cost_usd"] = 0
    progs[-1]["steps"][3]["cost_breakdown"]["books_usd"] = 0
    progs[-1]["steps"][3]["hours_per_week"] = 5.0
    progs[-1]["total_cost_usd"] = round(sum(s["cost_usd"] for s in progs[-1]["steps"]), 2)

    # software_dev
    progs.append(program(
        "delta_cs_ast", "software_dev", "cc_transfer",
        "Computer Science Associate in Science for Transfer (toward CSU)", DELTA, "Associate in Science for Transfer",
        "https://programmap.deltacollege.edu/program/computer-science-2/", "REAL", "ccc_program_mappers",
        chain("cst", DELTA, [("Precalculus", 4, 1), ("Programming Fundamentals (Python)", 4, 1),
                             ("English Composition", 4, 1), ("Calculus I", 5, 2), ("Data Structures (C++)", 4, 2),
                             ("GE: Humanities", 3, 2), ("Calculus II", 5, 3), ("Discrete Structures", 3, 3),
                             ("Computer Architecture and Assembly", 4, 3), ("Calculus-based Physics I", 5, 4),
                             ("GE: Social Science", 3, 4), ("GE and electives (remaining units)", 18, 5)],
              total=63, terms_map={"cst08": ["fall"], "cst10": ["fall"]},
              extra_prereqs={"cst08": ["cst05"], "cst10": ["cst07"]}),
        mapper_units="63-64 units", mapper_terms="5 terms", catalog_year="2025-2026",
        transfer_target={"name": "California State University, Stanislaus (Turlock)", "term": "Fall 2026",
                         "tuition_fee_per_semester_usd": 3419.0, "total_per_semester_usd": 4815.0, "status": "REAL",
                         "source_url": "https://www.csustan.edu/tuition-fees/fee-schedules-deadlines#fall-26"}))
    progs.append(program(
        "delta_computer_programming_coa", "software_dev", "certificate",
        "Computer Programming Certificate of Achievement", DELTA, "Certificate of Achievement",
        "https://programmap.deltacollege.edu/program/computer-programming/", "REAL", "ccc_program_mappers",
        chain("cpc", DELTA, [("Programming Fundamentals (Python)", 4, 1), ("Web Development I", 3, 1),
                             ("Database Fundamentals (SQL)", 3, 1), ("Data Structures (C++)", 4, 2),
                             ("Object-Oriented Programming (Java)", 4, 2), ("Web Development II", 3, 2),
                             ("Software Testing and Version Control", 3, 3), ("Mobile App Development", 4, 3),
                             ("Systems Analysis and Design", 3, 3), ("Programming Capstone and electives", 13.5, 4)],
              mix=lambda i, t: "online_hybrid" if i % 2 else "academic", total=44.5),
        mapper_units="44.5-48.5 units", mapper_terms="4 terms", catalog_year="2025-2026"))
    sw = W["software_dev"]["wage"]
    progs.append(program(
        "direct_software_portfolio", "software_dev", "direct_to_work",
        "Free online courses + portfolio to junior developer (self-taught route)", "freeCodeCamp and similar free providers",
        "Portfolio (no formal credential)", "https://www.freecodecamp.org/learn/", "SAMPLE", "foothold_program_samples",
        [course("ds01", "Responsive Web Design (free online)", 0, "Online", "online_hybrid", weeks=12, books=False),
         course("ds02", "JavaScript Algorithms and Data Structures (free online)", 0, "Online", "online_hybrid",
                ["ds01"], weeks=16, books=False),
         course("ds03", "Python and SQL basics (free online)", 0, "Online", "online_hybrid", ["ds01"], weeks=12,
                books=False),
         block("ds04", "Build 3 portfolio projects with Git", 8, 12, 0, ["ds02", "ds03"]),
         job("ds05", "Junior developer / IT support", 40, 52, sw["p25_hourly"], ["ds04"],
             note="Wage = 25th percentile for 15-1252 in Stockton-Lodi; junior roles may start lower (verify).")]))
    for st in progs[-1]["steps"]:
        if st["kind"] == "course":
            st["hours_per_week"] = 6.0

    # farm_ops_manager
    progs.append(program(
        "mjc_ag_business_ast", "farm_ops_manager", "cc_transfer",
        "Agriculture Business for Transfer Degree Associate of Science for Transfer (toward CSU Stanislaus / Fresno State)",
        MJC, "Associate of Science for Transfer",
        "https://programmap.mjc.edu/program/agriculture-business-for-transfer-degree/", "REAL", "ccc_program_mappers",
        chain("abt", MJC, [("Introduction to Agriculture Business", 3, 1), ("English Composition", 4, 1),
                           ("Agricultural Economics", 3, 1), ("Agricultural Accounting", 3, 2), ("Statistics", 4, 2),
                           ("Plant Science (with lab)", 4, 2), ("Ag Sales and Communication", 3, 3),
                           ("Agricultural Computer Applications", 3, 3), ("Animal Science", 4, 3),
                           ("Financial Accounting", 4, 4), ("GE and electives (remaining units)", 25, 5)],
              total=60, terms_map={"abt06": ["spring"]}),
        mapper_units="60-62 units", mapper_terms="5 terms", catalog_year="2026-2027"))
    progs.append(program(
        "delta_ag_business_coa", "farm_ops_manager", "certificate",
        "Agriculture Business Certificate of Achievement", DELTA, "Certificate of Achievement",
        "https://programmap.deltacollege.edu/program/agriculture-business/", "REAL", "ccc_program_mappers",
        chain("agb", DELTA, [("Introduction to Agriculture Business", 3, 1), ("Agricultural Economics", 3, 1),
                             ("Soil Science", 4, 1), ("Agricultural Accounting", 3, 2), ("Farm Management", 3, 2),
                             ("Irrigation Principles", 3, 2), ("Pest Management and Pesticide Safety", 3, 3),
                             ("Agricultural Marketing", 3, 3), ("Ag Computer Applications", 3, 3),
                             ("Ag Labor Management", 3, 4), ("Remaining certificate units", 28, 4)],
              mix=lambda i, t: "evening_only" if "Labor" in t else "academic", total=59),
        mapper_units="59-61 units", mapper_terms="4 terms", catalog_year="2025-2026"))
    fw = R["49-3041"]["wage"]
    progs.append(program(
        "direct_farm_crew_lead", "farm_ops_manager", "direct_to_work",
        "Farm crew to crew lead to operations (on-the-job route)", "Local farms and ag operations",
        "Qualified Applicator License (optional)", "https://www.cdpr.ca.gov/", "SAMPLE", "foothold_program_samples",
        [job("df01", "Farm equipment operator / crew member", 40, 52, None,
             note="No local OEWS wage read for farmworkers; wage unknown (verify).", wage_status="SAMPLE"),
         course("df02", "Pesticide safety and QAL exam prep (short course)", 0, "Online", "online_hybrid", ["df01"],
                weeks=8, books=False),
         block("df03", "Qualified Applicator License exam", 4, 2, 0, ["df02"], note="SAMPLE: fee not verified."),
         job("df04", "Crew lead / equipment lead", 45, 104, fw["median_hourly"], ["df03"],
             note="Wage reference = Stockton-Lodi median for 49-3041 (farm equipment mechanics), small sample; "
                  "crew-lead pay not read.", wage_status="REAL")]))
    progs[-1]["steps"][0].pop("paid_wage_hourly")

    # robotics_tech
    progs.append(program(
        "delta_automation_mechatronics_coa", "robotics_tech", "certificate",
        "Automation Technician - Mechatronics Certificate of Achievement", DELTA, "Certificate of Achievement",
        "https://programmap.deltacollege.edu/program/automation-technician-mechatronics/", "REAL",
        "ccc_program_mappers",
        chain("amc", DELTA, [("DC/AC Circuits", 4, 1), ("Industrial Safety and Lockout/Tagout", 2, 1),
                             ("Mechanical Systems and Drives", 4, 1), ("Digital Electronics", 4, 2),
                             ("Programmable Logic Controllers I", 4, 2), ("Sensors and Actuators", 3.5, 2),
                             ("Fluid Power (Hydraulics/Pneumatics)", 4, 3), ("PLC II and HMI", 4, 3),
                             ("Industrial Robotics", 4, 3)],
              mix=lambda i, t: "lab_sat" if i % 3 == 1 else "lab", total=33.5,
              terms_map={"amc09": ["spring"]}),
        mapper_units="33.5 units", mapper_terms="3 terms", catalog_year="2025-2026"))
    progs.append(program(
        "mjc_automation_technician_coa", "robotics_tech", "certificate",
        "Automation Technician Certificate of Achievement", MJC, "Certificate of Achievement",
        "https://programmap.mjc.edu/program/automation-technician/", "REAL", "ccc_program_mappers",
        chain("mjat", MJC, [("Industrial Electricity", 4, 1), ("Motor Controls", 4, 1), ("Industrial Safety", 1.5, 1),
                            ("Programmable Logic Controllers", 4, 2), ("Industrial Robotics and Automation", 5.5, 2)],
              mix="evening_only", total=19, terms_map={"mjat05": ["spring"]}),
        mapper_units="19 units", mapper_terms="2 terms", catalog_year="2026-2027",
        note="Tight case: modeled as evening-only sections (SAMPLE) - fits a day-shift worker; robotics course once a year."))
    rw = W["robotics_tech"]["wage"]
    progs.append(program(
        "direct_maintenance_tech", "robotics_tech", "direct_to_work",
        "Warehouse maintenance helper to automation technician (on-the-job route)", "Local distribution centers",
        "Employer training + PLC short courses", "https://www.onetonline.org/link/summary/17-3024.01", "SAMPLE",
        "foothold_program_samples",
        [job("dr01", "Maintenance helper (distribution center)", 40, 52, wb["p75_hourly"],
             note="Wage reference = 75th percentile for 53-7062 in Stockton-Lodi (experienced warehouse worker)."),
         course("dr02", "PLC and sensors basics (free online)", 0, "Online", "online_hybrid", ["dr01"], weeks=10,
                books=False),
         block("dr03", "Employer robotics/conveyor training", 6, 8, 0, ["dr02"]),
         job("dr04", "Automation / robotics technician", 40, 52, rw["median_hourly"], ["dr03"],
             note="Wage = Sacramento MSA median for 17-3024 (no Stockton-Lodi row; not local).")]))
    progs[-1]["steps"][1]["hours_per_week"] = 4.0
    progs.append(program(
        "engineering_transfer_prep_ucm", "robotics_tech", "cc_transfer",
        "Engineering transfer preparation (math/physics sequence) toward UC Merced Mechanical Engineering", DELTA,
        "Transfer preparation (verify the agreement on ASSIST)", "https://assist.org", "SAMPLE",
        "foothold_program_samples",
        chain("eng", DELTA, [("Precalculus (dual enrollment eligible)", 4, 1), ("Introduction to Engineering", 2, 1),
                             ("Calculus I", 5, 2), ("English Composition", 4, 2), ("Calculus II", 5, 3),
                             ("Physics: Mechanics (calculus-based)", 5, 3), ("Engineering Graphics / CAD", 3, 3),
                             ("Multivariable Calculus", 5, 4), ("Physics: Electricity and Magnetism", 5, 4),
                             ("Statics", 3, 5), ("Circuit Analysis", 4, 5), ("GE and electives (remaining units)", 14, 6)],
              total=60, terms_map={"eng06": ["fall"], "eng10": ["spring"]},
              extra_prereqs={"eng06": ["eng03"], "eng09": ["eng06", "eng05"], "eng10": ["eng06"],
                             "eng11": ["eng09"]}),
        note="SAMPLE route: course list is a generic UC engineering prep sequence, not read from a mapper page. "
             "Physics: Mechanics modeled as offered once a year (fall only). Check ASSIST for the real agreement.",
        transfer_target={"name": "University of California, Merced", "basis": "2027-28 new CA resident, per year",
                         "uc_tuition_and_ssf_usd": 16278, "status": "REAL",
                         "source_url": "https://admission.universityofcalifornia.edu/tuition-financial-aid/tuition-cost-of-attendance/",
                         "campus_total_per_semester_usd": 8462, "campus_total_status": "SAMPLE",
                         "campus_total_url": "https://studentbilling.ucmerced.edu/tuition-fees/tuition"}))
    return progs


# ---------------------------------------------------------------- personas
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def personas() -> dict:
    return {
        "fictional": True, "status": "FICTIONAL", "source_id": "foothold_personas",
        "note": "All personas are fictional composites; no real person is described.",
        "personas": [
            {
                "id": "maya", "kind": "learner", "fictional": True, "name": "Maya", "display_name": "Maya Ortiz",
                "age": 16, "grade": "11th grade (junior)", "region": "Stockton (San Joaquin County)",
                "interests": ["engineering", "robotics club", "math"], "target_career": "robotics_tech",
                "interests_careers": ["robotics_tech", "software_dev", "electrician"],
                "goal": "Transfer to a UC (UC Merced engineering) without debt; start college classes while in high school.",
                "story": "Robotics club builder who wants a UC but worries about cost and getting to campus by bus.",
                "current_credits": 0, "hours_per_week": 10, "budget_usd": 4000, "commute_minutes": 35,
                "commute_mode": "bus", "dependents": 0,
                "available_windows": [{"days": WEEKDAYS, "start": "15:30", "end": "21:00"},
                                      {"days": ["Sat"], "start": "09:00", "end": "17:00"}],
                "constraints": {"hours_per_week": 10, "budget_usd": 4000, "commute_minutes": 35, "dependents": 0,
                                "current_credits": 0, "no_class_before": "15:30", "days_off": ["Sun"]},
                "preferred_routes": ["cc_transfer", "certificate"],
                "budget_note": "Whole-plan budget (fictional): family can set aside about $100 a month. Fee waivers such as the California College Promise Grant may lower costs (not verified here).",
            },
            {
                "id": "dev", "kind": "learner", "fictional": True, "name": "Dev", "display_name": "Dev Sandhu",
                "age": 41, "region": "Lathrop (San Joaquin County)", "current_job": "Warehouse order picker",
                "current_job_soc": "53-7062", "current_wage_hourly": 23.25,
                "current_wage_note": "Stockton-Lodi median for 53-7062 (CA EDD OEWS 2026 Q1), used as Dev's fictional wage.",
                "interests": ["fixing equipment", "automation", "steady pay"], "target_career": "robotics_tech",
                "interests_careers": ["robotics_tech", "diesel_mechanic", "logistics_lead"],
                "goal": "Move from picking to maintaining the robots that are replacing picking jobs, without losing income.",
                "story": "Twelve years in warehouses; the new automated picking system made him curious, not scared.",
                "current_credits": 0, "hours_per_week": 10, "work_hours_per_week": 45, "budget_usd": 2000,
                "commute_minutes": 20, "commute_mode": "car", "dependents": 2,
                "available_windows": [{"days": WEEKDAYS, "start": "18:00", "end": "22:00"},
                                      {"days": ["Sat", "Sun"], "start": "08:00", "end": "16:00"}],
                "constraints": {"hours_per_week": 10, "budget_usd": 2000, "commute_minutes": 20, "dependents": 2,
                                "current_credits": 0, "no_class_before": "17:30"},
                "preferred_routes": ["certificate", "direct_to_work"],
            },
            {
                "id": "luis", "kind": "learner", "fictional": True, "name": "Luis", "display_name": "Luis Navarro",
                "age": 18, "grade": "12th grade (senior)", "region": "Manteca (San Joaquin County)",
                "family_business": "family farm-equipment repair shop (about 15 h/week)",
                "interests": ["diesel engines", "farm equipment", "welding"], "target_career": "diesel_mechanic",
                "interests_careers": ["diesel_mechanic", "welder", "farm_ops_manager"],
                "goal": "Get certified on diesel and farm equipment so he can grow the family shop.",
                "story": "Has rebuilt tractor hydraulics with his uncle since he was 13; wants papers to prove it.",
                "current_credits": 0, "hours_per_week": 14, "work_hours_per_week": 15, "budget_usd": 1500,
                "commute_minutes": 25, "commute_mode": "car", "dependents": 0,
                "available_windows": [{"days": WEEKDAYS, "start": "07:30", "end": "14:30"},
                                      {"days": ["Tue", "Thu"], "start": "17:00", "end": "21:30"}],
                "constraints": {"hours_per_week": 14, "budget_usd": 1500, "commute_minutes": 25, "dependents": 0,
                                "current_credits": 0, "days_off": ["Sat"]},
                "preferred_routes": ["certificate", "apprenticeship"],
            },
            {
                "id": "tri_valley_freight", "kind": "employer", "fictional": True, "name": "Tri-Valley Freight",
                "display_name": "Tri-Valley Freight", "org": "Tri-Valley Freight",
                "industry": "Third-party logistics and distribution (fictional)", "region": "Stockton / Lathrop",
                "size": "about 600 employees (fictional)",
                "hiring_for": ["robotics_tech", "logistics_lead", "diesel_mechanic"],
                "story": "A fictional regional distribution company automating two warehouses and short on technicians.",
                "contact_email": "hiring@trivalleyfreight.example.org",
            },
        ],
    }


# ---------------------------------------------------------------- sources
def sources() -> list[dict]:
    return [
        {"id": "edd_oews_2026q1", "title": "CA EDD Occupational Employment and Wage Statistics (OEWS), 2026 Q1 wages, Stockton-Lodi MSA (Sacramento MSA / California for 17-3024)",
         "url": OEWS_URL, "publisher": "California Employment Development Department (BLS-EDD cooperative program)",
         "license": "Public data (data.ca.gov); facts only", "retrieved": RETRIEVED, "status": "REAL",
         "notes": ["Wages updated by EDD to 2026 Q1 with the Employment Cost Index; employment = May 2025 OEWS estimates.",
                   "Used because BLS hosts blocked scripted requests on 2026-10-24.",
                   "logistics_lead uses SOC 53-1047 (O*NET profile 11-3071); 17-3024 has no Stockton-Lodi row."],
         "used_by": ["wages.json", "careers.json", "programs.json"], "producer": "data/build_programs.py"},
        {"id": "edd_projections", "title": "CA EDD Long-Term Occupational Employment Projections (Stockton-Lodi 2023-2033; California 2024-2034)",
         "url": PROJ_URL, "publisher": "California Employment Development Department",
         "license": "Public data (data.ca.gov); facts only", "retrieved": RETRIEVED, "status": "REAL",
         "notes": "annual_openings = 10-year total openings / 10 (derived by Foothold).",
         "used_by": ["wages.json", "careers.json"], "producer": "data/build_programs.py"},
        {"id": "sjeti_apprenticeship", "title": "San Joaquin & Calaveras Counties Electrical JATC (SJETI) Inside Wireman apprenticeship; DIR DAS listing",
         "url": "https://sjeti.org/", "publisher": "SJETI; California Department of Industrial Relations",
         "license": "Public web pages; facts only", "retrieved": RETRIEVED, "status": "REAL",
         "notes": "5 years, ~200 h/year related training, tuition-free, starting wage $21.35/h, entry algebra requirement. DIR: https://www.dir.ca.gov/databases/das/results_aigdetail.asp?varOccId=9810",
         "used_by": ["programs.json"], "producer": "data/build_programs.py"},
        {"id": "csu_campus_fees", "title": "CSU campus fee pages, Fall 2026 (Stanislaus, Fresno, Sacramento)",
         "url": "https://www.csustan.edu/tuition-fees/fee-schedules-deadlines#fall-26", "publisher": "California State University campuses",
         "license": "Public web pages; facts only", "retrieved": RETRIEVED, "status": "REAL",
         "used_by": ["programs.json"], "producer": "data/build_programs.py"},
        {"id": "uc_tuition", "title": "University of California tuition and cost of attendance (2027-28 new CA resident estimate)",
         "url": "https://admission.universityofcalifornia.edu/tuition-financial-aid/tuition-cost-of-attendance/",
         "publisher": "University of California", "license": "Public web page; facts only", "retrieved": RETRIEVED,
         "status": "REAL", "notes": "UC Merced campus-specific fees ($8,462/semester) are SAMPLE: the campus page blocked our fetch.",
         "used_by": ["programs.json"], "producer": "data/build_programs.py"},
        {"id": "foothold_program_samples", "title": "Foothold sample program schedules (course titles, sections, times, weekly hours, books, on-the-job routes)",
         "url": "data/build_programs.py", "publisher": "Foothold", "license": "Foothold-made planning placeholders",
         "retrieved": None, "status": "SAMPLE",
         "notes": ["Section times and course splits are placeholders for the planner; verify with each college's schedule of classes.",
                   "Books = $80 per course (SAMPLE). Hours per week = 2 x units (SAMPLE); courses over 5 units are split into parts.",
                   "Enrollment fees = units x $46 (REAL, Delta College fee page)."],
         "used_by": ["programs.json"], "producer": "data/build_programs.py"},
        {"id": "foothold_personas", "title": "Foothold demo personas (Maya, Dev, Luis, Tri-Valley Freight)",
         "url": "data/build_programs.py", "publisher": "Foothold", "license": "Fictional", "retrieved": None,
         "status": "FICTIONAL", "used_by": ["personas.json"], "producer": "data/build_programs.py"},
    ]


def main() -> int:
    wages, per_career = build_wages()
    wr(OUT / "wages.json", wages)
    careers = rd(OUT / "careers.json")
    for c in careers:
        pc = per_career.get(c["id"])
        if pc:
            c["wage"], c["outlook"] = pc["wage"], pc["outlook"]
    wr(OUT / "careers.json", careers)
    progs = build_programs(wages)
    wr(OUT / "programs.json", progs)
    wr(OUT / "personas.json", personas())
    wr(OUT / "sources" / "programs.json", sources())
    n_steps = sum(len(p["steps"]) for p in progs)
    st = {}
    for p in progs:
        st[p["status"]] = st.get(p["status"], 0) + 1
    print(f"wages: {len(per_career)} careers + {len(wages['related'])} related SOCs")
    print(f"programs: {len(progs)} ({st}), {n_steps} steps")
    print("personas: 4; sources/programs.json:", len(sources()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
