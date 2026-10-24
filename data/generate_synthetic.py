#!/usr/bin/env python3
"""Generate Foothold's SYNTHETIC / FICTIONAL population (seeded, deterministic).

Outputs (data/processed/synthetic/, every file has top-level "fictional": true):
    learners.json     ~2000 synthetic learners for the graph recommender
    employers.json    fictional Central Valley employers (incl. Tri-Valley Freight); no real company names
    talent_pool.json  ~150 opted-in talent cards (blind + hidden fields, synthetic fairness group)
    circles.json      support circles with supportive, realistic posts by pseudonymous handles
and data/processed/sources/synthetic.json.

Archetypes (each has career weights, an hours budget, and a prior-skill set):
    hs_student        high-school juniors/seniors exploring; few prior skills; mostly cc_transfer interest
    career_changer    adults 30-55 leaving jobs exposed to automation (warehouse, retail); prior ops skills
    trades_youth      18-24, hands-on, family or part-time work in shops/fields; trades interest
    returning_adult   adults returning to school after a gap; caregiving constraints; nursing/IT interest
    ag_worker         farm and packing-house workers moving toward equipment or management roles
    it_curious        self-taught tinkerers aiming at software or automation

Learnable structure (what the recommender can find): each learner prefers a career; completed courses are
drawn mostly from courses that teach that career's skills; skills = union of completed-course skills plus
archetype prior skills (with dropout); placed_job is a jobs.json role whose required skills the learner
mostly covers (coverage >= 0.6, with probability rising with coverage), else null. ~15% are cold-start
learners (no completed courses, 0-2 skills, never placed). Nothing here describes a real person.

Run: $FOOTHOLD_PY data/generate_synthetic.py [--seed 7]
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "data" / "processed"
OUT = P / "synthetic"

REGIONS = {  # region -> synthetic group mix (A, B, C); a region proxy the fairness audit can test for
    "Stockton": (0.30, 0.45, 0.25), "Lodi": (0.50, 0.30, 0.20), "Manteca": (0.40, 0.35, 0.25),
    "Tracy": (0.45, 0.30, 0.25), "Lathrop": (0.30, 0.40, 0.30), "Modesto": (0.35, 0.40, 0.25),
    "Turlock": (0.40, 0.35, 0.25), "Merced": (0.25, 0.45, 0.30),
}
ARCHETYPES = {
    "hs_student": {"share": 0.24, "careers": {"software_dev": 3, "robotics_tech": 3, "registered_nurse": 3,
                                                "electrician": 2, "welder": 1, "diesel_mechanic": 1},
                   "prior": ["mathematics", "reading_comprehension", "active_learning"], "n_courses": (0, 3)},
    "career_changer": {"share": 0.22, "careers": {"robotics_tech": 4, "logistics_lead": 4, "diesel_mechanic": 2,
                                                    "electrician": 2, "software_dev": 1},
                       "prior": ["forklift_safety", "shipping_receiving", "osha_safety", "coordination",
                                 "time_management", "inventory_systems"], "n_courses": (1, 4)},
    "trades_youth": {"share": 0.18, "careers": {"diesel_mechanic": 4, "welder": 4, "electrician": 3,
                                                  "farm_ops_manager": 1},
                     "prior": ["repairing", "equipment_maintenance", "troubleshooting", "osha_safety"],
                     "n_courses": (1, 4)},
    "returning_adult": {"share": 0.14, "careers": {"registered_nurse": 4, "software_dev": 2, "logistics_lead": 2},
                        "prior": ["service_orientation", "social_perceptiveness", "time_management", "speaking"],
                        "n_courses": (1, 3)},
    "ag_worker": {"share": 0.12, "careers": {"farm_ops_manager": 4, "diesel_mechanic": 3, "welder": 1},
                  "prior": ["ag_equipment_operation", "pesticide_safety", "irrigation_management", "osha_safety"],
                  "n_courses": (1, 3)},
    "it_curious": {"share": 0.10, "careers": {"software_dev": 5, "robotics_tech": 3},
                   "prior": ["programming", "python", "complex_problem_solving"], "n_courses": (2, 5)},
}
COLD_START = 0.15

EMPLOYERS = [  # all fictional names; checked against no real company list beyond avoiding known brands
    ("tri_valley_freight", "Tri-Valley Freight", "Third-party logistics and distribution", "Lathrop",
     ["robotics_tech", "logistics_lead", "diesel_mechanic"], "about 600"),
    ("delta_breeze_logistics", "Delta Breeze Logistics", "Warehousing", "Stockton", ["logistics_lead", "robotics_tech"], "about 300"),
    ("oakline_ag_equipment", "Oakline Ag Equipment", "Farm equipment dealer and service", "Lodi",
     ["diesel_mechanic", "welder"], "about 80"),
    ("sunfield_orchards", "Sunfield Orchards Co-op", "Almond and walnut growing (co-op)", "Turlock",
     ["farm_ops_manager", "diesel_mechanic"], "about 150"),
    ("valley_crest_health", "Valley Crest Community Health", "Community hospital", "Modesto",
     ["registered_nurse"], "about 1,200"),
    ("riverbend_clinic_network", "Riverbend Clinic Network", "Outpatient clinics", "Stockton", ["registered_nurse"], "about 400"),
    ("granite_line_fabrication", "Granite Line Fabrication", "Structural steel fabrication", "Manteca",
     ["welder"], "about 60"),
    ("canal_street_electric", "Canal Street Electric", "Electrical contractor", "Tracy", ["electrician"], "about 90"),
    ("heron_point_software", "Heron Point Software", "Agtech software", "Merced", ["software_dev"], "about 40"),
    ("bluegate_packing", "Bluegate Packing", "Fruit packing and cold storage", "Lodi",
     ["robotics_tech", "logistics_lead", "electrician"], "about 500"),
    ("ironwood_truck_service", "Ironwood Truck Service", "Heavy truck repair", "Stockton", ["diesel_mechanic"], "about 45"),
    ("mesa_verde_dairy", "Mesa Verde Dairy Partners", "Dairy operations", "Merced", ["farm_ops_manager", "diesel_mechanic"], "about 70"),
    ("northgate_automation", "Northgate Automation Services", "Conveyor and robotics integrator", "Tracy",
     ["robotics_tech", "electrician", "software_dev"], "about 120"),
    ("cottonwood_care_homes", "Cottonwood Care Homes", "Skilled nursing", "Turlock", ["registered_nurse"], "about 200"),
    ("sierra_vista_transit_parts", "Sierra Vista Transit Parts", "Parts distribution", "Modesto",
     ["logistics_lead"], "about 110"),
    ("tule_fog_data", "Tule Fog Data Co.", "Small IT services firm", "Stockton", ["software_dev"], "about 25"),
]

FIRST = ["Ana", "Marco", "Jasmine", "Tomas", "Priya", "Kevin", "Lupe", "Andre", "Mai", "Jorge", "Hannah", "Rafael",
         "Simran", "Darnell", "Elena", "Bao", "Carmen", "Isaiah", "Nadia", "Victor", "Rosa", "Arjun", "Leah", "Mateo"]
LAST = ["Alvarez", "Nguyen", "Brooks", "Gill", "Ramos", "Chen", "Herrera", "Patel", "Lopez", "Kaur", "Reyes",
        "Thompson", "Vang", "Morales", "Singh", "Delgado", "Lee", "Castillo", "Moua", "Ortega"]


def rd(name):
    with open(P / name, encoding="utf-8") as fh:
        obj = json.load(fh)
    if isinstance(obj, dict):
        obj = next(v for v in obj.values() if isinstance(v, list))
    return obj


def wr(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def wchoice(rng, weights: dict):
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys])[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--n", type=int, default=2000)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    skills = {s["id"] for s in rd("skills.json")}
    courses = rd("courses.json")
    jobs = rd("jobs.json")
    careers = {c["id"]: c for c in rd("careers.json")}
    programs = rd("programs.json")

    # courses relevant to each career = courses teaching at least one of the career's skills
    rel = {cid: [c for c in courses if set(c["skills"]) & set(car["skills"])] for cid, car in careers.items()}
    jobs_by_career: dict[str, list] = {}
    for j in jobs:
        jobs_by_career.setdefault(j["career_id"], []).append(j)

    learners = []
    arche_keys = list(ARCHETYPES)
    shares = [ARCHETYPES[a]["share"] for a in arche_keys]
    region_keys = list(REGIONS)
    for i in range(args.n):
        a = rng.choices(arche_keys, weights=shares)[0]
        spec = ARCHETYPES[a]
        region = rng.choice(region_keys)
        career = wchoice(rng, spec["careers"])
        cold = rng.random() < COLD_START
        if cold:
            completed = []
            sk = set(rng.sample([s for s in spec["prior"] if s in skills], k=min(rng.randint(0, 2), len(spec["prior"]))))
        else:
            n = rng.randint(*spec["n_courses"])
            pool = rel[career] if rel[career] else courses
            chosen = []
            for _ in range(n):
                c = rng.choice(pool) if rng.random() < 0.8 else rng.choice(courses)  # 20% exploration noise
                if c["id"] not in chosen:
                    chosen.append(c["id"])
            completed = chosen
            sk = {s for s in spec["prior"] if s in skills and rng.random() < 0.7}
            for cid in completed:
                c = next(x for x in courses if x["id"] == cid)
                sk |= {s for s in c["skills"] if s in skills and rng.random() < 0.85}
        placed = None
        if not cold:
            best, best_cov = None, 0.0
            for j in jobs_by_career.get(career, []):
                req = set(j.get("required_skills") or [])
                cov = len(req & sk) / len(req) if req else 0.0
                if cov > best_cov:
                    best, best_cov = j, cov
            if best and best_cov >= 0.6 and rng.random() < 0.35 + 0.6 * best_cov:
                placed = best["id"]
        learners.append({
            "id": f"syn_l{i + 1:04d}", "archetype": a, "region": region, "target_career": career,
            "skills": sorted(sk), "completed_courses": completed, "placed_job": placed, "cold_start": cold,
            "fictional": True,
        })

    employers = []
    for eid, name, industry, region, hiring, size in EMPLOYERS:
        employers.append({"id": eid, "name": name, "industry": industry, "region": region,
                          "hiring_careers": hiring, "size": size + " employees (fictional)",
                          "contact_email": f"hiring@{eid.replace('_', '')}.example.org", "fictional": True})

    # talent pool
    prog_by_career: dict[str, list] = {}
    for p in programs:
        prog_by_career.setdefault(p["career_id"], []).append(p)
    bands = ["low", "mid", "high"]
    avail = ["evenings and weekends", "weekdays", "part-time (20 h/week)", "full-time after certificate",
             "summer internship", "immediately, full-time"]

    def band(rng, bias=0.0):
        r = rng.random() + bias
        return "high" if r > 0.72 else "mid" if r > 0.3 else "low"

    def group_for(region):
        return rng.choices(["A", "B", "C"], weights=REGIONS[region])[0]

    cards = []
    persona_cards = [
        ("maya", "Maya Ortiz", "Stockton", "robotics_tech", "engineering_transfer_prep_ucm", 5,
         ["mathematics", "programming", "robot_programming", "sensors_actuators", "complex_problem_solving"],
         {"safety": "high", "output": "mid", "team_trust": "high"}, "after school and Saturdays (about 10 h/week)"),
        ("dev", "Dev Sandhu", "Lathrop", "robotics_tech", "mjc_automation_technician_coa", 20,
         ["forklift_safety", "shipping_receiving", "inventory_systems", "osha_safety", "lockout_tagout",
          "equipment_maintenance", "troubleshooting"],
         {"safety": "high", "output": "high", "team_trust": "mid"}, "evenings and weekends"),
        ("luis", "Luis Navarro", "Manteca", "diesel_mechanic", "delta_ag_mechanics_coa", 10,
         ["diesel_diagnostics", "hydraulics", "repairing", "equipment_maintenance", "mig_welding", "troubleshooting"],
         {"safety": "mid", "output": "high", "team_trust": "high"}, "weekdays after 2:30 pm; summers full-time"),
    ]
    for k, (pid, name, region, career, prog, pct, sk, sb, av) in enumerate(persona_cards):
        initials = "".join(w[0] for w in name.split())
        cards.append({
            "id": f"cand_{pid}", "candidate_id": f"cand_{pid}", "persona_id": pid, "opted_in": True,
            "blind": {"candidate_id": f"cand_{pid}", "target_career": career, "demonstrated_skills": sk,
                      "sim_bands": sb, "pathway_progress": {"program": prog, "percent": pct},
                      "availability": av, "region": f"{region} area"},
            "hidden": {"name": name, "photo_initials": initials, "exact_location": f"{region}, CA (fictional address)",
                       "contact_email": f"{name.lower().replace(' ', '.')}@example.com",
                       "phone": f"555-01{10 + k:02d}"},
            "group": ["A", "B", "C"][k], "fictional": True,
        })
    target_n = 150
    i = 0
    while len(cards) < target_n:
        i += 1
        region = rng.choice(region_keys)
        career = rng.choice(list(careers))
        csk = careers[career]["skills"]
        sk = sorted(set(rng.sample(csk, k=rng.randint(2, 6))) |
                    set(rng.sample(sorted(skills), k=rng.randint(0, 2))))
        progs = prog_by_career.get(career) or []
        prog = rng.choice(progs)["id"] if progs else None
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        g = group_for(region)
        # skill-driven bands; group does NOT enter (fairness audit checks downstream models for proxies)
        bias = (len(sk) - 4) * 0.05
        cards.append({
            "id": f"cand_{i:04d}", "candidate_id": f"cand_{i:04d}", "persona_id": None, "opted_in": True,
            "blind": {"candidate_id": f"cand_{i:04d}", "target_career": career, "demonstrated_skills": sk,
                      "sim_bands": {"safety": band(rng, bias), "output": band(rng, bias), "team_trust": band(rng)},
                      "pathway_progress": {"program": prog, "percent": rng.choice([0, 10, 20, 35, 50, 65, 80, 100])},
                      "availability": rng.choice(avail), "region": f"{region} area"},
            "hidden": {"name": name, "photo_initials": name.split()[0][0] + name.split()[1][0],
                       "exact_location": f"{region}, CA (fictional address)",
                       "contact_email": f"{name.lower().replace(' ', '.')}.{i}@example.com",
                       "phone": f"555-{rng.randint(200, 999):03d}-{rng.randint(1000, 9999):04d}"},
            "group": g, "fictional": True,
        })

    circles = {
        "fictional": True, "status": "FICTIONAL",
        "note": "Fictional communities and pseudonymous posts written by Foothold; no real people.",
        "circles": [
            {"id": "students", "name": "Students figuring it out", "description": "High schoolers and first-year college students comparing paths.",
             "fictional": True, "posts": [
                ("robot_rookie", "Signed up for my first dual-enrollment class at Delta. Kind of nervous about being the youngest in the room."),
                ("mathlete_209", "You'll be fine. I did precalc there junior year; the professor cared more that you showed up than how old you were."),
                ("busline_reader", "Tip for anyone taking the bus: I do my reading on the ride. 35 minutes each way adds up."),
                ("quiet_coder", "Does anyone else feel behind because they didn't start coding at 10? Started at 16 and it's going okay."),
                ("mathlete_209", "Totally normal. Most people in my CS class started in high school or later."),
                ("future_rn_kay", "Anatomy lab is hard but the study group on Thursdays is saving me."),
                ("robot_rookie", "Update: survived week one. The counselor helped me map which classes transfer. ASSIST is confusing but worth it."),
                ("first_gen_frankie", "First in my family doing college stuff. Asking questions in office hours felt weird at first, now it's my favorite part."),
            ]},
            {"id": "career_changers", "name": "Career changers", "description": "Adults switching fields, often while working full-time.",
             "fictional": True, "posts": [
                ("night_shift_nate", "Warehouse brought in the new picking robots. Instead of panicking I asked the tech what training he had."),
                ("forklift_to_plc", "Started an evening PLC class at 41. My kids quiz me on ladder logic now, it's hilarious."),
                ("steady_hands_mo", "Hardest part for me is the schedule. Two kids, 45 hours a week. I take one class at a time and that's okay."),
                ("night_shift_nate", "One class at a time still gets you there. Took me three semesters for my first certificate."),
                ("second_act_sue", "Went back for prereqs at 38 for nursing. The younger students ask me for help with time management."),
                ("forklift_to_plc", "Anyone know if employers count sim results or just certificates? Asking before I spend money."),
                ("steady_hands_mo", "Some do both. Mine cared a lot about the safety record I already had."),
                ("second_act_sue", "Reminder to rest. We're doing two jobs: working and learning."),
            ]},
            {"id": "trades", "name": "Trades crew", "description": "Diesel, welding, electrical and ag mechanics folks.",
             "fictional": True, "posts": [
                ("tractor_tuner", "Rebuilt a hydraulic pump with my uncle this weekend. Want the certificate so customers trust the shop."),
                ("arc_and_spark", "SMAW cert test is next month. Practicing verticals every night after work."),
                ("wire_nut_wren", "Got into the apprenticeship interview round. The algebra requirement was the scary part, glad I did it."),
                ("tractor_tuner", "Congrats! What did they ask in the oral interview?"),
                ("wire_nut_wren", "Mostly why I wanted the trade and how I handle safety. Be honest and specific."),
                ("diesel_dani", "Air brakes class was way more math than I expected. Worth it though."),
                ("arc_and_spark", "Shoutout to the open lab hours. Free practice time makes a huge difference."),
                ("diesel_dani", "Remember to ask about tool programs. Some shops help with tool costs."),
            ]},
            {"id": "caregivers", "name": "Parents and caregivers", "description": "Learning while caring for kids or family.",
             "fictional": True, "posts": [
                ("mom_of_three_ty", "Online sections are the only reason I can take classes. Studying after bedtime."),
                ("papa_bear_ben", "Found a Saturday hybrid class so my partner covers mornings. Small wins."),
                ("grandma_learns", "Taking care of my mom and taking a spreadsheet course. Slow but steady."),
                ("mom_of_three_ty", "Some days I only get 20 minutes in. Counting those as progress now."),
                ("papa_bear_ben", "The campus has a childcare center, ask about it. I didn't know for a whole semester."),
                ("care_and_code", "Feeling guilty about time away from family. Anyone else?"),
                ("grandma_learns", "Yes. My kids told me they're proud of me. That helped."),
                ("care_and_code", "Thanks all. Signing up for one class next term instead of two."),
            ]},
        ],
    }
    for c in circles["circles"]:
        c["posts"] = [{"id": f"{c['id']}_p{j + 1}", "handle": h, "text": t, "fictional": True}
                      for j, (h, t) in enumerate(c["posts"])]

    meta = {"fictional": True, "status": "SYNTHETIC", "source_id": "foothold_synthetic", "seed": args.seed}
    wr(OUT / "learners.json", {**meta, "archetypes": {k: {kk: vv for kk, vv in v.items() if kk != "share"} | {"share": v["share"]} for k, v in ARCHETYPES.items()},
                               "cold_start_rate": COLD_START, "learners": learners})
    wr(OUT / "employers.json", {**meta, "status": "FICTIONAL", "source_id": "foothold_fictional_employers",
                                "employers": employers})
    wr(OUT / "talent_pool.json", {**meta, "note": "group is a synthetic label for the fairness audit only: never a "
                                  "model feature, never displayed on cards.", "candidates": cards})
    wr(OUT / "circles.json", {**circles, "source_id": "foothold_fictional_circles"})
    wr(P / "sources" / "synthetic.json", [
        {"id": "foothold_synthetic", "title": "Foothold synthetic learner population and talent pool (seeded)",
         "url": "data/generate_synthetic.py", "publisher": "Foothold", "license": "Synthetic; generated by Foothold",
         "retrieved": None, "status": "SYNTHETIC", "notes": f"seed={args.seed}; archetypes documented in the script.",
         "used_by": ["synthetic/learners.json", "synthetic/talent_pool.json"], "producer": "data/generate_synthetic.py"},
        {"id": "foothold_fictional_employers", "title": "Foothold fictional employers (incl. Tri-Valley Freight)",
         "url": "data/generate_synthetic.py", "publisher": "Foothold", "license": "Fictional", "retrieved": None,
         "status": "FICTIONAL", "used_by": ["synthetic/employers.json"], "producer": "data/generate_synthetic.py"},
        {"id": "foothold_fictional_circles", "title": "Foothold fictional support circles and posts",
         "url": "data/generate_synthetic.py", "publisher": "Foothold", "license": "Fictional", "retrieved": None,
         "status": "FICTIONAL", "used_by": ["synthetic/circles.json"], "producer": "data/generate_synthetic.py"},
    ])
    placed = sum(1 for x in learners if x["placed_job"])
    cold = sum(1 for x in learners if x["cold_start"])
    print(f"learners={len(learners)} placed={placed} cold_start={cold} employers={len(employers)} "
          f"talent_cards={len(cards)} circles={len(circles['circles'])} posts={sum(len(c['posts']) for c in circles['circles'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
