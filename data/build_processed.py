#!/usr/bin/env python3
"""Foothold data backbone: O*NET 31.0 raw files + Foothold editorial tables -> data/processed/*.json.

Run from anywhere (paths are resolved from this file):
    $FOOTHOLD_PY data/build_processed.py                    # offline, deterministic rebuild
    $FOOTHOLD_PY data/build_processed.py --verify-courses   # re-check course pages online, then rebuild
Then:
    $FOOTHOLD_PY data/build_sources.py                      # merge sources/*.json -> sources.json + SOURCES.md
    $FOOTHOLD_PY data/validate.py                           # check every processed file

Writes (this script owns these files):
    data/processed/traits.json        21 O*NET 31.0 Work Styles, CONTRACTS section 4 order and ids
    data/processed/occupations.json   8 careers + 34 related O*NET occupations, raw WI/DR + 0..1 percentiles
    data/processed/careers.json       career backbone; wage/outlook (and any extra keys) written by other
                                      scripts are preserved on rebuild
    data/processed/skills.json        35 O*NET 31.0 skills + Foothold job-specific skills
    data/processed/courses.json       free / low-cost learning resources, REAL or SAMPLE per item
    data/processed/jobs.json          generic job nodes (Foothold taxonomy, SAMPLE)
    data/processed/sources/onet.json  source records for everything above
    data/schemas/*.schema.json        JSON Schemas (event schema enumerates trait + coworker ids)
Evidence log for course page checks: data/raw/courses/course_checks.json (written by --verify-courses).

Honesty rules applied here:
  * O*NET values are copied or transformed with a documented formula (status REAL, source onet_31_0).
  * A course is REAL only if its exact page was fetched and matched on the check date AND its cost is
    known (free, or derived from a REAL per-unit fee). Otherwise it is SAMPLE and links to the
    provider's homepage unless the exact page itself was verified.
  * Hours are Foothold estimates (hours_status SAMPLE) unless the provider states them.
  * Job nodes and the skill taxonomy are Foothold editorial work (SAMPLE). Coworkers are FICTIONAL.
Stdlib only.
"""

from __future__ import annotations

import argparse
import bisect
import collections
import concurrent.futures as cf
import csv
import datetime as dt
import html
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_ONET = DATA / "raw" / "onet"
RAW_PROGRAMS = DATA / "raw" / "programs" / "programs_raw.json"
PROCESSED = DATA / "processed"
SOURCES_DIR = PROCESSED / "sources"
SCHEMAS = DATA / "schemas"
COURSE_CHECKS = DATA / "raw" / "courses" / "course_checks.json"

# --------------------------------------------------------------------------------------------
# Shared vocabularies (CONTRACTS.md section 4)
# --------------------------------------------------------------------------------------------
STATUSES = ["REAL", "SAMPLE", "SYNTHETIC", "FICTIONAL"]
ROUTE_TYPES = ["cc_transfer", "certificate", "apprenticeship", "direct_to_work"]
MOODS = ["calm", "tense", "upbeat", "tired", "skeptical"]
LEVELS = ["entry", "mid", "senior"]
SIM_STATS = ["safety", "output", "team_trust", "stress"]
COURSE_KINDS = ["course", "book", "guide", "tool", "program", "certification"]
CAREER_IDS = [
    "logistics_lead", "registered_nurse", "diesel_mechanic", "welder",
    "electrician", "software_dev", "farm_ops_manager", "robotics_tech",
]
TRAIT_IDS = [
    "innovation", "achievement_orientation", "intellectual_curiosity", "tolerance_for_ambiguity",
    "initiative", "adaptability", "self_confidence", "perseverance", "leadership_orientation",
    "humility", "sincerity", "empathy", "cooperation", "optimism", "social_orientation",
    "cautiousness", "attention_to_detail", "dependability", "integrity", "stress_tolerance",
    "self_control",
]
SOC_PATTERN = r"^\d{2}-\d{4}\.\d{2}$"
ID_PATTERN = r"^[a-z][a-z0-9_]*$"
ONET_ONLINE = "https://www.onetonline.org/link/summary/{soc}"
RIASEC = ["realistic", "investigative", "artistic", "social", "enterprising", "conventional"]
SKILL_SOURCE_ONET = "O*NET 31.0"
SKILL_SOURCE_FOOTHOLD = "Foothold taxonomy"
# Inline credit for text copied verbatim from the O*NET 31.0 content model (full credit line with the
# modification note: sources.json id onet_31_0 / data/SOURCES.md).
ONET_CREDIT = "From the O*NET 31.0 Database by USDOL/ETA, used under CC BY 4.0."

# O*NET skill group element -> (category slug, kind)
ONET_SKILL_GROUPS = {
    "2.A.1": ("foundational", "essential"),
    "2.A.2": ("ways_of_working", "essential"),
    "2.B.1": ("social", "transferable"),
    "2.B.2": ("problem_solving", "transferable"),
    "2.B.3": ("technical", "transferable"),
    "2.B.4": ("systems", "transferable"),
    "2.B.5": ("resource_management", "transferable"),
}

# Career -> related-occupation group (Foothold editorial grouping, matches SELECTION.json groups)
CAREER_GROUP = {
    "logistics_lead": "logistics",
    "registered_nurse": "health",
    "diesel_mechanic": "trades",
    "welder": "trades",
    "electrician": "trades",
    "software_dev": "tech",
    "farm_ops_manager": "agriculture_food",
    "robotics_tech": "automation_manufacturing",
}

# --------------------------------------------------------------------------------------------
# Foothold job-specific skills (descriptions are Foothold's own words)
# --------------------------------------------------------------------------------------------
FOOTHOLD_SKILLS = [
    ("forklift_safety", "Forklift and warehouse safety", "logistics",
     "Operating a forklift or pallet jack safely: pre-shift checks, stable loads, and watching for people on the floor."),
    ("inventory_systems", "Inventory systems", "logistics",
     "Using a warehouse management or inventory system to receive, count, locate, and reconcile stock."),
    ("shipping_receiving", "Shipping and receiving", "logistics",
     "Checking freight against paperwork, scheduling dock doors, and recording damage or shortages."),
    ("patient_assessment", "Patient assessment", "healthcare",
     "Taking vital signs, asking focused questions, and noticing when a patient's condition changes."),
    ("medication_safety", "Medication safety", "healthcare",
     "Preparing and giving medications with the right checks, and documenting every dose."),
    ("infection_control", "Infection control", "healthcare",
     "Hand hygiene, protective equipment, and isolation steps that stop infections from spreading."),
    ("bls_cpr", "CPR and Basic Life Support", "healthcare",
     "Recognizing cardiac arrest and giving effective CPR with an AED until help takes over."),
    ("ehr_charting", "Health record charting", "healthcare",
     "Recording care accurately and on time in an electronic health record."),
    ("diesel_diagnostics", "Diesel diagnostics", "mechanical",
     "Using scan tools, service information, and tests to find faults in diesel engines, fuel, and emissions systems."),
    ("hydraulics", "Hydraulics", "mechanical",
     "How pumps, valves, cylinders, and hoses move heavy equipment, and how to test and repair them safely."),
    ("air_brakes", "Air brake systems", "mechanical",
     "Inspecting, adjusting, and repairing the air brake systems on trucks, buses, and trailers."),
    ("mig_welding", "MIG welding (GMAW)", "welding",
     "Setting up and running gas metal arc welds: wire feed, shielding gas, travel speed, and joint prep."),
    ("tig_welding", "TIG welding (GTAW)", "welding",
     "Precise gas tungsten arc welds on steel, stainless steel, and aluminum."),
    ("stick_welding", "Stick welding (SMAW)", "welding",
     "Shielded metal arc welding in flat, horizontal, vertical, and overhead positions."),
    ("blueprint_reading", "Blueprint reading", "trades_core",
     "Reading drawings, dimensions, tolerances, and weld or electrical symbols to build to spec."),
    ("nec_code_basics", "NEC code basics", "electrical",
     "Finding and applying National Electrical Code rules for wiring methods, grounding, and overcurrent protection."),
    ("conduit_bending", "Conduit bending", "electrical",
     "Measuring and bending conduit for offsets, saddles, and 90-degree bends that fit the run."),
    ("electrical_theory", "Electrical theory", "electrical",
     "Voltage, current, resistance, Ohm's law, and AC/DC circuits, plus safe meter use."),
    ("python", "Python", "software",
     "Writing, running, and debugging Python programs and scripts."),
    ("git", "Git and version control", "software",
     "Tracking changes with commits and branches, and collaborating through pull requests."),
    ("sql", "SQL and databases", "software",
     "Designing tables and writing queries to store, find, and update data."),
    ("web_fundamentals", "HTML, CSS, and JavaScript", "software",
     "Building accessible web pages and adding interactivity in the browser."),
    ("software_testing", "Software testing and debugging", "software",
     "Writing tests, reproducing bugs, and checking that fixes work."),
    ("irrigation_management", "Irrigation management", "agriculture",
     "Scheduling and maintaining irrigation using soil moisture, weather, and crop water-use data."),
    ("ag_equipment_operation", "Ag equipment operation", "agriculture",
     "Safely setting up and operating tractors, harvesters, sprayers, and implements."),
    ("pesticide_safety", "Pesticide safety", "agriculture",
     "Handling, applying, and recording pesticides according to the label and California rules, with the right protective equipment."),
    ("plc_basics", "PLC basics", "automation",
     "Reading and editing ladder logic, tracing inputs and outputs, and troubleshooting a programmable logic controller."),
    ("sensors_actuators", "Sensors and actuators", "automation",
     "How sensors, motors, valves, and pneumatic cylinders connect to and are driven by a control system."),
    ("robot_programming", "Industrial robot programming", "automation",
     "Jogging a robot arm, teaching positions, and running programs inside safety limits."),
    ("lockout_tagout", "Lockout/tagout", "safety",
     "Shutting off, locking, and verifying zero energy before servicing machines."),
    ("osha_safety", "Workplace safety basics", "safety",
     "Spotting common job hazards and knowing worker rights and protections, at the level of an OSHA 10-hour course."),
    ("spreadsheets", "Spreadsheets", "digital",
     "Building and reading spreadsheets for schedules, counts, and budgets."),
]

# --------------------------------------------------------------------------------------------
# Careers: Foothold editorial fields. People are FICTIONAL.
# --------------------------------------------------------------------------------------------
def _cw(cid, name, pronouns, role, style, mood):
    return {"id": cid, "name": name, "pronouns": pronouns, "role": role, "style": style,
            "base_mood": mood, "fictional": True}


CAREERS_META = {
    "logistics_lead": {
        "summary": ("Leads a shift or an area of a warehouse or distribution center. You plan the day's inbound "
                    "and outbound work, keep people and forklifts moving safely, and sort out problems when "
                    "trucks, counts, or systems don't match. Floor experience as an associate or forklift "
                    "operator is one way in."),
        "path_types": ["certificate", "direct_to_work", "cc_transfer"],
        "foothold_skills": ["forklift_safety", "inventory_systems", "shipping_receiving", "spreadsheets", "osha_safety"],
        "coworkers": [
            _cw("rosa_delgado", "Rosa Delgado", "she/her", "Inbound dock supervisor",
                "Direct and fast; trusts people who flag problems early.", "tense"),
            _cw("tou_vang", "Tou Vang", "he/him", "Forklift operator, night shift",
                "Quiet and safety-first; goes silent when he feels rushed.", "tired"),
            _cw("darnell_hayes", "Darnell Hayes", "he/him", "Inventory control clerk",
                "Jokes a lot, but catches every count mismatch.", "upbeat"),
        ],
    },
    "registered_nurse": {
        "summary": ("Cares for patients in hospitals, clinics, and home health. You assess how patients are doing, "
                    "give medications and treatments safely, teach patients and families, and coordinate with "
                    "doctors and the rest of the care team. Becoming an RN takes an approved nursing program and "
                    "a passing score on the NCLEX-RN licensing exam."),
        "path_types": ["cc_transfer", "certificate"],
        "foothold_skills": ["patient_assessment", "medication_safety", "infection_control", "bls_cpr", "ehr_charting"],
        "coworkers": [
            _cw("grace_villanueva", "Grace Villanueva", "she/her", "Charge nurse",
                "Calm under pressure; expects clear, complete handoffs.", "calm"),
            _cw("harpreet_sandhu", "Harpreet Sandhu", "he/him", "Hospitalist physician",
                "Brisk on rounds; listens closely when you bring vitals and trends.", "skeptical"),
            _cw("luz_herrera", "Luz Herrera", "she/her", "Certified nursing assistant",
                "Warm with patients and stretched thin; notices who pitches in.", "tired"),
        ],
    },
    "diesel_mechanic": {
        "summary": ("Inspects, diagnoses, and repairs diesel trucks, buses, and heavy equipment, including engines, "
                    "air brakes, hydraulics, and electronic controls. The work mixes hands-on repair with computer "
                    "diagnostics, and getting it right matters because these machines carry heavy loads on public "
                    "roads and job sites."),
        "path_types": ["certificate", "apprenticeship", "direct_to_work"],
        "foothold_skills": ["diesel_diagnostics", "hydraulics", "air_brakes", "lockout_tagout", "osha_safety"],
        "coworkers": [
            _cw("manny_soares", "Manny Soares", "he/him", "Shop foreman",
                "Old-school; explains once and hates comebacks.", "skeptical"),
            _cw("pao_xiong", "Pao Xiong", "he/him", "Senior diesel technician",
                "Patient teacher who loves a tricky electrical fault.", "calm"),
            _cw("brenda_ochoa", "Brenda Ochoa", "she/her", "Service writer",
                "Juggles impatient fleet customers; wants honest time estimates.", "tense"),
        ],
    },
    "welder": {
        "summary": ("Joins and cuts metal for farm equipment, structures, and repairs using MIG, TIG, and stick "
                    "processes. You read prints, set up the machine, and check your own work. Skills are usually "
                    "proven with a hands-on weld test."),
        "path_types": ["certificate", "direct_to_work"],
        "foothold_skills": ["mig_welding", "tig_welding", "stick_welding", "blueprint_reading", "osha_safety"],
        "coworkers": [
            _cw("ernesto_ruiz", "Ernesto Ruiz", "he/him", "Lead welder and fitter",
                "Perfectionist about fit-up; quiet praise for a clean bead.", "calm"),
            _cw("kayla_brooks", "Kayla Brooks", "she/her", "Welding apprentice",
                "Eager and full of questions; sometimes rushes the prep.", "upbeat"),
            _cw("arman_petrosyan", "Arman Petrosyan", "he/him", "Quality inspector",
                "Measures everything and trusts paperwork over promises.", "skeptical"),
        ],
    },
    "electrician": {
        "summary": ("Installs, maintains, and troubleshoots wiring, panels, lighting, and controls in homes, "
                    "businesses, and industrial sites, following the National Electrical Code. In California, "
                    "electricians usually train through a state-approved apprenticeship, or register as an "
                    "electrician trainee while enrolled in an approved school, and then pass a state "
                    "certification exam."),
        "path_types": ["apprenticeship", "certificate"],
        "foothold_skills": ["electrical_theory", "nec_code_basics", "conduit_bending", "blueprint_reading", "lockout_tagout"],
        "coworkers": [
            _cw("dale_nakamura", "Dale Nakamura", "he/him", "Foreman, journey-level electrician",
                "Methodical; zero tolerance for skipping lockout.", "calm"),
            _cw("yesenia_cruz", "Yesenia Cruz", "she/her", "Second-year apprentice",
                "Fast learner and competitive; nervous about the code exam.", "tense"),
            _cw("ninos_youkhana", "Ninos Youkhana", "he/him", "General contractor superintendent",
                "Schedule-driven; short on sleep and patience before inspections.", "tired"),
        ],
    },
    "software_dev": {
        "summary": ("Designs, writes, tests, and maintains software, from web and mobile apps to the systems behind "
                    "farms, clinics, and warehouses. Day to day you break problems into small pieces, write code "
                    "with a team, review each other's work, and fix bugs."),
        "path_types": ["cc_transfer", "certificate", "direct_to_work"],
        "foothold_skills": ["python", "git", "sql", "web_fundamentals", "software_testing"],
        "coworkers": [
            _cw("priya_raman", "Priya Raman", "she/her", "Tech lead",
                "Kind but exacting in code review; always asks how you tested it.", "calm"),
            _cw("marcus_bell", "Marcus Bell", "he/him", "Product manager",
                "Optimistic about deadlines; needs ideas turned into clear tickets.", "upbeat"),
            _cw("sokha_chhim", "Sokha Chhim", "she/her", "QA engineer",
                "Finds the edge case nobody considered; dry sense of humor.", "skeptical"),
        ],
    },
    "farm_ops_manager": {
        "summary": ("Plans and runs day-to-day farm operations: planting and harvest schedules, irrigation, "
                    "equipment, crews, budgets, and food-safety and pesticide rules. It is part fieldwork and part "
                    "business, and decisions depend on weather, water, and markets."),
        "path_types": ["cc_transfer", "certificate", "direct_to_work"],
        "foothold_skills": ["irrigation_management", "ag_equipment_operation", "pesticide_safety", "spreadsheets", "osha_safety"],
        "coworkers": [
            _cw("lupe_mendoza", "Lupe Mendoza", "she/her", "Field crew supervisor",
                "Knows every row and every worker; protective of her crew.", "tired"),
            _cw("dirk_visser", "Dirk Visser", "he/him", "Farm owner, third generation",
                "Proud of the land; wary of new tech until it pays off.", "skeptical"),
            _cw("navdeep_kaur", "Navdeep Kaur", "she/her", "Irrigation and pest scout",
                "Data-driven; shows up with soil-moisture charts.", "upbeat"),
        ],
    },
    "robotics_tech": {
        "summary": ("Keeps automated production lines running by installing, programming, and troubleshooting "
                    "robots, PLCs, sensors, and conveyors in food processing, packaging, and manufacturing plants. "
                    "Much of the job is figuring out why a machine stopped and fixing it safely and quickly."),
        "path_types": ["certificate", "direct_to_work"],
        "foothold_skills": ["plc_basics", "sensors_actuators", "robot_programming", "electrical_theory", "lockout_tagout"],
        "coworkers": [
            _cw("alejandro_ibarra", "Alejandro Ibarra", "he/him", "Maintenance supervisor",
                "Wants the line running; values root-cause fixes over quick resets.", "tense"),
            _cw("mai_thao", "Mai Thao", "she/her", "Controls technician",
                "Precise; documents every change to the PLC program.", "calm"),
            _cw("trevor_hall", "Trevor Hall", "he/him", "Production line lead",
                "Friendly but impatient during downtime; counts cases per minute.", "upbeat"),
        ],
    },
}

# --------------------------------------------------------------------------------------------
# Job nodes (Foothold taxonomy; titles generic; closest O*NET occupation for verification)
# (id, title, career_id, level, onet_soc, required_skills, leads_to)
# --------------------------------------------------------------------------------------------
JOBS = [
    # logistics_lead
    ("warehouse_associate", "Warehouse Associate", "logistics_lead", "entry", "53-7062.00",
     ["osha_safety", "coordination", "monitoring", "time_management"],
     ["forklift_operator", "inventory_control_specialist"]),
    ("forklift_operator", "Forklift Operator", "logistics_lead", "entry", "53-7051.00",
     ["forklift_safety", "osha_safety", "operation_and_control", "operations_monitoring"],
     ["warehouse_shift_lead"]),
    ("inventory_control_specialist", "Inventory Control Specialist", "logistics_lead", "entry", "43-5071.00",
     ["inventory_systems", "spreadsheets", "quality_control_analysis", "mathematics"],
     ["warehouse_shift_lead", "logistics_coordinator"]),
    ("warehouse_shift_lead", "Warehouse Shift Lead", "logistics_lead", "mid", "53-1042.00",
     ["management_of_personnel_resources", "coordination", "instructing", "forklift_safety", "inventory_systems"],
     ["distribution_operations_manager"]),
    ("logistics_coordinator", "Logistics Coordinator", "logistics_lead", "mid", "13-1081.00",
     ["shipping_receiving", "spreadsheets", "coordination", "complex_problem_solving", "writing"],
     ["distribution_operations_manager"]),
    ("distribution_operations_manager", "Distribution Operations Manager", "logistics_lead", "senior", "11-3071.00",
     ["management_of_personnel_resources", "management_of_financial_resources", "management_of_material_resources",
      "judgment_and_decision_making", "negotiation", "systems_evaluation"],
     []),
    # registered_nurse
    ("certified_nursing_assistant", "Certified Nursing Assistant", "registered_nurse", "entry", "31-1131.00",
     ["infection_control", "bls_cpr", "service_orientation", "social_perceptiveness", "active_listening"],
     ["licensed_vocational_nurse", "registered_nurse_med_surg"]),
    ("medical_assistant", "Medical Assistant", "registered_nurse", "entry", "31-9092.00",
     ["ehr_charting", "infection_control", "patient_assessment", "service_orientation", "speaking"],
     ["licensed_vocational_nurse"]),
    ("licensed_vocational_nurse", "Licensed Vocational Nurse", "registered_nurse", "mid", "29-2061.00",
     ["medication_safety", "patient_assessment", "infection_control", "ehr_charting", "monitoring"],
     ["registered_nurse_med_surg"]),
    ("registered_nurse_med_surg", "Registered Nurse (Medical-Surgical)", "registered_nurse", "mid", "29-1141.00",
     ["patient_assessment", "medication_safety", "ehr_charting", "critical_thinking", "coordination",
      "judgment_and_decision_making"],
     ["charge_nurse"]),
    ("charge_nurse", "Charge Nurse", "registered_nurse", "senior", "29-1141.00",
     ["management_of_personnel_resources", "coordination", "judgment_and_decision_making", "instructing",
      "time_management", "patient_assessment"],
     []),
    # diesel_mechanic
    ("lube_pm_technician", "Lube and Preventive Maintenance Technician", "diesel_mechanic", "entry", "49-3031.00",
     ["equipment_maintenance", "osha_safety", "operations_monitoring", "reading_comprehension"],
     ["diesel_technician_trainee"]),
    ("diesel_technician_trainee", "Diesel Technician Trainee", "diesel_mechanic", "entry", "49-3031.00",
     ["equipment_maintenance", "repairing", "air_brakes", "hydraulics", "lockout_tagout"],
     ["diesel_technician", "heavy_equipment_mechanic", "farm_equipment_technician"]),
    ("diesel_technician", "Diesel Technician", "diesel_mechanic", "mid", "49-3031.00",
     ["diesel_diagnostics", "troubleshooting", "repairing", "air_brakes", "hydraulics"],
     ["diesel_shop_foreman"]),
    ("heavy_equipment_mechanic", "Heavy Equipment Mechanic", "diesel_mechanic", "mid", "49-3042.00",
     ["hydraulics", "diesel_diagnostics", "troubleshooting", "repairing", "equipment_maintenance"],
     ["diesel_shop_foreman"]),
    ("farm_equipment_technician", "Farm Equipment Service Technician", "diesel_mechanic", "mid", "49-3041.00",
     ["hydraulics", "ag_equipment_operation", "troubleshooting", "repairing", "diesel_diagnostics"],
     ["diesel_shop_foreman"]),
    ("diesel_shop_foreman", "Diesel Shop Foreman", "diesel_mechanic", "senior", "49-1011.00",
     ["management_of_personnel_resources", "diesel_diagnostics", "instructing", "quality_control_analysis",
      "time_management"],
     []),
    # welder
    ("welder_helper", "Welder Helper", "welder", "entry", "51-9198.00",
     ["osha_safety", "equipment_maintenance", "monitoring", "mathematics"],
     ["production_welder"]),
    ("production_welder", "Production Welder", "welder", "entry", "51-4121.00",
     ["mig_welding", "blueprint_reading", "quality_control_analysis", "osha_safety"],
     ["structural_welder", "fabricator_fitter", "tig_welder"]),
    ("structural_welder", "Structural Welder", "welder", "mid", "51-4121.00",
     ["stick_welding", "mig_welding", "blueprint_reading", "quality_control_analysis", "mathematics"],
     ["weld_inspector"]),
    ("fabricator_fitter", "Metal Fabricator and Fitter", "welder", "mid", "51-2041.00",
     ["blueprint_reading", "mig_welding", "mathematics", "equipment_selection", "operation_and_control"],
     ["weld_inspector"]),
    ("tig_welder", "TIG Welder (Precision and Stainless)", "welder", "mid", "51-4121.00",
     ["tig_welding", "blueprint_reading", "quality_control_analysis", "monitoring"],
     ["weld_inspector"]),
    ("weld_inspector", "Weld Quality Inspector", "welder", "senior", "51-9061.00",
     ["quality_control_analysis", "blueprint_reading", "writing", "instructing", "monitoring"],
     []),
    # electrician
    ("electrical_helper", "Electrical Helper", "electrician", "entry", "47-3013.00",
     ["osha_safety", "lockout_tagout", "conduit_bending", "coordination"],
     ["electrician_trainee"]),
    ("solar_pv_installer", "Solar PV Installer", "electrician", "entry", "47-2231.00",
     ["electrical_theory", "installation", "osha_safety", "nec_code_basics"],
     ["electrician_trainee"]),
    ("electrician_trainee", "Electrician Trainee (Apprentice)", "electrician", "entry", "47-2111.00",
     ["electrical_theory", "nec_code_basics", "conduit_bending", "blueprint_reading", "lockout_tagout", "mathematics"],
     ["journey_electrician", "industrial_maintenance_electrician"]),
    ("journey_electrician", "Journey-Level Electrician", "electrician", "mid", "47-2111.00",
     ["nec_code_basics", "installation", "troubleshooting", "blueprint_reading", "electrical_theory"],
     ["electrical_foreman"]),
    ("industrial_maintenance_electrician", "Industrial Maintenance Electrician", "electrician", "mid", "49-9071.00",
     ["troubleshooting", "plc_basics", "electrical_theory", "lockout_tagout", "repairing"],
     ["electrical_foreman", "controls_lead"]),
    ("electrical_foreman", "Electrical Foreman", "electrician", "senior", "47-1011.00",
     ["management_of_personnel_resources", "nec_code_basics", "coordination", "judgment_and_decision_making",
      "blueprint_reading"],
     []),
    # software_dev
    ("it_support_technician", "IT Support Technician", "software_dev", "entry", "15-1232.00",
     ["troubleshooting", "service_orientation", "active_listening", "installation", "writing"],
     ["junior_web_developer", "qa_test_analyst"]),
    ("junior_web_developer", "Junior Web Developer", "software_dev", "entry", "15-1254.00",
     ["web_fundamentals", "git", "programming", "software_testing"],
     ["software_developer"]),
    ("qa_test_analyst", "QA Test Analyst", "software_dev", "entry", "15-1253.00",
     ["software_testing", "quality_control_analysis", "sql", "writing", "git"],
     ["software_developer"]),
    ("software_developer", "Software Developer", "software_dev", "mid", "15-1252.00",
     ["python", "git", "sql", "software_testing", "programming", "complex_problem_solving"],
     ["senior_software_engineer"]),
    ("senior_software_engineer", "Senior Software Engineer", "software_dev", "senior", "15-1252.00",
     ["systems_analysis", "technology_design", "programming", "instructing", "judgment_and_decision_making"],
     []),
    # farm_ops_manager
    ("farmworker_crop", "Farmworker (Crops and Orchards)", "farm_ops_manager", "entry", "45-2092.00",
     ["osha_safety", "pesticide_safety", "coordination", "monitoring"],
     ["ag_equipment_operator", "field_crew_supervisor"]),
    ("ag_equipment_operator", "Agricultural Equipment Operator", "farm_ops_manager", "entry", "45-2091.00",
     ["ag_equipment_operation", "equipment_maintenance", "operation_and_control", "osha_safety"],
     ["field_crew_supervisor", "farm_equipment_technician"]),
    ("precision_ag_technician", "Precision Ag and Irrigation Technician", "farm_ops_manager", "mid", "19-4012.01",
     ["irrigation_management", "sensors_actuators", "spreadsheets", "systems_analysis", "science"],
     ["farm_operations_manager"]),
    ("field_crew_supervisor", "Field Crew Supervisor", "farm_ops_manager", "mid", "45-1011.00",
     ["management_of_personnel_resources", "coordination", "pesticide_safety", "osha_safety", "speaking",
      "instructing"],
     ["farm_operations_manager"]),
    ("farm_operations_manager", "Farm Operations Manager", "farm_ops_manager", "senior", "11-9013.00",
     ["management_of_financial_resources", "management_of_personnel_resources", "irrigation_management",
      "judgment_and_decision_making", "spreadsheets", "systems_evaluation"],
     []),
    # robotics_tech
    ("automated_line_operator", "Automated Line Operator", "robotics_tech", "entry", "51-9111.00",
     ["operations_monitoring", "operation_and_control", "lockout_tagout", "quality_control_analysis"],
     ["maintenance_technician"]),
    ("maintenance_technician", "Maintenance Technician I", "robotics_tech", "entry", "49-9071.00",
     ["equipment_maintenance", "repairing", "lockout_tagout", "electrical_theory", "osha_safety"],
     ["industrial_machinery_mechanic", "automation_technician"]),
    ("industrial_machinery_mechanic", "Industrial Machinery Mechanic", "robotics_tech", "mid", "49-9041.00",
     ["troubleshooting", "repairing", "hydraulics", "sensors_actuators", "blueprint_reading"],
     ["controls_lead"]),
    ("automation_technician", "Automation Technician", "robotics_tech", "mid", "17-3024.00",
     ["plc_basics", "sensors_actuators", "electrical_theory", "troubleshooting", "installation"],
     ["robotics_technician", "controls_lead"]),
    ("robotics_technician", "Robotics Technician", "robotics_tech", "mid", "17-3024.01",
     ["robot_programming", "plc_basics", "sensors_actuators", "troubleshooting", "programming"],
     ["controls_lead"]),
    ("controls_lead", "Controls and Automation Lead", "robotics_tech", "senior", "17-3024.01",
     ["plc_basics", "robot_programming", "systems_analysis", "instructing", "management_of_personnel_resources"],
     []),
]

# --------------------------------------------------------------------------------------------
# Course catalog. Each entry: what we claim + how to verify it.
#   check: {"title": [...]} substrings expected in <title>; {"body": [...]} in page text;
#          {"fcc": superBlock} freeCodeCamp page-data; {"openstax": (slug, exact title)} OpenStax CMS API.
#   cost: 0 (free) | None (unknown, price varies) | ("units", n) community college program
#   hours: Foothold estimate unless hours_real (provider-stated) is given.
#   Skill mappings are Foothold's editorial judgment.
# --------------------------------------------------------------------------------------------
KHAN = "https://www.khanacademy.org/"
OCW = "https://ocw.mit.edu/"
OSTX = "https://openstax.org/"
OSHA = "https://www.osha.gov/"
FCC = "https://www.freecodecamp.org/"
CS50 = "https://cs50.harvard.edu/"
WISTECH = "https://www.wistechopen.org/"
DELTA_MAP = "https://programmap.deltacollege.edu/"
MJC_MAP = "https://programmap.mjc.edu/"
PROV_OSTX = "OpenStax (Rice University)"
PROV_OCW = "MIT OpenCourseWare"
PROV_OSHA = "U.S. Occupational Safety and Health Administration (OSHA)"
PROV_OPENRN = "Open RN / WisTech Open (Chippewa Valley Technical College)"
PROV_DELTA = "San Joaquin Delta College"
PROV_MJC = "Modesto Junior College"
PROV_CS50 = "Harvard University (CS50)"


def C(cid, title, provider, home, url, kind, skills, hours, check=None, cost=0,
      hours_real=None, notes=None):
    return {"id": cid, "title": title, "provider": provider, "home": home, "url": url, "kind": kind,
            "skills": skills, "hours": hours, "check": check, "cost": cost, "hours_real": hours_real,
            "notes": notes}


COURSES = [
    # ---- software and digital ----
    C("fcc_scientific_python", "Scientific Computing with Python", "freeCodeCamp", FCC,
      "https://www.freecodecamp.org/learn/scientific-computing-with-python/", "course",
      ["python", "programming", "complex_problem_solving"], 300, {"fcc": "scientific-computing-with-python"}),
    C("fcc_responsive_web_design", "Responsive Web Design", "freeCodeCamp", FCC,
      "https://www.freecodecamp.org/learn/2022/responsive-web-design/", "course",
      ["web_fundamentals", "programming"], 300, {"fcc": "2022/responsive-web-design"}),
    C("fcc_javascript_algorithms", "JavaScript Algorithms and Data Structures", "freeCodeCamp", FCC,
      "https://www.freecodecamp.org/learn/javascript-algorithms-and-data-structures-v8/", "course",
      ["web_fundamentals", "programming", "complex_problem_solving"], 300,
      {"fcc": "javascript-algorithms-and-data-structures-v8"}),
    C("fcc_relational_database", "Relational Database", "freeCodeCamp", FCC,
      "https://www.freecodecamp.org/learn/relational-database/", "course",
      ["sql", "git", "programming"], 300, {"fcc": "relational-database"}),
    C("fcc_quality_assurance", "Quality Assurance", "freeCodeCamp", FCC,
      "https://www.freecodecamp.org/learn/quality-assurance/", "course",
      ["software_testing", "quality_control_analysis", "programming"], 300, {"fcc": "quality-assurance"}),
    C("cs50x", "CS50x: Introduction to Computer Science", PROV_CS50, CS50,
      "https://cs50.harvard.edu/x/", "course",
      ["programming", "complex_problem_solving", "sql", "web_fundamentals"], 120, {"title": ["CS50x"]}),
    C("cs50_python", "CS50's Introduction to Programming with Python", PROV_CS50, CS50,
      "https://cs50.harvard.edu/python/", "course",
      ["python", "programming", "software_testing"], 80, {"title": ["Introduction to Programming with Python"]}),
    C("cs50_sql", "CS50's Introduction to Databases with SQL", PROV_CS50, CS50,
      "https://cs50.harvard.edu/sql/", "course",
      ["sql", "systems_analysis"], 60, {"title": ["Introduction to Databases with SQL"]}),
    C("cs50_web", "CS50's Web Programming with Python and JavaScript", PROV_CS50, CS50,
      "https://cs50.harvard.edu/web/", "course",
      ["web_fundamentals", "python", "sql", "git", "technology_design", "operations_analysis"], 120,
      {"title": ["Web Programming with Python and JavaScript"]}),
    C("mit_6_100l", "Introduction to CS and Programming using Python (6.100L, Fall 2022)", PROV_OCW, OCW,
      "https://ocw.mit.edu/courses/6-100l-introduction-to-cs-and-programming-using-python-fall-2022/", "course",
      ["python", "programming", "mathematics"], 100, {"title": ["Introduction to CS and Programming using Python"]}),
    C("mit_missing_semester", "The Missing Semester of Your CS Education", "MIT CSAIL",
      "https://missing.csail.mit.edu/", "https://missing.csail.mit.edu/", "course",
      ["git", "software_testing", "programming"], 24, {"title": ["Missing Semester"]}),
    C("pro_git", "Pro Git (2nd edition)", "Scott Chacon and Ben Straub (git-scm.com)", "https://git-scm.com/",
      "https://git-scm.com/book/en/v2", "book", ["git"], 20, {"body": ["Pro Git"]}),
    C("py4e", "Python for Everybody", "Charles Severance (py4e.com)", "https://www.py4e.com/",
      "https://www.py4e.com/", "course", ["python", "programming", "sql"], 60, {"title": ["Python for Everybody"]}),
    C("python_tutorial", "The Python Tutorial", "Python Software Foundation", "https://www.python.org/",
      "https://docs.python.org/3/tutorial/", "guide", ["python"], 10, {"title": ["The Python Tutorial"]}),
    C("odin_foundations", "Foundations", "The Odin Project", "https://www.theodinproject.com/",
      "https://www.theodinproject.com/paths/foundations/courses/foundations", "course",
      ["web_fundamentals", "git"], 120, {"title": ["Foundations", "The Odin Project"]}),
    C("mdn_learn_web", "Learn web development", "MDN Web Docs (Mozilla)", "https://developer.mozilla.org/",
      "https://developer.mozilla.org/en-US/docs/Learn_web_development", "guide",
      ["web_fundamentals"], 60, {"title": ["Learn web development"]}),
    C("openstax_intro_python", "Introduction to Python Programming", PROV_OSTX, OSTX,
      "https://openstax.org/details/books/introduction-python-programming", "book",
      ["python", "programming"], 40, {"openstax": ("introduction-python-programming", "Introduction to Python Programming")}),
    # ---- math, science, communication, management ----
    C("khan_algebra_1", "Algebra 1", "Khan Academy", KHAN, KHAN, "course", ["mathematics"], 60),
    C("khan_geometry", "Geometry", "Khan Academy", KHAN, KHAN, "course", ["mathematics"], 40),
    C("khan_physics", "High school physics", "Khan Academy", KHAN, KHAN, "course", ["science", "mathematics"], 40),
    C("khan_chemistry", "Chemistry", "Khan Academy", KHAN, KHAN, "course", ["science"], 40),
    C("khan_electrical_engineering", "Electrical engineering: circuits", "Khan Academy", KHAN, KHAN, "course",
      ["electrical_theory", "science"], 20),
    C("khan_personal_finance", "Personal finance", "Khan Academy", KHAN, KHAN, "course",
      ["management_of_financial_resources"], 15),
    C("openstax_intro_statistics", "Introductory Statistics 2e", PROV_OSTX, OSTX,
      "https://openstax.org/details/books/introductory-statistics-2e", "book",
      ["mathematics", "critical_thinking"], 60, {"openstax": ("introductory-statistics-2e", "Introductory Statistics 2e")}),
    C("openstax_college_success", "College Success", PROV_OSTX, OSTX,
      "https://openstax.org/details/books/college-success", "book",
      ["learning_strategies", "active_learning", "time_management"], 30,
      {"openstax": ("college-success", "College Success")}),
    C("openstax_writing_guide", "Writing Guide with Handbook", PROV_OSTX, OSTX,
      "https://openstax.org/details/books/writing-guide", "book",
      ["writing", "reading_comprehension", "critical_thinking"], 40,
      {"openstax": ("writing-guide", "Writing Guide with Handbook")}),
    C("openstax_org_behavior", "Organizational Behavior", PROV_OSTX, OSTX,
      "https://openstax.org/details/books/organizational-behavior", "book",
      ["social_perceptiveness", "coordination", "negotiation", "persuasion"], 50,
      {"openstax": ("organizational-behavior", "Organizational Behavior")}),
    C("openstax_principles_management", "Principles of Management", PROV_OSTX, OSTX,
      "https://openstax.org/details/books/principles-management", "book",
      ["management_of_personnel_resources", "judgment_and_decision_making", "time_management", "instructing",
       "coordination"], 50, {"openstax": ("principles-management", "Principles of Management")}),
    C("openstax_workplace_software", "Workplace Software and Skills", PROV_OSTX, OSTX,
      "https://openstax.org/details/books/workplace-software-skills", "book",
      ["spreadsheets", "writing"], 40, {"openstax": ("workplace-software-skills", "Workplace Software and Skills")}),
    C("learnfree_excel", "Excel: Foundations", "LearnFree (GCFGlobal)", "https://www.learnfree.org/",
      "https://www.learnfree.org/series/excel-foundations", "course",
      ["spreadsheets", "mathematics"], 8, {"title": ["Excel: Foundations"]}),
    C("mit_management_communication", "Management Communication for Undergraduates (15.279, Fall 2012)", PROV_OCW, OCW,
      "https://ocw.mit.edu/courses/15-279-management-communication-for-undergraduates-fall-2012/", "course",
      ["speaking", "writing", "persuasion", "active_listening"], 60,
      {"title": ["Management Communication for Undergraduates"]}),
    C("mit_logistics_systems", "Logistics Systems (ESD.260J, Fall 2006)", PROV_OCW, OCW,
      "https://ocw.mit.edu/courses/esd-260j-logistics-systems-fall-2006/", "course",
      ["inventory_systems", "shipping_receiving", "systems_analysis", "mathematics"], 100,
      {"title": ["Logistics Systems"]}),
    C("mit_supply_chain_planning", "Supply Chain Planning (15.762J, Spring 2011)", PROV_OCW, OCW,
      "https://ocw.mit.edu/courses/15-762j-supply-chain-planning-spring-2011/", "course",
      ["inventory_systems", "management_of_material_resources", "systems_evaluation", "judgment_and_decision_making"],
      80, {"title": ["Supply Chain Planning"]}),
    # ---- healthcare ----
    C("openstax_fundamentals_nursing", "Fundamentals of Nursing", PROV_OSTX, OSTX,
      "https://openstax.org/details/books/fundamentals-nursing", "book",
      ["patient_assessment", "infection_control", "ehr_charting", "service_orientation"], 80,
      {"openstax": ("fundamentals-nursing", "Fundamentals of Nursing")}),
    C("openstax_clinical_nursing_skills", "Clinical Nursing Skills", PROV_OSTX, OSTX,
      "https://openstax.org/details/books/clinical-nursing-skills", "book",
      ["patient_assessment", "infection_control", "medication_safety"], 70,
      {"openstax": ("clinical-nursing-skills", "Clinical Nursing Skills")}),
    C("openstax_pharmacology", "Pharmacology for Nurses", PROV_OSTX, OSTX,
      "https://openstax.org/details/books/pharmacology", "book",
      ["medication_safety", "science"], 60, {"openstax": ("pharmacology", "Pharmacology for Nurses")}),
    C("openstax_med_surg", "Medical-Surgical Nursing", PROV_OSTX, OSTX,
      "https://openstax.org/details/books/medical-surgical-nursing", "book",
      ["patient_assessment", "monitoring", "critical_thinking"], 90,
      {"openstax": ("medical-surgical-nursing", "Medical-Surgical Nursing")}),
    C("openstax_anatomy_physiology", "Anatomy and Physiology 2e", PROV_OSTX, OSTX,
      "https://openstax.org/details/books/anatomy-and-physiology-2e", "book",
      ["science"], 90, {"openstax": ("anatomy-and-physiology-2e", "Anatomy and Physiology 2e")}),
    C("openrn_nursing_fundamentals", "Nursing Fundamentals 2e (Open RN)", PROV_OPENRN, WISTECH,
      "https://wtcs.pressbooks.pub/nursingfundamentals/", "book",
      ["patient_assessment", "infection_control", "ehr_charting", "social_perceptiveness"], 60,
      {"title": ["Nursing Fundamentals"]}),
    C("openrn_nursing_pharmacology", "Nursing Pharmacology (Open RN)", PROV_OPENRN, WISTECH,
      "https://wtcs.pressbooks.pub/pharmacology/", "book", ["medication_safety"], 50,
      {"title": ["Nursing Pharmacology"]}),
    C("openrn_nursing_skills", "Nursing Skills 2e (Open RN)", PROV_OPENRN, WISTECH,
      "https://wtcs.pressbooks.pub/nursingskills/", "book",
      ["patient_assessment", "medication_safety", "infection_control"], 50, {"title": ["Nursing Skills"]}),
    C("openrn_nursing_management", "Nursing Management and Professional Concepts 2e (Open RN)", PROV_OPENRN, WISTECH,
      "https://wtcs.pressbooks.pub/nursingmpc/", "book",
      ["management_of_personnel_resources", "coordination", "judgment_and_decision_making"], 40,
      {"title": ["Nursing Management and Professional Concepts"]}),
    C("redcross_cpr_first_aid", "CPR, AED and First Aid classes", "American Red Cross", "https://www.redcross.org/",
      "https://www.redcross.org/take-a-class", "certification", ["bls_cpr"], 5,
      {"title": ["Take a Class"]}, cost=None, notes="Class prices vary by course type and location; not verified."),
    C("aha_bls", "Basic Life Support (BLS) course", "American Heart Association", "https://cpr.heart.org/",
      "https://cpr.heart.org/", "certification", ["bls_cpr"], 4, None, cost=None,
      notes="Exact course page not verified (site blocked scripted requests); prices vary by training center."),
    C("openwho_ipc", "Infection prevention and control courses", "World Health Organization (OpenWHO)",
      "https://openwho.org/", "https://openwho.org/", "course", ["infection_control"], 5, None,
      notes="Course catalog page not verified (rendered by JavaScript); verify on openwho.org."),
    # ---- logistics and workplace safety ----
    C("osha_forklift_etool", "eTool: Powered Industrial Trucks (Forklift)", PROV_OSHA, OSHA,
      "https://www.osha.gov/etools/powered-industrial-trucks", "guide",
      ["forklift_safety", "osha_safety", "operation_and_control"], 3, {"title": ["Powered Industrial Trucks"]}),
    C("osha_warehousing", "Warehousing safety (topic overview)", PROV_OSHA, OSHA,
      "https://www.osha.gov/warehousing", "guide", ["osha_safety", "forklift_safety"], 1, {"title": ["Warehousing"]}),
    C("osha_outreach_10_hour", "OSHA Outreach Training Program: 10-hour course",
      PROV_OSHA + ", delivered by authorized trainers", OSHA,
      "https://www.osha.gov/training/outreach", "certification", ["osha_safety"], 10,
      {"title": ["Outreach Training Program"], "body": ["10-hour or 30-hour course completion card"]}, cost=None,
      hours_real="OSHA page: students receive an OSHA 10-hour or 30-hour course completion card",
      notes="Price set by each authorized trainer; not verified."),
    C("osha_lockout_tagout", "Control of Hazardous Energy (Lockout/Tagout)", PROV_OSHA, OSHA,
      "https://www.osha.gov/control-hazardous-energy", "guide", ["lockout_tagout", "osha_safety"], 2,
      {"title": ["Lockout/Tagout"]}),
    C("osha_electrical_safety", "Electrical safety (topic overview)", PROV_OSHA, OSHA,
      "https://www.osha.gov/electrical", "guide", ["osha_safety", "lockout_tagout"], 1, {"title": ["Electrical"]}),
    C("osha_welding_safety", "Welding, cutting, and brazing safety (topic overview)", PROV_OSHA, OSHA,
      "https://www.osha.gov/welding-cutting-brazing", "guide", ["osha_safety"], 1,
      {"title": ["Welding, Cutting, and Brazing"]}),
    C("osha_robotics_safety", "Robotics safety (topic overview)", PROV_OSHA, OSHA,
      "https://www.osha.gov/robotics", "guide", ["osha_safety", "lockout_tagout"], 1, {"title": ["Robotics"]}),
    C("osha_agricultural_operations", "Agricultural operations safety (topic overview)", PROV_OSHA, OSHA,
      "https://www.osha.gov/agricultural-operations", "guide", ["osha_safety", "ag_equipment_operation"], 1,
      {"title": ["Agricultural Operations"]}),
    C("calosha_heat_illness", "Heat Illness Prevention guidance and resources",
      "Cal/OSHA (California Department of Industrial Relations)", "https://www.dir.ca.gov/",
      "https://www.dir.ca.gov/dosh/heatillnessinfo.html", "guide", ["osha_safety"], 2,
      {"title": ["Heat Illness Prevention"]}),
    C("ca_dmv_commercial_handbook", "California Commercial Driver Handbook (air brakes section)",
      "California Department of Motor Vehicles", "https://www.dmv.ca.gov/",
      "https://www.dmv.ca.gov/portal/driver-handbooks/", "book", ["air_brakes", "reading_comprehension"], 10,
      {"title": ["Handbooks"], "body": ["Commercial Driver Handbook"]},
      notes="Link is the DMV handbooks page, which lists the Commercial Driver Handbook PDF."),
    # ---- trades: welding, electrical, mechanical, automation ----
    C("openwa_intro_welding", "Introduction to Welding",
      "Washington Open ProfTech (Washington State Board for Community and Technical Colleges)",
      "https://openwa.pressbooks.pub/", "https://openwa.pressbooks.pub/welding1/", "book",
      ["stick_welding", "mig_welding", "tig_welding", "osha_safety"], 40, {"title": ["Introduction to Welding"]}),
    C("wistech_blueprint_reading", "Blueprint Reading", "WisTech Open", WISTECH,
      "https://wtcs.pressbooks.pub/blueprintreading/", "book", ["blueprint_reading", "mathematics"], 30,
      {"title": ["Blueprint Reading"]}),
    C("aws_certified_welder", "AWS Certified Welder program (performance-based weld tests)",
      "American Welding Society (AWS)", "https://www.aws.org/", "https://www.aws.org/", "certification",
      ["mig_welding", "stick_welding", "tig_welding", "quality_control_analysis"], 8, None, cost=None,
      notes="Program page and fees not verified; test fees vary by accredited test facility."),
    C("nfpa_free_access", "Free access to NFPA 70 (National Electrical Code)",
      "National Fire Protection Association (NFPA)", "https://www.nfpa.org/",
      "https://www.nfpa.org/for-professionals/codes-and-standards/list-of-codes-and-standards/free-access",
      "guide", ["nec_code_basics", "reading_comprehension"], 20, {"title": ["Free access"]}),
    C("kuphaldt_electric_circuits", "Lessons In Electric Circuits", "Tony R. Kuphaldt (hosted by ibiblio)",
      "https://www.ibiblio.org/", "https://www.ibiblio.org/kuphaldt/electricCircuits/", "book",
      ["electrical_theory", "mathematics"], 80, {"title": ["Lessons In Electric Circuits"]}),
    C("kuphaldt_socratic_instrumentation", "Socratic Instrumentation (industrial instrumentation and control)",
      "Tony R. Kuphaldt (hosted by ibiblio)", "https://www.ibiblio.org/",
      "https://www.ibiblio.org/kuphaldt/socratic/sinst/", "book",
      ["sensors_actuators", "plc_basics", "troubleshooting", "operations_monitoring"], 100,
      {"title": ["Socratic Instrumentation"]}),
    C("mit_circuits_electronics", "Circuits and Electronics (6.002, Spring 2007)", PROV_OCW, OCW,
      "https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/", "course",
      ["electrical_theory", "mathematics", "science"], 120, {"title": ["Circuits and Electronics"]}),
    C("mit_intro_robotics", "Introduction to Robotics (2.12, Fall 2005)", PROV_OCW, OCW,
      "https://ocw.mit.edu/courses/2-12-introduction-to-robotics-fall-2005/", "course",
      ["robot_programming", "sensors_actuators", "technology_design", "operations_analysis", "mathematics"], 100,
      {"title": ["Introduction to Robotics"]}),
    C("hybrid_text_plcs", "Hybrid Text: Working With PLCs", "Ted Evans (Atlantic OER Pressbooks)",
      "https://pressbooks.atlanticoer-relatlantique.ca/",
      "https://pressbooks.atlanticoer-relatlantique.ca/eltghybridtext/", "book", ["plc_basics", "troubleshooting"],
      40, {"title": ["Working With PLCs"]}),
    C("nwtc_fluids_1", "Fluids 1: Fluid Power and Pneumatics (NWTC)",
      "Northeast Wisconsin Technical College (LibreTexts)", "https://libretexts.org/",
      "https://eng.libretexts.org/Courses/Northeast_Wisconsin_Technical_College/Fluids_1%3A_Fluid_Power_and_Pneumatics_(NWTC)",
      "book", ["hydraulics", "sensors_actuators"], 30, {"title": ["Fluids 1"]}),
    C("nwtc_fluids_2", "Fluids 2: Basic Hydraulics", "Northeast Wisconsin Technical College (WisTech Open)", WISTECH,
      "https://www.wistechopen.org/resources/fluids-2-basic-hydraulics", "book",
      ["hydraulics", "troubleshooting", "equipment_selection"], 30,
      {"title": ["Fluids 2: Basic Hydraulics"], "body": ["Zero Textbook Cost"]}),
    C("arduino_docs_learn", "Arduino Docs: Learn (getting started, sensors, motors)", "Arduino",
      "https://www.arduino.cc/", "https://docs.arduino.cc/learn/", "guide",
      ["sensors_actuators", "programming", "electrical_theory"], 15, {"body": ["Getting Started with Arduino"]}),
    C("isa_ccst", "Certified Control Systems Technician (CCST)", "International Society of Automation (ISA)",
      "https://www.isa.org/", "https://www.isa.org/certification/ccst", "certification",
      ["plc_basics", "sensors_actuators", "troubleshooting"], 40,
      {"title": ["Certified Control Systems Technician"]}, cost=None,
      notes=("ISA lists the CCST Level 1 exam as 150 questions in 4 hours (page read on the check date). Exam fee "
             "not verified. Hours here are a Foothold estimate of preparation time.")),
    C("saca_certifications", "SACA industry certifications (automation and Industry 4.0)",
      "Smart Automation Certification Alliance (SACA)", "https://www.saca.org/", "https://www.saca.org/",
      "certification", ["plc_basics", "robot_programming", "sensors_actuators"], 20, None, cost=None,
      notes="Not verified (TLS error from our network); fees not verified."),
    C("ase_truck_tests", "ASE Medium-Heavy Truck certification tests",
      "National Institute for Automotive Service Excellence (ASE)", "https://www.ase.com/", "https://www.ase.com/",
      "certification", ["diesel_diagnostics", "air_brakes", "repairing"], 20, None, cost=None,
      notes="Not verified (site blocked scripted requests); test fees not verified."),
    # ---- agriculture ----
    C("cimis", "CIMIS: California Irrigation Management Information System",
      "California Department of Water Resources", "https://cimis.water.ca.gov/", "https://cimis.water.ca.gov/",
      "tool", ["irrigation_management", "science"], 3,
      {"title": ["California Irrigation Management Information System"]}),
    C("fao_56_crop_et", ("Crop Evapotranspiration: Guidelines for Computing Crop Water Requirements "
                         "(FAO Irrigation and Drainage Paper 56)"),
      "Food and Agriculture Organization of the United Nations (FAO)", "https://www.fao.org/",
      "https://www.fao.org/4/x0490e/x0490e00.htm", "book", ["irrigation_management", "science", "mathematics"], 30,
      {"body": ["Crop evapotranspiration", "FAO Irrigation and drainage paper 56"]}),
    C("ucipm_online_training", "UC IPM online training courses",
      "UC Statewide Integrated Pest Management Program (UC ANR)", "https://ipm.ucanr.edu/",
      "https://ipm.ucanr.edu/online-training/", "course", ["pesticide_safety", "science"], 5,
      {"title": ["Online Training"], "body": ["Courses may be accessed for free"]},
      notes="Free to access; a fee applies only if you request continuing education units (per the page)."),
    C("cdpr_worker_safety", "Pesticide worker health and safety", "California Department of Pesticide Regulation",
      "https://www.cdpr.ca.gov/", "https://www.cdpr.ca.gov/worker-health-and-safety/", "guide",
      ["pesticide_safety", "osha_safety"], 2, {"title": ["Worker Health and Safety"]}),
    C("psu_nstmop", "National Safe Tractor and Machinery Operation Program", "Penn State Extension",
      "https://extension.psu.edu/", "https://extension.psu.edu/national-safe-tractor-and-machinery-operation-program",
      "course", ["ag_equipment_operation", "osha_safety", "operation_and_control"], 24,
      {"title": ["National Safe Tractor and Machinery Operation Program"], "body": ["24 hours of instruction"]},
      cost=None, hours_real="Penn State page: the NSTMOP recommends 24 hours of instruction",
      notes="Delivered by local instructors; cost varies and was not verified."),
    # ---- community college certificates (units from the official Program Pathways Mapper) ----
    C("delta_gmaw_fcaw_coa", "Gas Metal Arc Welding (GMAW)/Flux Core Arc Welding (FCAW) Certificate of Achievement",
      PROV_DELTA, DELTA_MAP,
      "https://programmap.deltacollege.edu/program/gas-metal-arc-welding-gmaw-flux-core-arc-welding-fcaw/",
      "program", ["mig_welding", "blueprint_reading", "osha_safety"], None,
      {"title": ["Gas Metal Arc Welding (GMAW)/Flux Core Arc Welding (FCAW)"]}, cost=("units", 20.0)),
    C("delta_smaw_coa", "Oxy-Fuel Processes and Shielded Metal Arc Welding (SMAW) Certificate of Achievement",
      PROV_DELTA, DELTA_MAP,
      "https://programmap.deltacollege.edu/program/oxy-fuel-processes-and-shielded-metal-arc-welding-smaw/",
      "program", ["stick_welding", "osha_safety"], None,
      {"title": ["Shielded Metal Arc Welding"]}, cost=("units", 20.0)),
    C("delta_diesel_technician_coa", "Diesel Equipment Technician Certificate of Achievement", PROV_DELTA, DELTA_MAP,
      "https://programmap.deltacollege.edu/program/diesel-equipment-technician/", "program",
      ["diesel_diagnostics", "hydraulics", "air_brakes", "repairing", "equipment_selection"], None,
      {"title": ["Diesel Equipment Technician"]}, cost=("units", 42.5)),
    C("delta_heavy_equipment_mechanic_coa", "Heavy Equipment Mechanic Certificate of Achievement", PROV_DELTA, DELTA_MAP,
      "https://programmap.deltacollege.edu/program/heavy-equipment-mechanic/", "program",
      ["hydraulics", "equipment_maintenance", "repairing"], None,
      {"title": ["Heavy Equipment Mechanic"]}, cost=("units", 24.0)),
    C("delta_electrician_trainee_coa",
      "Electrical Technology - General Electrician Trainee Certificate of Achievement", PROV_DELTA, DELTA_MAP,
      "https://programmap.deltacollege.edu/program/electrical-technology-general-electrician-trainee/", "program",
      ["electrical_theory", "nec_code_basics", "conduit_bending", "blueprint_reading", "installation"], None,
      {"title": ["General Electrician Trainee"]}, cost=("units", 43.0)),
    C("mjc_electrician_coa", "Electrician Certificate of Achievement", PROV_MJC, MJC_MAP,
      "https://programmap.mjc.edu/program/electrician/", "program",
      ["electrical_theory", "nec_code_basics", "conduit_bending"], None,
      {"title": ["Electrician"]}, cost=("units", 34.0)),
    C("delta_automation_mechatronics_coa", "Automation Technician - Mechatronics Certificate of Achievement",
      PROV_DELTA, DELTA_MAP,
      "https://programmap.deltacollege.edu/program/automation-technician-mechatronics/", "program",
      ["plc_basics", "sensors_actuators", "robot_programming", "electrical_theory", "installation"], None,
      {"title": ["Automation Technician - Mechatronics"]}, cost=("units", 33.5)),
    C("delta_logistics_supervisor_coa", "Logistics and Transportation Supervisor Certificate of Achievement",
      PROV_DELTA, DELTA_MAP,
      "https://programmap.deltacollege.edu/program/logistics-and-transportation-supervisor/", "program",
      ["inventory_systems", "shipping_receiving", "management_of_personnel_resources"], None,
      {"title": ["Logistics and Transportation Supervisor"]}, cost=("units", 24.0)),
    C("delta_ag_mechanics_coa", "Agriculture Mechanics Certificate of Achievement", PROV_DELTA, DELTA_MAP,
      "https://programmap.deltacollege.edu/program/agriculture-mechanics/", "program",
      ["ag_equipment_operation", "equipment_maintenance", "repairing"], None,
      {"title": ["Agriculture Mechanics"]}, cost=("units", 16.5)),
    C("mjc_mechanized_ag_coa", "Mechanized Agriculture Technician Certificate of Achievement", PROV_MJC, MJC_MAP,
      "https://programmap.mjc.edu/program/mechanized-agriculture-technician/", "program",
      ["ag_equipment_operation", "hydraulics", "equipment_maintenance", "diesel_diagnostics"], None,
      {"title": ["Mechanized Agriculture Technician"]}, cost=("units", 30.0)),
]

# Community college enrollment fee (REAL, read on the Delta College fee page 2026-10-24; also in programs_raw.json)
CCC_FEE_FALLBACK = 46.0
CCC_FEE_URL = "https://www.deltacollege.edu/admission-aid/tuition-fees"
CC_HOURS_PER_UNIT_ESTIMATE = 18  # Foothold estimate: ~18 class hours per semester unit (lecture-equivalent)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
OPENSTAX_API = "https://openstax.org/apps/cms/api/v2/pages/?type=books.Book&fields=title,slug,book_state&limit=250"


# --------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------
def slug(text: str) -> str:
    s = text.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def read_csv(name: str) -> list[dict]:
    with open(RAW_ONET / name, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_json(path: Path, default=None, tries: int = 3):
    if not path.exists():
        return default
    for attempt in range(tries):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError:
            if attempt == tries - 1:
                raise
            time.sleep(0.5)
    return default


def write_json(path: Path, obj) -> None:
    """Atomic write (temp file + replace) so the live API never reads a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    for attempt in range(8):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:  # file briefly open elsewhere (Windows / OneDrive)
            time.sleep(0.25 * (attempt + 1))
    os.replace(tmp, path)


def r3(x: float) -> float:
    return round(float(x), 3)


def r4(x: float) -> float:
    return round(float(x), 4)


def percentile_rank(sorted_vals: list[float], x: float) -> float:
    """Mid-rank percentile: (n_below + 0.5 * n_equal) / N. 0.5 ~ the middle of the universe."""
    lo = bisect.bisect_left(sorted_vals, x)
    hi = bisect.bisect_right(sorted_vals, x)
    return (lo + 0.5 * (hi - lo)) / len(sorted_vals)


def quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return float("nan")
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


# --------------------------------------------------------------------------------------------
# O*NET loading
# --------------------------------------------------------------------------------------------
class Onet:
    def __init__(self) -> None:
        self.selection = load_json(RAW_ONET / "SELECTION.json")
        if not self.selection:
            sys.exit("missing data/raw/onet/SELECTION.json")
        self.content = {r["Element ID"]: (r["Element Name"], r["Description"]) for r in read_csv("content_model_reference.csv")}
        self.occ = {r["O*NET-SOC Code"]: (r["Title"], r["Description"]) for r in read_csv("occupation_data.csv")}

        self.ws: dict[str, dict[str, dict[str, float]]] = collections.defaultdict(lambda: collections.defaultdict(dict))
        for r in read_csv("work_styles.csv"):
            self.ws[r["O*NET-SOC Code"]][r["Element ID"]][r["Scale ID"]] = float(r["Data Value"])

        self.skill_im: dict[str, dict[str, float]] = collections.defaultdict(dict)
        self.skill_names: dict[str, str] = {}
        for name in ("essential_skills.csv", "transferable_skills.csv"):
            for r in read_csv(name):
                self.skill_names[r["Element ID"]] = r["Element Name"]
                if r["Scale ID"] == "IM":
                    self.skill_im[r["O*NET-SOC Code"]][r["Element ID"]] = float(r["Data Value"])

        self.interest: dict[str, dict[str, float]] = collections.defaultdict(dict)
        for r in read_csv("career_interest_types.csv"):
            self.interest[r["O*NET-SOC Code"]][r["Element ID"]] = float(r["Data Value"])

        self.ws_elements = [e["element_id"] for e in self.selection["work_styles"]]
        self.trait_of = dict(zip(self.ws_elements, TRAIT_IDS))
        self.element_of = dict(zip(TRAIT_IDS, self.ws_elements))
        # Universe: every occupation with complete Work Styles data (21 elements x WI and DR)
        self.universe = sorted(
            soc for soc, d in self.ws.items()
            if all(e in d and "WI" in d[e] and "DR" in d[e] for e in self.ws_elements)
        )
        self.wi_sorted = {tid: sorted(self.ws[soc][eid]["WI"] for soc in self.universe)
                          for tid, eid in self.element_of.items()}
        # Skill importance stats across every occupation with Skills data
        self.skill_elements = sorted(self.skill_names, key=lambda e: [int(p) if p.isdigit() else p for p in e.split(".")])
        self.skill_id_of = {e: slug(self.skill_names[e]) for e in self.skill_elements}
        socs = [s for s in self.skill_im if len(self.skill_im[s]) == len(self.skill_elements)]
        self.skill_universe = len(socs)
        self.skill_mean = {e: statistics.fmean(self.skill_im[s][e] for s in socs) for e in self.skill_elements}
        self.skill_sd = {e: statistics.pstdev([self.skill_im[s][e] for s in socs]) for e in self.skill_elements}

    def check_traits(self) -> None:
        if len(self.ws_elements) != 21:
            sys.exit(f"expected 21 work styles, found {len(self.ws_elements)}")
        for tid, eid in zip(TRAIT_IDS, self.ws_elements):
            name = self.content[eid][0]
            if slug(name) != tid:
                sys.exit(f"trait order mismatch: {eid} {name!r} -> {slug(name)!r} != contract id {tid!r}")

    def holland(self, soc: str) -> str:
        letters = "RIASEC"
        out = []
        for e in ("1.B.1.g", "1.B.1.h", "1.B.1.i"):
            v = int(round(self.interest[soc].get(e, 0)))
            if 1 <= v <= 6:
                out.append(letters[v - 1])
        return "".join(out)

    def interests(self, soc: str) -> dict[str, float]:
        return {name: self.interest[soc][f"1.B.1.{chr(ord('a') + i)}"]
                for i, name in enumerate(RIASEC) if f"1.B.1.{chr(ord('a') + i)}" in self.interest[soc]}

    def distinctive_skills(self, soc: str, k: int = 5, min_im: float = 2.5) -> list[tuple[str, float, float]]:
        """O*NET skills with the highest importance relative to the all-occupation mean (z-score)."""
        rows = []
        for e, v in self.skill_im[soc].items():
            sd = self.skill_sd[e] or 1.0
            z = (v - self.skill_mean[e]) / sd
            if v >= min_im and z > 0:
                rows.append((self.skill_id_of[e], z, v))
        rows.sort(key=lambda t: (-t[1], t[0]))
        return rows[:k]


# --------------------------------------------------------------------------------------------
# Builders
# --------------------------------------------------------------------------------------------
def build_traits(on: Onet) -> list[dict]:
    group_names = {g["element_id"]: g["name"] for g in on.selection["work_style_groups"]}
    traits = []
    for tid, eid in zip(TRAIT_IDS, on.ws_elements):
        gid = eid.rsplit(".", 1)[0]
        gname = on.content[gid][0]
        if group_names.get(gid) and group_names[gid] != gname:
            print(f"  ! group name differs between SELECTION.json and content model for {gid}", file=sys.stderr)
        traits.append({
            "id": tid,
            "name": on.content[eid][0],
            "onet_element_id": eid,
            "group": gname,
            "group_id": gid,
            "short": on.content[eid][1],
            "credit": ONET_CREDIT,
            "source_id": "onet_31_0",
        })
    return traits


def occupation_record(on: Onet, soc: str, career_id: str | None, group: str | None) -> dict:
    if soc not in on.occ:
        sys.exit(f"{soc} not in occupation_data.csv")
    if soc not in on.universe:
        sys.exit(f"{soc} lacks complete Work Styles data")
    wi = {tid: on.ws[soc][eid]["WI"] for tid, eid in on.element_of.items()}
    dr = {tid: int(round(on.ws[soc][eid]["DR"])) for tid, eid in on.element_of.items()}
    work_styles = {tid: r4(percentile_rank(on.wi_sorted[tid], wi[tid])) for tid in TRAIT_IDS}
    distinctive = [tid for tid, rank in sorted(dr.items(), key=lambda kv: kv[1]) if rank > 0]
    title, description = on.occ[soc]
    rec = {
        "onet_soc": soc,
        "title": title,
        "career_id": career_id,
        "group": group,
        "description": description,
        "onet_url": ONET_ONLINE.format(soc=soc),
        "wi": wi,
        "dr": dr,
        "work_styles": work_styles,
        "distinctive_work_styles": distinctive,
        "skills_im": {on.skill_id_of[e]: on.skill_im[soc][e] for e in on.skill_elements if e in on.skill_im[soc]},
        "interests": on.interests(soc),
        "holland_code": on.holland(soc),
    }
    return rec


def build_occupations(on: Onet) -> dict:
    sel = on.selection
    group_of = {soc: g for g, socs in sel["related_groups"].items() for soc in socs}
    occs = []
    for c in sel["careers"]:
        occs.append(occupation_record(on, c["onet_soc"], c["career_id"], CAREER_GROUP[c["career_id"]]))
    for r in sel["related"]:
        occs.append(occupation_record(on, r["onet_soc"], None, group_of.get(r["onet_soc"])))
    n = len(on.universe)
    dist = {}
    for tid in TRAIT_IDS:
        vals = on.wi_sorted[tid]
        dist[tid] = {"min": vals[0], "p25": r3(quantile(vals, 0.25)), "median": r3(quantile(vals, 0.5)),
                     "p75": r3(quantile(vals, 0.75)), "max": vals[-1], "mean": r4(statistics.fmean(vals)),
                     "sd": r4(statistics.pstdev(vals))}
    return {
        "provenance": {
            "status": "REAL",
            "source_id": "onet_31_0",
            "dataset": "O*NET 31.0 Database",
            "release": sel["release"],
            "retrieved": sel["retrieved"],
            "license": "CC BY 4.0",
            "license_url": sel["license_url"],
            "attribution": sel["attribution"],
            "modified_by_foothold": True,
            "files": ["work_styles.csv", "essential_skills.csv", "transferable_skills.csv",
                      "career_interest_types.csv", "occupation_data.csv", "content_model_reference.csv"],
            "built_by": "data/build_processed.py",
        },
        "method": {
            "work_styles": (
                f"Percentile rank of the occupation's O*NET 31.0 Work Styles Impact (WI, -3..+3) for each trait, "
                f"computed across all {n} O*NET-SOC occupations that have complete Work Styles data "
                "(all 21 elements with both WI and DR)."),
            "formula": "work_styles[t] = (n_below + 0.5 * n_equal) / N, where n_below / n_equal count occupations whose WI for t is lower / equal (mid-rank for ties)",
            "universe_size": n,
            "interpretation": "0.5 is about the middle of all occupations; 0.9 means a higher WI than about 90% of occupations. Values are relative, not absolute importance.",
            "why_not_raw_wi": "Raw WI is high almost everywhere for Dependability and Attention to Detail (about 2.3-3.0 for the 8 careers), so raw values barely separate careers; percentiles spread every trait across 0..1.",
            "wi": "raw O*NET WI values copied unchanged",
            "wi_distribution": (f"per trait: min, p25, median, p75, max, mean and population sd of raw WI across the same "
                                f"{n}-occupation universe (use (wi - mean) / sd for z-scores)"),
            "dr": "raw O*NET Distinctiveness Rank (1 = most distinctive, 0 = not in the occupation's ranked list)",
            "distinctive_work_styles": "trait ids with DR > 0, ordered by DR (most distinctive first)",
            "skills_im": "raw O*NET 31.0 Importance (IM, 1..5) for the 35 Essential + Transferable skills, keyed by skills.json id",
            "interests": "raw O*NET 31.0 Occupational Interest (OI, 1..7) for the six RIASEC types",
            "holland_code": "letters for the O*NET first/second/third interest high-points (IH codes 1-6 = R,I,A,S,E,C; 0 = none)",
        },
        "trait_order": TRAIT_IDS,
        "wi_distribution": dist,
        "occupations": occs,
    }


def build_skills(on: Onet) -> list[dict]:
    skills = []
    for e in on.skill_elements:
        group = e.rsplit(".", 1)[0]
        category, kind = ONET_SKILL_GROUPS[group]
        skills.append({
            "id": on.skill_id_of[e],
            "name": on.skill_names[e],
            "category": category,
            "kind": kind,
            "source": SKILL_SOURCE_ONET,
            "onet_element_id": e,
            "description": on.content[e][1],
            "credit": ONET_CREDIT,
            "source_id": "onet_31_0",
        })
    onet_ids = {s["id"] for s in skills}
    for sid, name, category, desc in FOOTHOLD_SKILLS:
        if sid in onet_ids:
            sys.exit(f"Foothold skill id collides with an O*NET skill id: {sid}")
        skills.append({
            "id": sid,
            "name": name,
            "category": category,
            "kind": "job_specific",
            "source": SKILL_SOURCE_FOOTHOLD,
            "onet_element_id": None,
            "description": desc,
            "source_id": "foothold_taxonomy",
        })
    ids = [s["id"] for s in skills]
    dupes = [i for i, n in collections.Counter(ids).items() if n > 1]
    if dupes:
        sys.exit(f"duplicate skill ids: {dupes}")
    return skills


def build_careers(on: Onet, occupations: dict, skill_ids: set[str]) -> list[dict]:
    occ_by_career = {o["career_id"]: o for o in occupations["occupations"] if o["career_id"]}
    existing = load_json(PROCESSED / "careers.json", default=[]) or []
    old_by_id = {c.get("id"): c for c in existing if isinstance(c, dict)}
    careers = []
    seen_coworkers: set[str] = set()
    for c in on.selection["careers"]:
        cid = c["career_id"]
        meta = CAREERS_META[cid]
        occ = occ_by_career[cid]
        onet_skills = [s for s, _z, _im in on.distinctive_skills(c["onet_soc"])]
        foothold = list(meta["foothold_skills"])
        skills = list(dict.fromkeys(foothold + onet_skills))
        missing = [s for s in skills if s not in skill_ids]
        if missing:
            sys.exit(f"{cid}: unknown skills {missing}")
        for cw in meta["coworkers"]:
            if cw["id"] in seen_coworkers:
                sys.exit(f"duplicate coworker id {cw['id']}")
            seen_coworkers.add(cw["id"])
        rec = {
            "id": cid,
            "title": c["title"],
            "onet_soc": c["onet_soc"],
            "onet_title": c["onet_title"],
            "onet_url": ONET_ONLINE.format(soc=c["onet_soc"]),
            "summary": meta["summary"],
            "path_types": [r for r in ROUTE_TYPES if r in meta["path_types"]],
            "work_styles": occ["work_styles"],
            "distinctive_work_styles": occ["distinctive_work_styles"],
            "skills": skills,
            "skills_basis": {
                "foothold": foothold,
                "onet": onet_skills,
                "method": ("foothold = Foothold job-specific skills (editorial); onet = the 5 O*NET 31.0 skills with the "
                           "highest Importance relative to the all-occupation mean (z-score), among skills with IM >= 2.5"),
            },
            "holland_code": occ["holland_code"],
            "wage": None,
            "outlook": None,
            "coworkers": meta["coworkers"],
            "provenance": {
                "onet": {"status": "REAL", "source_id": "onet_31_0",
                         "fields": ["onet_soc", "onet_title", "work_styles", "distinctive_work_styles", "skills_basis.onet", "holland_code"]},
                "summary": "Foothold editorial (own words)",
                "path_types": "Foothold editorial; checked against data/raw/programs/programs_raw.json",
                "skills_basis.foothold": {"status": "SAMPLE", "source_id": "foothold_taxonomy"},
                "coworkers": {"status": "FICTIONAL", "source_id": "foothold_fictional_coworkers"},
                "wage_outlook": "filled by the wages/outlook build step; preserved on rebuild",
            },
        }
        old = old_by_id.get(cid)
        if old:
            for k in ("wage", "outlook"):
                if old.get(k) is not None:
                    rec[k] = old[k]
            for k, v in old.items():  # keep keys another producer added
                if k not in rec:
                    rec[k] = v
        careers.append(rec)
    return careers


def ccc_fee_per_unit() -> tuple[float, str]:
    raw = load_json(RAW_PROGRAMS, default=None)
    try:
        fee = float(raw["fees"]["ccc_enrollment_fee_per_unit"]["value"])
        retrieved = raw["fees"]["ccc_enrollment_fee_per_unit"].get("retrieved", "2026-10-24")
        return fee, f"Delta College fee page, read {retrieved}"
    except (TypeError, KeyError, ValueError):
        return CCC_FEE_FALLBACK, "Delta College fee page, read 2026-10-24"


def program_units_from_raw() -> dict[str, tuple[float, float, str]]:
    """url -> (units_min, units_max, terms) from the programs research file (REAL, read 2026-10-24)."""
    raw = load_json(RAW_PROGRAMS, default=None) or {}
    out = {}
    for block in (raw.get("career_programs") or {}).values():
        for p in block.get("programs", []):
            if p.get("url") and p.get("units_min") is not None:
                out.setdefault(p["url"], (p["units_min"], p["units_max"], p.get("terms")))
    return out


def build_courses(skill_ids: set[str]) -> list[dict]:
    checks = (load_json(COURSE_CHECKS, default={}) or {}).get("checks", {})
    fee, fee_basis = ccc_fee_per_unit()
    raw_units = program_units_from_raw()
    out = []
    for c in COURSES:
        bad = [s for s in c["skills"] if s not in skill_ids]
        if bad:
            sys.exit(f"course {c['id']}: unknown skills {bad}")
        if c["kind"] not in COURSE_KINDS:
            sys.exit(f"course {c['id']}: bad kind {c['kind']}")
        chk = checks.get(c["id"]) if c["check"] else None
        verified = bool(chk and chk.get("matched") and chk.get("url") == c["url"])
        rec = {"id": c["id"], "title": c["title"], "provider": c["provider"], "kind": c["kind"]}

        # cost
        cost = c["cost"]
        units = terms = None
        if isinstance(cost, tuple):  # ("units", n): community college program
            units = cost[1]
            raw = raw_units.get(c["url"])
            if raw and not (raw[0] == raw[1] == units):
                print(f"  ! {c['id']}: units {units} differ from programs_raw.json {raw}", file=sys.stderr)
            if raw:
                terms = raw[2]
            rec["cost_usd"] = round(units * fee, 2)
            rec["cost_basis"] = (f"derived: {units:g} units x ${fee:g}/unit California community college enrollment fee "
                                 f"for residents ({fee_basis}); excludes books, tools, materials, and other campus fees")
            rec["cost_source_id"] = "delta_fees"
            cost_known = True
        elif cost == 0:
            rec["cost_usd"] = 0
            rec["cost_basis"] = "free to access" if verified else "free resource (listing not verified)"
            cost_known = True
        else:
            rec["cost_usd"] = None
            rec["cost_basis"] = "not verified: price varies by provider or location; check the provider page"
            cost_known = False

        # hours
        if c["hours_real"] and verified:
            rec["hours"] = c["hours"]
            rec["hours_status"] = "REAL"
            rec["hours_basis"] = c["hours_real"]
        elif units is not None:
            rec["hours"] = int(round(units * CC_HOURS_PER_UNIT_ESTIMATE))
            rec["hours_status"] = "SAMPLE"
            rec["hours_basis"] = (f"Foothold estimate: {units:g} units x {CC_HOURS_PER_UNIT_ESTIMATE} class hours per unit "
                                  "(lecture-equivalent; lab hours add more). Check the program map.")
        else:
            rec["hours"] = c["hours"]
            rec["hours_status"] = "SAMPLE"
            rec["hours_basis"] = "Foothold estimate of study time; not stated by the provider"
        if units is not None:
            rec["units"] = units
            rec["terms"] = terms

        rec["skills"] = c["skills"]
        status = "REAL" if (verified and cost_known) else "SAMPLE"
        rec["status"] = status
        if verified:
            rec["url"] = c["url"]
            rec["verify_url"] = c["url"]
            rec["retrieved"] = chk.get("checked")
            rec["evidence"] = chk.get("evidence")
        else:
            rec["url"] = c["home"]
            rec["verify_url"] = c["home"]
            rec["retrieved"] = None
            rec["evidence"] = ("exact page not verified; link goes to the provider's homepage"
                               if c["check"] is None else f"check failed: {(chk or {}).get('error') or 'not run'}")
        if c["kind"] == "program":
            rec["source_id"] = "ccc_program_mappers" if verified else "course_listings_sample"
        else:
            rec["source_id"] = "course_listings_verified" if status == "REAL" else "course_listings_sample"
        rec["skills_basis"] = "Foothold editorial mapping"
        if c["notes"]:
            rec["notes"] = c["notes"]
        out.append(rec)
    ids = [r["id"] for r in out]
    dupes = [i for i, n in collections.Counter(ids).items() if n > 1]
    if dupes:
        sys.exit(f"duplicate course ids: {dupes}")
    return out


def build_jobs(on: Onet, skill_ids: set[str]) -> list[dict]:
    ids = {j[0] for j in JOBS}
    if len(ids) != len(JOBS):
        sys.exit("duplicate job ids")
    clash = ids & set(CAREER_IDS)
    if clash:
        sys.exit(f"job ids clash with career ids: {clash}")
    out = []
    for jid, title, career, level, soc, req, leads in JOBS:
        if career not in CAREER_IDS or level not in LEVELS:
            sys.exit(f"job {jid}: bad career/level")
        if soc not in on.occ:
            sys.exit(f"job {jid}: {soc} not in occupation_data.csv")
        bad = [s for s in req if s not in skill_ids]
        if bad:
            sys.exit(f"job {jid}: unknown skills {bad}")
        bad = [x for x in leads if x not in ids]
        if bad:
            sys.exit(f"job {jid}: unknown leads_to {bad}")
        out.append({
            "id": jid,
            "title": title,
            "career_id": career,
            "level": level,
            "required_skills": req,
            "leads_to": leads,
            "onet_soc": soc,
            "onet_title": on.occ[soc][0],
            "verify_url": ONET_ONLINE.format(soc=soc),
            "status": "SAMPLE",
            "source_id": "foothold_taxonomy",
        })
    return out


def build_sources(on: Onet, courses: list[dict]) -> list[dict]:
    sel = on.selection
    n = len(on.universe)
    verified = [c for c in courses if c["source_id"] == "course_listings_verified"]
    sample = [c for c in courses if c["source_id"] == "course_listings_sample"]
    programs = [c for c in courses if c["source_id"] == "ccc_program_mappers"]
    checked_dates = sorted({c["retrieved"] for c in courses if c.get("retrieved")})

    def providers(rows):
        return sorted({f"{c['provider']} ({c['verify_url']})" for c in rows})

    return [
        {
            "id": "onet_31_0",
            "title": "O*NET 31.0 Database: Work Styles, Essential Skills, Transferable Skills, Career Interest Types, Occupation Data, Content Model Reference",
            "url": "https://www.onetcenter.org/database.html",
            "publisher": "U.S. Department of Labor, Employment and Training Administration (USDOL/ETA), National Center for O*NET Development",
            "license": "CC BY 4.0",
            "license_url": sel["license_url"],
            "license_page": sel["license_page"],
            "retrieved": sel["retrieved"],
            "status": "REAL",
            "attribution": sel["attribution"],
            "modified": True,
            "modifications": [
                "Work Styles WI values (-3..+3) converted to 0..1 percentile ranks across all occupations with complete Work Styles data (traits.json ids, occupations.json, careers.json).",
                "Element names mapped to snake_case ids; Work Styles and skill descriptions copied verbatim from content_model_reference.csv.",
                "Career skill lists choose the 5 O*NET skills with the highest Importance relative to the all-occupation mean, combined with Foothold job-specific skills.",
                "Only 42 of the 1,016 occupations are kept in occupations.json (8 Foothold careers + 34 related occupations).",
                "Foothold career titles and summaries are Foothold's own; O*NET titles are kept in onet_title.",
            ],
            "methods": {
                "Work styles (traits) on a 0..1 scale": (
                    f"For each of the 21 O*NET 31.0 Work Styles and each occupation: value = (number of occupations with a lower "
                    f"Work Styles Impact (WI) + 0.5 x number with the same WI) / {n}, where {n} is every O*NET-SOC occupation "
                    "with complete Work Styles data (21 elements, WI and DR). 0.5 is about the middle of all occupations; "
                    "0.9 means a higher WI than about 90% of occupations. Raw WI and DR stay in occupations.json."),
                "Career skills": (
                    "careers.json skills = Foothold job-specific skills (editorial, SAMPLE) + the 5 O*NET 31.0 skills with the "
                    f"highest Importance z-score versus the mean of all {on.skill_universe} occupations with Skills data, among "
                    "skills with Importance >= 2.5."),
            },
            "files": [{"file": f["file"], "url": f["url"], "rows": f["rows"], "sha256": f["sha256"]} for f in sel["files"]],
            "used_by": ["traits.json", "occupations.json", "careers.json", "skills.json", "jobs.json"],
            "producer": "data/build_processed.py",
        },
        {
            "id": "onet_online",
            "title": "O*NET OnLine occupation summary pages (verification links)",
            "url": "https://www.onetonline.org/",
            "publisher": "National Center for O*NET Development, for USDOL/ETA",
            "license": "Linked only; no content copied",
            "retrieved": sel["retrieved"],
            "status": "REAL",
            "notes": "careers.json onet_url and jobs.json verify_url use https://www.onetonline.org/link/summary/<O*NET-SOC code> (pattern checked: HTTP 200 on 2026-10-24).",
            "used_by": ["careers.json", "occupations.json", "jobs.json"],
            "producer": "data/build_processed.py",
        },
        {
            "id": "foothold_taxonomy",
            "title": "Foothold skills taxonomy and job nodes (job-specific skills, generic job titles, required skills, career ladders)",
            "url": "data/build_processed.py",
            "publisher": "Foothold (editorial)",
            "license": "Foothold project",
            "retrieved": None,
            "status": "SAMPLE",
            "notes": "Editorial mapping, not verified against job postings. Each job links to the closest O*NET occupation so typical tasks and skills can be checked. Titles are generic; no employer names.",
            "used_by": ["skills.json", "jobs.json", "careers.json"],
            "producer": "data/build_processed.py",
        },
        {
            "id": "foothold_fictional_coworkers",
            "title": "Fictional coworkers for the Try-the-job sim (3 per career)",
            "url": "data/build_processed.py",
            "publisher": "Foothold",
            "license": "Foothold project",
            "retrieved": None,
            "status": "FICTIONAL",
            "notes": "All names, roles, and personalities are invented. Any resemblance to real people is coincidental.",
            "used_by": ["careers.json"],
            "producer": "data/build_processed.py",
        },
        {
            "id": "course_listings_verified",
            "title": f"Learning resources whose exact page was fetched and matched ({len(verified)} listings)",
            "url": "data/raw/courses/course_checks.json",
            "publisher": "Various public providers (see list); checked by Foothold",
            "license": "Links and short factual metadata only; no provider content copied",
            "retrieved": checked_dates[-1] if checked_dates else None,
            "status": "REAL",
            "notes": "Title, provider, URL and cost (free) confirmed on the check date (HTTP 200 + expected title/text, the freeCodeCamp page-data file, or the OpenStax catalog API). Hours are Foothold estimates (hours_status SAMPLE) unless the page states them. Skill tags are Foothold's editorial mapping.",
            "providers": providers(verified),
            "used_by": ["courses.json"],
            "producer": "data/build_processed.py",
        },
        {
            "id": "course_listings_sample",
            "title": f"Learning resources not verified at the exact page or with unknown cost ({len(sample)} listings)",
            "url": "data/build_processed.py",
            "publisher": "Various public providers (see list)",
            "license": "Links only",
            "retrieved": None,
            "status": "SAMPLE",
            "notes": "Plausible listings at real providers. When the exact page was not verified the link goes to the provider homepage; when the price is not stated cost_usd is null. Verify before relying on them.",
            "providers": providers(sample),
            "used_by": ["courses.json"],
            "producer": "data/build_processed.py",
        },
        {
            "id": "ccc_program_mappers",
            "title": f"California Community Colleges Program Pathways Mapper pages, San Joaquin Delta College and Modesto Junior College ({len(programs)} certificates used in courses.json)",
            "url": "https://programmap.deltacollege.edu/",
            "publisher": "San Joaquin Delta College; Modesto Junior College",
            "license": "Public web pages; facts only (title, award, units)",
            "retrieved": checked_dates[-1] if checked_dates else "2026-10-24",
            "status": "REAL",
            "notes": "Units read from the program map pages (data/raw/programs/programs_raw.json, read 2026-10-24); page titles re-checked by build_processed.py --verify-courses. Also: https://programmap.mjc.edu/",
            "used_by": ["courses.json"],
            "producer": "data/build_processed.py",
        },
        {
            "id": "delta_fees",
            "title": "San Joaquin Delta College Tuition and Fees: California community college enrollment fee ($46 per unit, residents)",
            "url": CCC_FEE_URL,
            "publisher": "San Joaquin Delta College",
            "license": "Public web page; facts only",
            "retrieved": "2026-10-24",
            "status": "REAL",
            "notes": "The page states the enrollment fee is approved by the California State Legislature. courses.json program cost_usd = units x fee (excludes books, tools, materials, other fees).",
            "used_by": ["courses.json"],
            "producer": "data/build_processed.py",
        },
    ]


# --------------------------------------------------------------------------------------------
# JSON Schemas (draft 2020-12 subset; validate.py implements the keywords used here)
# --------------------------------------------------------------------------------------------
def build_schemas(careers: list[dict], traits: list[dict]) -> dict[str, dict]:
    coworker_ids = [cw["id"] for c in careers for cw in c["coworkers"]]
    trait_enum = [t["id"] for t in traits]  # exactly what is written to traits.json, in file order
    num_or_null = {"type": ["number", "null"]}
    str_ = {"type": "string", "minLength": 1}
    status = {"enum": STATUSES}
    base = "https://foothold.local/schemas/"
    draft = "https://json-schema.org/draft/2020-12/schema"
    trait_map = {"type": "object", "required": TRAIT_IDS, "propertyNames": {"enum": TRAIT_IDS},
                 "additionalProperties": {"type": "number", "minimum": 0, "maximum": 1}}

    event = {
        "$schema": draft,
        "$id": base + "event.schema.json",
        "title": "Foothold sim event",
        "description": ("One workday scenario for the Try-the-job sim (docs/CONTRACTS.md section 5). Generated by "
                        "data/build_processed.py: trait ids come from data/processed/traits.json and coworker ids from "
                        "data/processed/careers.json. events.json wraps these as {schema_version: 1, status, events: [Event]}. "
                        "Every choice carries coworker_hints (use {} when no coworker reacts). A crunch event may leave "
                        "career_ids empty, meaning it can appear in any career; a non-crunch event needs at least one career."),
        "type": "object",
        "required": ["event_id", "career_ids", "clock", "title", "text", "crunch", "status", "choices"],
        "if": {"properties": {"crunch": {"const": False}}, "required": ["crunch"]},
        "then": {"properties": {"career_ids": {"minItems": 1}}},
        "properties": {
            "event_id": {"type": "string", "pattern": ID_PATTERN, "maxLength": 48},
            "career_ids": {"type": "array", "uniqueItems": True, "items": {"enum": CAREER_IDS},
                           "description": "careers this event belongs to; may be empty only when crunch is true"},
            "clock": {"type": "string", "pattern": "^([01][0-9]|2[0-3]):[0-5][0-9]$",
                      "description": "24-hour HH:MM time of day in the sim"},
            "title": {"type": "string", "minLength": 1, "maxLength": 80},
            "text": {"type": "string", "minLength": 20, "maxLength": 900, "description": "Scenario, 2-4 sentences"},
            "crunch": {"type": "boolean"},
            "status": {"type": "string", "minLength": 1, "examples": ["DRAFT — needs human review"]},
            "choices": {"type": "array", "minItems": 3, "maxItems": 3, "items": {"$ref": "#/$defs/choice"},
                        "description": "Exactly 3 choices; choice_id values must be unique within the event"},
        },
        "$defs": {
            "choice": {
                "type": "object",
                "required": ["choice_id", "text", "trait_deltas", "stat_deltas", "coworker_hints"],
                "properties": {
                    "choice_id": {"type": "string", "pattern": "^[a-z0-9_]{1,16}$"},
                    "text": {"type": "string", "minLength": 1, "maxLength": 400},
                    "trait_deltas": {
                        "type": "object", "minProperties": 2, "maxProperties": 4,
                        "propertyNames": {"enum": trait_enum},
                        "additionalProperties": {"type": "number", "minimum": -1, "maximum": 1},
                        "description": "2-4 traits, each delta in [-1, 1]",
                    },
                    "stat_deltas": {
                        "type": "object", "minProperties": 1,
                        "propertyNames": {"enum": SIM_STATS},
                        "additionalProperties": {"type": "integer", "minimum": -15, "maximum": 15},
                        "description": "integer deltas in [-15, 15] for safety, output, team_trust, stress",
                    },
                    "coworker_hints": {
                        "type": "object",
                        "propertyNames": {"enum": coworker_ids},
                        "additionalProperties": {"type": "string", "minLength": 1, "maxLength": 240},
                        "description": ("coworker id (careers.json) -> how that coworker tends to feel about this choice; "
                                        "required on every choice, {} allowed"),
                    },
                },
            },
        },
    }

    trait = {
        "$schema": draft, "$id": base + "traits.schema.json", "title": "Foothold traits (O*NET 31.0 Work Styles)",
        "type": "array", "minItems": 21, "maxItems": 21,
        "items": {"type": "object", "required": ["id", "name", "onet_element_id", "group", "short"],
                  "properties": {"id": {"enum": TRAIT_IDS}, "name": str_,
                                 "onet_element_id": {"type": "string", "pattern": r"^1\.D\.[1-4]\.[a-i]$"},
                                 "group": str_, "group_id": {"type": "string", "pattern": r"^1\.D\.[1-4]$"},
                                 "short": str_, "credit": str_, "source_id": str_}},
    }

    coworker = {"type": "object", "required": ["id", "name", "role", "style", "base_mood"],
                "properties": {"id": {"type": "string", "pattern": ID_PATTERN}, "name": str_, "role": str_,
                               "style": {"type": "string", "minLength": 1, "maxLength": 200},
                               "base_mood": {"enum": MOODS}, "pronouns": str_, "fictional": {"const": True}}}
    career = {
        "$schema": draft, "$id": base + "careers.schema.json", "title": "Foothold careers",
        "type": "array", "minItems": 8, "maxItems": 8,
        "items": {
            "type": "object",
            "required": ["id", "title", "onet_soc", "onet_title", "summary", "path_types", "work_styles", "skills",
                         "wage", "outlook", "coworkers"],
            "properties": {
                "id": {"enum": CAREER_IDS}, "title": str_,
                "onet_soc": {"type": "string", "pattern": SOC_PATTERN}, "onet_title": str_,
                "summary": {"type": "string", "minLength": 20},
                "path_types": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"enum": ROUTE_TYPES}},
                "work_styles": trait_map,
                "skills": {"type": "array", "minItems": 1, "uniqueItems": True,
                           "items": {"type": "string", "pattern": ID_PATTERN}},
                "wage": {"type": ["object", "null"],
                         "required": ["median_hourly", "median_annual", "p25_annual", "p75_annual", "area", "period",
                                      "source_id", "status"],
                         "properties": {"median_hourly": num_or_null, "median_annual": num_or_null,
                                        "p25_annual": num_or_null, "p75_annual": num_or_null,
                                        "area": str_, "period": str_, "source_id": str_, "status": status}},
                "outlook": {"type": ["object", "null"],
                            "required": ["growth_pct", "annual_openings", "period", "source_id", "status"],
                            "properties": {"growth_pct": num_or_null, "annual_openings": num_or_null,
                                           "period": str_, "source_id": str_, "status": status}},
                "coworkers": {"type": "array", "minItems": 3, "maxItems": 3, "items": coworker},
            },
        },
    }

    occupation = {
        "$schema": draft, "$id": base + "occupations.schema.json", "title": "Foothold occupations (career-fit universe)",
        "type": "object", "required": ["provenance", "method", "occupations"],
        "properties": {
            "provenance": {"type": "object", "required": ["status", "source_id", "retrieved", "license"],
                           "properties": {"status": {"const": "REAL"}, "source_id": str_, "retrieved": str_,
                                          "license": str_}},
            "method": {"type": "object", "required": ["work_styles", "formula", "universe_size"]},
            "occupations": {
                "type": "array", "minItems": 8,
                "items": {"type": "object",
                          "required": ["onet_soc", "title", "career_id", "work_styles", "wi", "dr"],
                          "properties": {
                              "onet_soc": {"type": "string", "pattern": SOC_PATTERN}, "title": str_,
                              "career_id": {"enum": CAREER_IDS + [None]},
                              "work_styles": trait_map,
                              "wi": {"type": "object", "required": TRAIT_IDS, "propertyNames": {"enum": TRAIT_IDS},
                                     "additionalProperties": {"type": "number", "minimum": -3, "maximum": 3}},
                              "dr": {"type": "object", "required": TRAIT_IDS, "propertyNames": {"enum": TRAIT_IDS},
                                     "additionalProperties": {"type": "integer", "minimum": 0, "maximum": 10}},
                              "skills_im": {"type": "object",
                                            "additionalProperties": {"type": "number", "minimum": 1, "maximum": 5}},
                              "interests": {"type": "object", "propertyNames": {"enum": RIASEC},
                                            "additionalProperties": {"type": "number", "minimum": 1, "maximum": 7}},
                          }},
            },
        },
    }

    skill = {
        "$schema": draft, "$id": base + "skills.schema.json", "title": "Foothold skills",
        "type": "array", "minItems": 1,
        "items": {"type": "object", "required": ["id", "name", "category", "source"],
                  "properties": {"id": {"type": "string", "pattern": ID_PATTERN}, "name": str_,
                                 "category": {"type": "string", "pattern": ID_PATTERN},
                                 "kind": {"enum": ["essential", "transferable", "job_specific"]},
                                 "source": {"enum": [SKILL_SOURCE_ONET, SKILL_SOURCE_FOOTHOLD]},
                                 "onet_element_id": {"type": ["string", "null"]},
                                 "description": {"type": "string"}, "credit": str_}},
    }

    course = {
        "$schema": draft, "$id": base + "courses.schema.json", "title": "Foothold learning resources",
        "type": "array", "minItems": 1,
        "items": {"type": "object",
                  "required": ["id", "title", "provider", "cost_usd", "hours", "skills", "url", "status"],
                  "properties": {"id": {"type": "string", "pattern": ID_PATTERN}, "title": str_, "provider": str_,
                                 "kind": {"enum": COURSE_KINDS},
                                 "cost_usd": {"type": ["number", "null"], "minimum": 0},
                                 "hours": {"type": "number", "exclusiveMinimum": 0},
                                 "hours_status": status,
                                 "skills": {"type": "array", "minItems": 1, "uniqueItems": True,
                                            "items": {"type": "string", "pattern": ID_PATTERN}},
                                 "url": {"type": "string", "pattern": "^https?://"},
                                 "verify_url": {"type": "string", "pattern": "^https?://"},
                                 "status": status,
                                 "retrieved": {"type": ["string", "null"]},
                                 "source_id": str_}},
    }

    job = {
        "$schema": draft, "$id": base + "jobs.schema.json", "title": "Foothold job nodes",
        "type": "array", "minItems": 1,
        "items": {"type": "object", "required": ["id", "title", "career_id", "required_skills", "level"],
                  "properties": {"id": {"type": "string", "pattern": ID_PATTERN}, "title": str_,
                                 "career_id": {"enum": CAREER_IDS}, "level": {"enum": LEVELS},
                                 "required_skills": {"type": "array", "minItems": 1, "uniqueItems": True,
                                                     "items": {"type": "string", "pattern": ID_PATTERN}},
                                 "leads_to": {"type": "array", "items": {"type": "string", "pattern": ID_PATTERN}},
                                 "onet_soc": {"type": "string", "pattern": SOC_PATTERN},
                                 "status": status, "source_id": str_}},
    }

    source = {
        "$schema": draft, "$id": base + "sources.schema.json",
        "title": "Foothold source records (data/processed/sources.json and data/processed/sources/*.json)",
        "type": "array",
        "items": {"type": "object", "required": ["id", "title", "url", "publisher", "license", "retrieved", "status"],
                  "properties": {"id": {"type": "string", "pattern": ID_PATTERN}, "title": str_,
                                 "url": str_, "publisher": str_, "license": str_,
                                 "retrieved": {"type": ["string", "null"]}, "status": status,
                                 "attribution": {"type": "string"}, "notes": {"type": ["string", "array"]},
                                 "used_by": {"type": "array", "items": {"type": "string"}}}},
    }

    return {"event": event, "traits": trait, "careers": career, "occupations": occupation, "skills": skill,
            "courses": course, "jobs": job, "sources": source}


# --------------------------------------------------------------------------------------------
# Course page verification (network; only with --verify-courses)
# --------------------------------------------------------------------------------------------
def http_get(url: str, tries: int = 3, timeout: int = 25, max_bytes: int = 3_000_000):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.geturl(), r.read(max_bytes).decode("utf-8", "replace"), None
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (401, 403, 404, 410):
                break
        except Exception as e:  # noqa: BLE001 - network errors of many kinds
            last = f"{type(e).__name__}: {str(e)[:120]}"
        time.sleep(1.5 * (attempt + 1))
    return None, url, "", last


def page_title(body: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(m.group(1))).strip() if m else ""


def page_text(body: str) -> str:
    body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", body, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body)))


def check_course(c: dict, openstax: dict | None, today: str) -> dict:
    spec = c["check"]
    res = {"url": c["url"], "checked": today, "matched": False, "method": None, "evidence": None, "error": None}
    try:
        if "fcc" in spec:
            res["method"] = "freeCodeCamp page-data"
            path = urllib.parse.urlparse(c["url"]).path.rstrip("/")
            status, _final, body, err = http_get(f"https://www.freecodecamp.org/page-data{path}/page-data.json")
            if status != 200:
                res["error"] = err or f"HTTP {status}"
                return res
            sb = json.loads(body).get("result", {}).get("pageContext", {}).get("superBlock")
            res["matched"] = sb == spec["fcc"]
            res["evidence"] = f"page-data superBlock={sb!r}"
            return res
        if "openstax" in spec:
            res["method"] = "OpenStax CMS API"
            slug_, title = spec["openstax"]
            if openstax is None:
                res["error"] = "OpenStax API unavailable"
                return res
            book = openstax.get(slug_)
            res["matched"] = bool(book and book["title"] == title and book.get("book_state") == "live")
            res["evidence"] = (f"API: slug={slug_!r} title={book['title']!r} state={book.get('book_state')!r}"
                               if book else f"slug {slug_!r} not in API listing")
            return res
        res["method"] = "page fetch"
        status, final, body, err = http_get(c["url"])
        if status != 200:
            res["error"] = err or f"HTTP {status}"
            return res
        title = page_title(body)
        text = page_text(body).lower() if "body" in spec else ""
        ok_title = all(s.lower() in title.lower() for s in spec.get("title", []))
        ok_body = all(s.lower() in text for s in spec.get("body", []))
        res["matched"] = ok_title and ok_body
        res["final_url"] = final
        res["evidence"] = f"HTTP 200; title={title[:120]!r}" + (f"; text contains {spec['body']}" if spec.get("body") and ok_body else "")
        if not res["matched"]:
            res["error"] = "expected title/text not found"
        return res
    except Exception as e:  # noqa: BLE001
        res["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        return res


def verify_courses() -> None:
    today = dt.date.today().isoformat()
    openstax = None
    status, _f, body, err = http_get(OPENSTAX_API)
    if status == 200:
        try:
            openstax = {it["meta"]["slug"]: {"title": it["title"], "book_state": it.get("book_state")}
                        for it in json.loads(body).get("items", [])}
        except Exception as e:  # noqa: BLE001
            print(f"  ! OpenStax API parse error: {e}", file=sys.stderr)
    else:
        print(f"  ! OpenStax API unavailable: {err}", file=sys.stderr)
    todo = [c for c in COURSES if c["check"]]
    print(f"verifying {len(todo)} course pages (network)...")
    results = {}
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(check_course, c, openstax, today): c["id"] for c in todo}
        for fut in cf.as_completed(futs):
            results[futs[fut]] = fut.result()
    ok = sum(1 for r in results.values() if r["matched"])
    for cid in sorted(results):
        r = results[cid]
        if not r["matched"]:
            print(f"  - not verified: {cid}: {r.get('error') or r.get('evidence')}")
    write_json(COURSE_CHECKS, {
        "description": "Evidence log for data/processed/courses.json: each listing's exact page was fetched on 'checked'. Written by data/build_processed.py --verify-courses.",
        "checked": today,
        "user_agent": "desktop browser UA string (scripted urllib request)",
        "summary": {"checked": len(results), "matched": ok},
        "checks": {k: results[k] for k in sorted(results)},
    })
    print(f"verified {ok}/{len(results)} course pages -> {COURSE_CHECKS.relative_to(ROOT)}")


# --------------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------------
def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verify-courses", action="store_true", help="re-check course pages online before building")
    args = ap.parse_args()

    if args.verify_courses:
        verify_courses()

    on = Onet()
    on.check_traits()
    traits = build_traits(on)
    occupations = build_occupations(on)
    skills = build_skills(on)
    skill_ids = {s["id"] for s in skills}
    careers = build_careers(on, occupations, skill_ids)
    courses = build_courses(skill_ids)
    jobs = build_jobs(on, skill_ids)
    sources = build_sources(on, courses)
    schemas = build_schemas(careers, traits)

    write_json(PROCESSED / "traits.json", traits)
    write_json(PROCESSED / "occupations.json", occupations)
    write_json(PROCESSED / "skills.json", skills)
    write_json(PROCESSED / "courses.json", courses)
    write_json(PROCESSED / "jobs.json", jobs)
    write_json(PROCESSED / "careers.json", careers)
    write_json(SOURCES_DIR / "onet.json", sources)
    for name, schema in schemas.items():
        write_json(SCHEMAS / f"{name}.schema.json", schema)

    cs = collections.Counter(c["status"] for c in courses)
    hs = collections.Counter(c["hours_status"] for c in courses)
    ks = collections.Counter(s["source"] for s in skills)
    preserved = [c["id"] for c in careers if c.get("wage") is not None or c.get("outlook") is not None]
    print("built data/processed (O*NET 31.0, universe", len(on.universe), "occupations with complete Work Styles):")
    print(f"  traits.json       {len(traits)} work styles")
    print(f"  occupations.json  {len(occupations['occupations'])} occupations (REAL, percentile-normalized)")
    print(f"  careers.json      {len(careers)} careers, {sum(len(c['coworkers']) for c in careers)} fictional coworkers"
          + (f"; wage/outlook preserved for {preserved}" if preserved else "; wage/outlook null (not filled yet)"))
    print(f"  skills.json       {len(skills)} skills {dict(ks)}")
    print(f"  courses.json      {len(courses)} resources status={dict(cs)} hours_status={dict(hs)}")
    print(f"  jobs.json         {len(jobs)} job nodes (SAMPLE)")
    print(f"  sources/onet.json {len(sources)} source records")
    print(f"  schemas           {', '.join(sorted(schemas))}")
    if not COURSE_CHECKS.exists():
        print("  note: no course check log yet; run with --verify-courses to verify course pages (all SAMPLE until then)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
