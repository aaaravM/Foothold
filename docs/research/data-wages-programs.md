# Foothold research: Stockton-Lodi wages, outlook, programs and costs

Retrieved: **2026-10-24** (`date` on research machine: Sat Oct 24 2026, PDT). Area: Stockton-Lodi MSA = San Joaquin County, CA (BLS area code 44700).

Status legend: **REAL** = read by us from the official page/file/API on the retrieval date. **SAMPLE** = not read from an official page; verify at the given URL before showing as fact. **DERIVED** = computed by us from REAL values (formula given). **NOT_READ** = official source blocked our fetch.

Machine-readable files (owned by this research task):

| File | What it is |
|---|---|
| `data/raw/wages/wages.json` | Clean per-SOC wages + projections (schema `foothold.wages.v1`) |
| `data/raw/wages/edd_oews_stockton_raw.json` | Raw CKAN response: EDD OEWS rows, Stockton-Lodi MSA, 2025 Q1 + 2026 Q1, 12 SOCs + all-occupations |
| `data/raw/wages/edd_oews_173024_raw.json` | Raw CKAN response: 17-3024 for California and Sacramento MSA (not published for Stockton) |
| `data/raw/wages/edd_projections_stockton_ca_raw.json` | Raw CKAN response: EDD long-term projections, Stockton-Lodi MSA (2023-2033) + California (2024-2034) |
| `data/raw/programs/programs_raw.json` | Clean fees, career-to-program map (Delta + MJC), apprenticeship, transfer tuition, tools (schema `foothold.programs.v1`) |
| `data/raw/programs/delta_program_mapper_parsed.json`, `mjc_program_mapper_parsed.json` | Parsed program-mapper pages (title, award, units, terms, control number, TOP code) |
| `data/raw/programs/scorecard_{delta,mjc,csustan,csus,fresnostate,ucmerced}.json` | Raw College Scorecard API responses (DEMO_KEY) |

## 1. Key findings for builders

- **BLS blocked scripts, so wages come from CA EDD.** On 2026-10-24 every BLS host returned 403 or a 503 bot page to scripts: www.bls.gov (May 2025 pages and zips), data.bls.gov, api.bls.gov and download.bls.gov.
  - `https://www.bls.gov/oes/current/oes_44700.htm` now redirects to `https://www.bls.gov/oes/tables.htm`. The May 2025 MSA table moved to a JavaScript app: `https://data.bls.gov/oes/#/area/0044700/2025` (BLS index page, last modified 2026-05-15).
  - **We used CA EDD OEWS instead.** EDD is the state partner in the BLS OEWS program. Its employment figures are the May 2025 estimates. Its wages are "updated to the first quarter of 2026" using the US DOL Employment Cost Index (EDD OEWS page). All wage values below are REAL EDD values.
- **17-3024 (mechatronics technicians) has no Stockton-Lodi wage or projection.** EDD returned no row. Show the Sacramento MSA or California fallback, labeled as non-local.
- **Fees.** The CA community college enrollment fee is **$46 per unit** (Delta College fee page, which says the CA Legislature sets it). One academic year at 30 units comes to about $1,380 in enrollment fees (DERIVED: 30 x 46), plus Delta per-semester fees.
  - CSU Fall 2026 tuition is **$3,419 per semester** for undergraduates taking more than 6 units, the same on all three campus pages. Campus totals differ: Stanislaus State $4,815, Fresno State $4,317.50, Sacramento State $4,828.
- **Electrical apprenticeship near Stockton:** SJETI (San Joaquin & Calaveras Counties Electrical JATC). It runs **60 months**, starts at $21.35/hr and is tuition-free (DIR DAS listing and sjeti.org).
- **Program maps:** Delta `https://programmap.deltacollege.edu/` and MJC `https://programmap.mjc.edu/` both run the CCC "Program Pathways Mapper". It has stable URL patterns: `/category/<slug>/` and `/program/<slug>/`. Each program page shows units, terms, award type, a CCC program control number and a TOP code.

## 2. Wages: Stockton-Lodi MSA (CA EDD OEWS, 2026 Q1 wages / May 2025 employment)

Source: CA EDD OEWS dataset on data.ca.gov (https://data.ca.gov/dataset/oews), resource `aef4c53a-7e17-418c-acc1-d189e39b6caa`, Area Name = `Stockton-Lodi MSA`, Year = 2026, Quarter = `1st Qtr`, Industry = Total. Methodology: https://labormarketinfo.edd.ca.gov/data/oes-employment-and-wages.html. All-areas file for manual verification: https://labormarketinfo.edd.ca.gov/file/occup$/oeswages/all-oews-2026.zip. Status of every value in this table: **REAL**; retrieved 2026-10-24.

| SOC | Foothold role | EDD title | Employment | Median $/hr | P25 $/hr | P75 $/hr | Median $/yr | P25 $/yr | P75 $/yr | Mean $/yr | RSE % |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 00-0000 | baseline | Total all occupations | 289,660 | 24.08 | 19.42 | 36.90 | 50,089.32 | 40,396.59 | 76,754.54 | 66,407.45 | 0.4 |
| 53-1047 | Logistics lead (first-line supervisor, transportation/material moving) | First-Line Supervisors of Transportation and Material Moving Workers, Except Aircraft Cargo Handling Supervisors | 2,440 | 36.34 | 27.53 | 38.50 | 75,589.20 | 57,246.28 | 80,095.74 | 72,390.69 | 0.7 |
| 13-1081 | Logistics lead (logistician; usually BA-level) | Logisticians | 350 | 37.43 | 29.68 | 47.87 | 77,844.41 | 61,728.50 | 99,572.92 | 83,670.54 | 1.3 |
| 29-1141 | Registered nurse | Registered Nurses | 5,460 | 66.51 | 60.61 | 82.55 | 138,347.28 | 126,073.04 | 171,695.37 | 149,470.16 | 0.6 |
| 49-3031 | Diesel mechanic | Bus and Truck Mechanics and Diesel Engine Specialists | 760 | 34.81 | 26.17 | 38.99 | 72,400.82 | 54,436.86 | 81,089.74 | 70,529.36 | 1.4 |
| 49-3042 | Heavy equipment mechanic | Mobile Heavy Equipment Mechanics, Except Engines | 530 | 36.59 | 27.41 | 40.22 | 76,092.33 | 57,007.55 | 83,660.43 | 73,449.66 | 3.3 |
| 49-3041 | Farm equipment mechanic | Farm Equipment Mechanics and Service Technicians | 250 | 25.58 | 22.64 | 37.61 | 53,213.21 | 47,084.70 | 78,241.42 | 61,346.87 | 2.8 |
| 51-4121 | Welder | Welders, Cutters, Solderers, and Brazers | 740 | 25.31 | 23.71 | 30.31 | 52,654.67 | 49,320.29 | 63,036.27 | 58,198.35 | 1.1 |
| 47-2111 | Electrician | Electricians | 1,180 | 37.74 | 28.95 | 50.59 | 78,480.00 | 60,218.33 | 105,225.44 | 85,084.19 | 3.8 |
| 15-1252 | Software developer | Software Developers | 570 | 68.47 | 59.57 | 87.57 | 142,428.41 | 123,914.26 | 182,160.33 | 151,772.86 | 2 |
| 11-9013 | Farm/ranch/ag manager | Farmers, Ranchers, and Other Agricultural Managers | 100 | 49.85 | 44.96 | 64.77 | 103,701.04 | 93,523.10 | 134,712.72 | 118,464.63 | 5.5 |
| 17-3024 | Mechatronics / electro-mechanical technician | Electro-Mechanical and Mechatronics Technologists and Technicians | not published for Stockton-Lodi | | | | | | | | |
| 53-7062 | Warehouse baseline (hand laborers and material movers) | Laborers and Freight, Stock, and Material Movers, Hand | 15,030 | 23.25 | 20.63 | 27.67 | 48,366.05 | 42,909.16 | 57,563.06 | 48,907.66 | 0.5 |

Fallbacks for 17-3024 (EDD OEWS 2026 Q1; REAL; use with a "regional/statewide" label):

| Area | Employment | Median $/hr | P25 $/hr | P75 $/hr | Median $/yr | P25 $/yr | P75 $/yr | RSE % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Sacramento-Roseville-Folsom MSA | 40 | 38.85 | 35.25 | 47.14 | 80,789.96 | 73,316.45 | 98,049.96 | 3.2 |
| California | 1,850 | 40.31 | 35.14 | 52.15 | 83,832.82 | 73,080.01 | 108,463.53 | 2.5 |

Prior release (EDD 2025 Q1 wages / May 2024 employment), useful for showing a trend. Also stored in `wages.json` under `wages_prior_year`:

| SOC | Employment | Median $/hr | Median $/yr |
|---|---:|---:|---:|
| 53-1047 | 2,380 | 33.68 | 70,052.52 |
| 13-1081 | 330 | 36.83 | 76,614.68 |
| 29-1141 | 5,100 | 65.11 | 135,423.05 |
| 49-3031 | 650 | 32.64 | 67,871.94 |
| 49-3042 | 510 | 35.22 | 73,263.49 |
| 49-3041 | 190 | 23.74 | 49,396.88 |
| 51-4121 | 610 | 24.83 | 51,647.53 |
| 47-2111 | 1,160 | 37.02 | 76,998.65 |
| 15-1252 | 580 | 63.43 | 131,930.65 |
| 11-9013 | 80 | 55.18 | 114,779.43 |
| 53-7062 | 16,860 | 22.68 | 47,179.69 |

BLS cross-check (NOT_READ). For each SOC a user can verify the federal May 2025 values (median hourly/annual, employment) at `https://data.bls.gov/oes/#/area/0044700/2025`, or in `https://www.bls.gov/oes/special-requests/oesm25ma.zip` (MSA XLSX). BLS asks automated clients to follow its usage policy. In a browser it works normally.

## 3. Outlook: EDD long-term occupational projections

Source: https://data.ca.gov/dataset/long-term-occupational-employment-projections, resource `274e273c-d18c-4d84-b8df-49b4d13c14ce` (EDD page: https://labormarketinfo.edd.ca.gov/data/employment-projections.html). Local area = `Stockton-Lodi MSA (San Joaquin County)`, period **2023-2033**. Statewide = `California`, period **2024-2034**. "Total openings" covers the 10-year period (exits + transfers + growth). "Annual avg openings" = total / 10 (**DERIVED**). Other columns are **REAL**.

| SOC | Title | Base emp | Projected emp | Change | Growth % | Total openings (10 yr) | Annual avg openings (DERIVED) | Entry education | Training |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 00-0000 | Total, All Occupations (Stockton-Lodi) | 302,430 | 324,190 | 21,760 | 7.2 | 380,160 | 38,016 | | |
| 53-1047 | FirstLine Supervisors of Transportation & Material Moving Workers, Exc Aircraft Cargo Handling Supervisor | 2,330 | 2,610 | 280 | 12.0 | 2,690 | 269 | High school diploma or equivalent | None |
| 13-1081 | Logisticians | 350 | 440 | 90 | 25.7 | 410 | 41 | Bachelor's degree | None |
| 29-1141 | Registered Nurses | 4,880 | 5,280 | 400 | 8.2 | 3,010 | 301 | Bachelor's degree | None |
| 49-3031 | Bus and Truck Mechanics and Diesel Engine Specialists | 690 | 750 | 60 | 8.7 | 650 | 65 | High school diploma or equivalent | Long-term on-the-job training |
| 49-3042 | Mobile Heavy Equipment Mechanics, Except Engines | 550 | 610 | 60 | 10.9 | 530 | 53 | High school diploma or equivalent | Long-term on-the-job training |
| 49-3041 | Farm Equipment Mechanics and Service Technicians | 260 | 280 | 20 | 7.7 | 240 | 24 | High school diploma or equivalent | Long-term on-the-job training |
| 51-4121 | Welders, Cutters, Solderers, and Brazers | 650 | 700 | 50 | 7.7 | 710 | 71 | High school diploma or equivalent | Moderate-term on-the-job training |
| 47-2111 | Electricians | 1,200 | 1,510 | 310 | 25.8 | 1,490 | 149 | High school diploma or equivalent | Apprenticeship |
| 15-1252 | Software Developers | 590 | 690 | 100 | 16.9 | 430 | 43 | Bachelor's degree | None |
| 11-9013 | Farmers, Ranchers, and Other Agricultural Managers | 2,120 | 1,950 | -170 | -8.0 | 1,980 | 198 | High school diploma or equivalent | None |
| 17-3024 | Electro-Mechanical and Mechatronics Technologists and Technicians (**California 2024-2034**; no Stockton row) | 1,900 | 2,000 | 100 | 5.3 | 1,700 | 170 | Associate's degree | None |
| 53-7062 | Laborers and Freight, Stock, and Material Movers, Hand | 16,510 | 17,910 | 1,400 | 8.5 | 23,630 | 2,363 | No formal educational credential | Short-term on-the-job training |

California statewide 2024-2034 growth % for comparison (REAL): 53-1047 10.0%; 13-1081 19.5%; 29-1141 13.5%; 49-3031 5.1%; 49-3042 6.8%; 49-3041 5.4%; 51-4121 3.2%; 47-2111 14.9%; 15-1252 18.4%; 11-9013 -2.5%; 17-3024 5.3%; 53-7062 8.6%.

## 4. Community college fees (official)

| Item | Value | Unit | Source | Status |
|---|---:|---|---|---|
| CA community college enrollment fee (residents) | 46 | USD per semester unit (California residents) | https://www.deltacollege.edu/admission-aid/tuition-fees | REAL |
| Delta: Nonresident tuition (effective Summer 2026) | 328 | USD per unit, plus $46/unit enrollment fee | https://www.deltacollege.edu/admission-aid/tuition-fees | REAL |
| Delta: Student activity fee (Mustang Pass) | 10 | USD per semester | https://www.deltacollege.edu/admission-aid/tuition-fees | REAL |
| Delta: Student representation fee | 2 | USD per semester | https://www.deltacollege.edu/admission-aid/tuition-fees | REAL |
| Delta: Student health fee | 26 | USD per semester (22 for summer) | https://www.deltacollege.edu/admission-aid/tuition-fees | REAL |
| Delta: Parking permit (automobile) | 30 | USD per semester | https://www.deltacollege.edu/admission-aid/tuition-fees | REAL |
| Delta: Course audit | 15 | USD per unit | https://www.deltacollege.edu/admission-aid/tuition-fees | REAL |

The statute is Ed. Code section 76300 (https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=EDC&sectionNum=76300). leginfo returned 403 to both curl and WebFetch, so we did **not** read the statute text. The $46 figure is REAL from the Delta College official fee page. That page says the fee "is approved by the California State Legislature." Fee waiver programs exist (e.g. California College Promise Grant) but we did not verify their terms in this pass, so they are UNVERIFIED.

## 5. Programs by career (San Joaquin Delta College primary, Modesto Junior College alternate)

Source: each college's Program Pathways Mapper page (URL in table). Delta maps are catalog year **2025-2026**; the Delta site banner says 2026-2027 maps are coming soon. MJC maps are catalog year **2026-2027**. "Terms" is the mapper's "N terms to degree"; MJC term counts appear to include summer/winter sessions (e.g. 12-13 terms for ADN), so do not convert terms to years without care. "Est. enrollment fees" = units x $46 (**DERIVED**; excludes per-semester fees, books, tools and program fees). Every other column is **REAL**, retrieved 2026-10-24.

| SOC | College | Program (pathway) | Award | Units | Terms | Est. enrollment fees $ (DERIVED) | Control # | TOP | URL |
|---|---|---|---|---|---|---|---|---|---|
| 29-1141 | Delta | Nursing R.N. - Major Courses Only | Associate in Science | 36.5 units | 4 terms | 1,679 | 05623 | 1230.10 | https://programmap.deltacollege.edu/program/nursing-r-n/ |
| 29-1141 | Delta | Nursing R.N. - Pre-Nursing Prereqs & Additional Courses | Associate in Science | 47-50 units | 4 terms | 2,162-2,300 | 05623 | 1230.10 | https://programmap.deltacollege.edu/program/nursing-r-n/ |
| 29-1141 | Delta | Nurse Assistant and Home Health Aide Certificate of Completion (Noncredit) | Certificate of Completion (noncredit) | n/a | n/a | n/a | 45195 | 1230.30 | https://programmap.deltacollege.edu/program/nurse-assistant-and-home-health-aide/ |
| 29-1141 | MJC | Nursing: ADN Program (RN) - LVN Certified already to Nursing Program | Associate of Science | 95-101 units | 12 terms | 4,370-4,646 | 06678 | 1230.10 | https://programmap.mjc.edu/program/nursing-adn-program-rn/ |
| 29-1141 | MJC | Nursing: ADN Program (RN) - Prereq with Nursing Program Coursework | Associate of Science | 105.5 units | 13 terms | 4,853 | 06678 | 1230.10 | https://programmap.mjc.edu/program/nursing-adn-program-rn/ |
| 29-1141 | MJC | Nursing: ADN Program (RN) - Nurs. Prereq & CSU GE Cert for RN Prog Appl | Associate of Science | 69.5 units | 9 terms | 3,197 | 06678 | 1230.10 | https://programmap.mjc.edu/program/nursing-adn-program-rn/ |
| 51-4121 | Delta | Welding Technology | Certificate of Achievement | 42.5 units | 3 terms | 1,955 | 07426 | 0956.50 | https://programmap.deltacollege.edu/program/welding-technology/ |
| 51-4121 | Delta | Oxy-Fuel Processes and Shielded Metal Arc Welding (SMAW) | Certificate of Achievement | 20 units | 2 terms | 920 | 36597 | 0956.50 | https://programmap.deltacollege.edu/program/oxy-fuel-processes-and-shielded-metal-arc-welding-smaw/ |
| 51-4121 | Delta | Gas Metal Arc Welding (GMAW)/Flux Core Arc Welding (FCAW) | Certificate of Achievement | 20 units | 2 terms | 920 | 36608 | 0956.50 | https://programmap.deltacollege.edu/program/gas-metal-arc-welding-gmaw-flux-core-arc-welding-fcaw/ |
| 51-4121 | MJC | Welding | Associate of Science | 61.5-63 units | 6 terms | 2,829-2,898 | 06668 | 0956.50 | https://programmap.mjc.edu/program/welding/ |
| 49-3031 | Delta | Diesel Equipment Technician | Certificate of Achievement | 42.5 units | 5 terms | 1,955 | 22252 | 0947.00 | https://programmap.deltacollege.edu/program/diesel-equipment-technician/ |
| 49-3031 | Delta | Diesel Equipment Technician | Associate in Science | 66.5 units | 5 terms | 3,059 | 07420 | 0947.00 | https://programmap.deltacollege.edu/program/diesel-equipment-technician-2/ |
| 49-3031 | Delta | Diesel Bus Technician | Certificate of Achievement | 32.5 units | 4 terms | 1,495 | 37671 | 0947.00 | https://programmap.deltacollege.edu/program/diesel-bus-technician/ |
| 49-3042 | Delta | Heavy Equipment Technician | Certificate of Achievement | 31 units | 3 terms | 1,426 | 22253 | 0947.20 | https://programmap.deltacollege.edu/program/heavy-equipment-technician-2/ |
| 49-3042 | Delta | Heavy Equipment Technician | Associate in Science | 60-69 units | 5 terms | 2,760-3,174 | 14147 | 0947.20 | https://programmap.deltacollege.edu/program/heavy-equipment-technician/ |
| 49-3042 | Delta | Heavy Equipment Mechanic | Certificate of Achievement | 24 units | 3 terms | 1,104 | 14146 | 0947.20 | https://programmap.deltacollege.edu/program/heavy-equipment-mechanic/ |
| 49-3042 | Delta | Caterpillar Dealer Service Technician Apprenticeship | Associate in Science | 81 units | 5 terms | 3,726 | 14290 | 0947.20 | https://programmap.deltacollege.edu/program/caterpillar-dealer-service-technician-apprenticeship/ |
| 49-3042 | MJC | Basic Heavy Equipment Technician | Certificate of Achievement | 18 units | 1 term | 828 | 36013 | 0116.00 | https://programmap.mjc.edu/program/basic-heavy-equipment-technician/ |
| 49-3042 | MJC | Advanced Heavy Equipment Technician | Certificate of Achievement | 16 units | 2 terms | 736 | 19348 | 0116.00 | https://programmap.mjc.edu/program/advanced-heavy-equipment-technician/ |
| 49-3041 | Delta | Agriculture Mechanics | Certificate of Achievement | 16.5 units | 2 terms | 759 | 05581 | 0103.00 | https://programmap.deltacollege.edu/program/agriculture-mechanics/ |
| 49-3041 | MJC | Mechanized Agriculture Technician | Certificate of Achievement | 30 units | 3 terms | 1,380 | 30509 | 0116.00 | https://programmap.mjc.edu/program/mechanized-agriculture-technician/ |
| 49-3041 | MJC | Agriculture Mechanics | Associate of Science | 61-66 units | 5 terms | 2,806-3,036 | 06642 | 0116.00 | https://programmap.mjc.edu/program/agriculture-mechanics/ |
| 47-2111 | Delta | Electrical Technology - General Electrician Trainee | Certificate of Achievement | 43 units | 4 terms | 1,978 | 35073 | 0952.20 | https://programmap.deltacollege.edu/program/electrical-technology-general-electrician-trainee/ |
| 47-2111 | Delta | Electrical Technology | Associate in Science | 67-76 units | 5 terms | 3,082-3,496 | 35059 | 0952.20 | https://programmap.deltacollege.edu/program/electrical-technology/ |
| 47-2111 | Delta | Electrical Technology - Electrical Maintenance | Certificate of Achievement | 30-33 units | 3 terms | 1,380-1,518 | 07402 | 0952.20 | https://programmap.deltacollege.edu/program/electrical-technology-electrical-maintenance/ |
| 47-2111 | MJC | Electrician | Certificate of Achievement | 34 units | 4 terms | 1,564 | 35084 | 0952.20 | https://programmap.mjc.edu/program/electrician/ |
| 17-3024 | Delta | Automation Technician - Mechatronics | Certificate of Achievement | 33.5 units | 3 terms | 1,541 | 35052 | 0935.00 | https://programmap.deltacollege.edu/program/automation-technician-mechatronics/ |
| 17-3024 | Delta | Automation Technology - Mechatronics | Associate in Science | 60 units | 4 terms | 2,760 | 35050 | 0935.00 | https://programmap.deltacollege.edu/program/automation-technology-mechatronics/ |
| 17-3024 | Delta | Electronics Technology | Certificate of Achievement | 21-22 units | 2 terms | 966-1,012 | 07403 | 0934.00 | https://programmap.deltacollege.edu/program/electronics-technology/ |
| 17-3024 | Delta | Control Systems Technician Certificate of Completion (Noncredit) | Certificate of Completion (noncredit) | n/a | n/a | n/a | 45193 | 0935.00 | https://programmap.deltacollege.edu/program/control-systems-technician/ |
| 17-3024 | Delta | Basic Electronics Technician Certificate of Completion (Noncredit) | Certificate of Completion (noncredit) | n/a | n/a | n/a | 45194 | 0934.00 | https://programmap.deltacollege.edu/program/basic-electronics-technician/ |
| 17-3024 | MJC | Automation Technician | Certificate of Achievement | 19 units | 2 terms | 874 | 45106 | 0934.20 | https://programmap.mjc.edu/program/automation-technician/ |
| 17-3024 | MJC | Electro-Mechanic | Certificate of Achievement | 35 units | 4 terms | 1,610 | 35237 | 0943.00 | https://programmap.mjc.edu/program/electro-mechanic/ |
| 17-3024 | MJC | Industrial Electronics | Certificate of Achievement | 34 units | 4 terms | 1,564 | 20310 | 0934.20 | https://programmap.mjc.edu/program/industrial-electronics-2/ |
| 17-3024 | MJC | Industrial Electronics | Associate of Science | 58.5-59 units | 5 terms | 2,691-2,714 | 08129 | 0934.20 | https://programmap.mjc.edu/program/industrial-electronics/ |
| 15-1252 | Delta | Computer Science | Associate in Science for Transfer | 63-64 units | 5 terms | 2,898-2,944 | 33018 | 0706.00 | https://programmap.deltacollege.edu/program/computer-science-2/ |
| 15-1252 | Delta | Computer Science | Associate in Science | 60-61 units | 4 terms | 2,760-2,806 | 07304 | 0702.00 | https://programmap.deltacollege.edu/program/computer-science/ |
| 15-1252 | Delta | Computer Science | Certificate of Achievement | 50.5-53.5 units | 4 terms | 2,323-2,461 | 22247 | 0702.00 | https://programmap.deltacollege.edu/program/computer-science-3/ |
| 15-1252 | Delta | Computer Programming | Certificate of Achievement | 44.5-48.5 units | 4 terms | 2,047-2,231 | 05594 | 0707.10 | https://programmap.deltacollege.edu/program/computer-programming/ |
| 15-1252 | MJC | Computer Science for Transfer Degree - Two-Year Plan | Associate of Science for Transfer | 68-75 units | 6 terms | 3,128-3,450 | 33672 | 0706.00 | https://programmap.mjc.edu/program/computer-science-for-transfer-degree/ |
| 15-1252 | MJC | Computer Science for Transfer Degree - Three Year Plan | Associate of Science for Transfer | 69-74 units | 8 terms | 3,174-3,404 | 33672 | 0706.00 | https://programmap.mjc.edu/program/computer-science-for-transfer-degree/ |
| 15-1252 | MJC | Computer Science for Transfer Degree - Calculus & Physics Ready | Associate of Science for Transfer | 59-64 units | 6 terms | 2,714-2,944 | 33672 | 0706.00 | https://programmap.mjc.edu/program/computer-science-for-transfer-degree/ |
| 15-1252 | MJC | Computer Science - Information Systems | Associate of Science | 60.5-63.5 units | 7 terms | 2,783-2,921 | 06655 | 0706.00 | https://programmap.mjc.edu/program/computer-science/ |
| 15-1252 | MJC | Computer Science - Programming | Associate of Science | 60.5-63.5 units | 7 terms | 2,783-2,921 | 06655 | 0706.00 | https://programmap.mjc.edu/program/computer-science/ |
| 15-1252 | MJC | Computer Science - Networking | Associate of Science | 60-61 units | 7 terms | 2,760-2,806 | 06655 | 0706.00 | https://programmap.mjc.edu/program/computer-science/ |
| 11-9013 | Delta | Agriculture Business | Certificate of Achievement | 59-61 units | 4 terms | 2,714-2,806 | 22243 | 0112.00 | https://programmap.deltacollege.edu/program/agriculture-business/ |
| 11-9013 | Delta | Agriculture Plant Science | Associate in Science for Transfer | 60-61.5 units | 4 terms | 2,760-2,829 | 37666 | 0103.00 | https://programmap.deltacollege.edu/program/agriculture-plant-science/ |
| 11-9013 | MJC | Agriculture Business for Transfer Degree | Associate of Science for Transfer | 60-62 units | 5 terms | 2,760-2,852 | 35537 | 0112.00 | https://programmap.mjc.edu/program/agriculture-business-for-transfer-degree/ |
| 53-1047 | Delta | Logistics and Transportation Supervisor | Certificate of Achievement | 24 units | 2 terms | 1,104 | 05588 | 0510.00 | https://programmap.deltacollege.edu/program/logistics-and-transportation-supervisor/ |
| 53-1047 | Delta | Traffic Shipping and Receiving Technician | Certificate of Achievement | 15-16 units | 1 term | 690-736 | 11844 | 0510.00 | https://programmap.deltacollege.edu/program/traffic-shipping-and-receiving-technician/ |
| 53-1047 | Delta | Logistics and Transportation | Associate in Science | 60-64 units | 4 terms | 2,760-2,944 | 19693 | 0510.00 | https://programmap.deltacollege.edu/program/logistics-and-transportation/ |
| 53-1047 | MJC | Logistics and Supply Chain Management | Certificate of Achievement | 24-30 units | 3 terms | 1,104-1,380 | 35013 | 0510.00 | https://programmap.mjc.edu/program/logistics-and-supply-chain-management-2/ |
| 53-1047 | MJC | Logistics and Supply Chain Management | Associate of Science | 56-60 units | 6 terms | 2,576-2,760 | 35012 | 0510.00 | https://programmap.mjc.edu/program/logistics-and-supply-chain-management/ |
| 13-1081 | Delta | Logistics and Transportation | Associate in Science | 60-64 units | 4 terms | 2,760-2,944 | 19693 | 0510.00 | https://programmap.deltacollege.edu/program/logistics-and-transportation/ |
| 13-1081 | Delta | Business Administration for Transfer 2.0 | Associate in Science for Transfer | 60-64 units | 4 terms | 2,760-2,944 | 43281 | 0505.00 | https://programmap.deltacollege.edu/program/business-administration-for-transfer-2-0/ |
| 13-1081 | MJC | Logistics and Supply Chain Management | Associate of Science | 56-60 units | 6 terms | 2,576-2,760 | 35012 | 0510.00 | https://programmap.mjc.edu/program/logistics-and-supply-chain-management/ |
| 53-7062 | Delta | Traffic Shipping and Receiving Technician | Certificate of Achievement | 15-16 units | 1 term | 690-736 | 11844 | 0510.00 | https://programmap.deltacollege.edu/program/traffic-shipping-and-receiving-technician/ |

Notes:

- Delta Nursing R.N. (ADN) has a special-admission process ("Refer to the catalog for information about programs with Special Admission Requirements" on the mapper page). Two pathways are shown: 36.5 units for major courses only, or 47-50 units including pre-nursing prerequisites.
- We found no MJC diesel program in the MJC categories we checked (School of Agriculture, School of Industry and Trade). MJC heavy-equipment certificates are listed under 49-3042.
- Delta also lists an *Industrial Technology: Electrical Apprenticeship* and *Electrical Technology: Apprenticeship* (category page `https://programmap.deltacollege.edu/category/technical-careers-and-trades/`); we did not open those pages.

## 6. Registered electrical apprenticeship near Stockton

| Field | Value | Source | Status |
|---|---|---|---|
| Program | San Joaquin & Calaveras Counties Electrical J.A.T.C. (SJETI) | https://www.dir.ca.gov/databases/das/results_aigdetail.asp?varOccId=9810 | REAL |
| Occupation | Electrician-Inside Wireman | https://www.dir.ca.gov/databases/das/results_aigdetail.asp?varOccId=9810 | REAL |
| Length | 60 months (sjeti.org: 5 years) | https://www.dir.ca.gov/databases/das/results_aigdetail.asp?varOccId=9810 ; https://sjeti.org/ | REAL |
| Starting wage | $21.35/hr | https://www.dir.ca.gov/databases/das/results_aigdetail.asp?varOccId=9810 | REAL |
| Related classroom training | ~200 hours/year; tuition-free | https://sjeti.org/ | REAL |
| Min age / education | 18; High school diploma/GED/equivalent; one year of HS algebra (C or better) or one semester of college algebra (C or better) | https://www.dir.ca.gov/databases/das/results_aigdetail.asp?varOccId=9810 | REAL |
| Exams | Written test and oral exam; drug screen (cost borne by JATC) | https://www.dir.ca.gov/databases/das/results_aigdetail.asp?varOccId=9810 | REAL |
| Union affiliation | IBEW Local 595 (site menu and copy) | https://sjeti.org/ | REAL |
| Address / phone | 1531 El Pinal Drive, Stockton, CA 95205; (209) 462-0751 | https://www.dir.ca.gov/databases/das/results_aigdetail.asp?varOccId=9810 | REAL |
| Apply | https://sjeti.org/applicants/application-process/ ; https://sjeti.org/applicants/application/ | https://sjeti.org/ | REAL |

DIR DAS says its listing data was "current as of 10/24/2026". The sponsor-trust and NECA chapter details appeared only in a search summary and are not used here.

## 7. Transfer targets: tuition (official campus pages) and College Scorecard

| Institution | Term / basis | Tuition fee >6 units | Total incl. campus fees >6 units | Total 0-6 units | Source | Status |
|---|---|---:|---:|---:|---|---|
| California State University, Stanislaus (Turlock) | Fall 2026, per semester, undergraduate, CA resident | $3,419.00 | $4,815.00 | $3,257.00 | https://www.csustan.edu/tuition-fees/fee-schedules-deadlines#fall-26 | REAL |
| California State University, Fresno | Fall 2026, per semester, undergraduate, CA resident | $3,419.00 | $4,317.50 | $2,879.50 | https://adminfinance.fresnostate.edu/accountingservices/students/tuitionfees.html | REAL |
| California State University, Sacramento | Fall 2026 & Spring 2027, per semester, undergraduate, CA resident | $3,419.00 | $4,828.00 | $3,390.00 | https://www.csus.edu/administration-business-affairs/bursar/tuition-living-costs.html | REAL |
| UC system (applies to UC Merced) | 2027-28 new CA resident, per year, systemwide average | UC Tuition $16,278 (tuition + student services fee) | + campus fees avg $1,900; total cost on campus $49,078 | | https://admission.universityofcalifornia.edu/tuition-financial-aid/tuition-cost-of-attendance/ | REAL |
| UC Merced campus-specific | 2026-27, per semester | $7,101 tuition + $693 SSF + $668 campus fees | $8,462 | | https://studentbilling.ucmerced.edu/tuition-fees/tuition | **SAMPLE** (page 403 to us) |

CSU systemwide tuition 2026-27 = **$6,838/yr** (DERIVED: 2 x $3,419, the same Fall 2026 tuition fee on all three campus pages). The official CSU page (https://www.calstate.edu/attend/paying-for-college/csu-costs/tuition-and-fees/Pages/future-tuition-and-fees.aspx) returned 403/404 to us. Nonresident tuition: $471/unit (Fresno State, Sacramento State pages; REAL).

College Scorecard API (raw JSON saved; REAL; the API does not say which academic year "latest" refers to):

| School | UNITID | In-state tuition $ | Out-of-state tuition $ | Avg net price (public) $ | COA (academic yr) $ | Raw file |
|---|---:|---:|---:|---:|---:|---|
| San Joaquin Delta College | 122658 | 1,180 | 9,772 | 2,451 | 12,334 | `data/raw/programs/scorecard_delta.json` |
| Modesto Junior College | 118976 | 1,276 | 8,918 | 5,954 | 16,086 | `data/raw/programs/scorecard_mjc.json` |
| California State University-Stanislaus | 110495 | 8,690 | 22,010 | 3,565 | 17,570 | `data/raw/programs/scorecard_csustan.json` |
| California State University-Fresno | 110556 | 8,224 | 21,544 | 5,418 | 19,585 | `data/raw/programs/scorecard_fresnostate.json` |
| California State University-Sacramento | 110617 | 9,014 | 22,334 | 11,186 | 25,925 | `data/raw/programs/scorecard_csus.json` |
| University of California-Merced | 445188 | 16,271 | 53,873 | 11,583 | 41,008 | `data/raw/programs/scorecard_ucmerced.json` |

The Delta query also returns a second record, UNITID 12265801, with the same tuition and null net price/COA; use 122658. Reproduce:

```bash
curl -s "https://api.data.gov/ed/collegescorecard/v1/schools?api_key=DEMO_KEY&school.name=San%20Joaquin%20Delta%20College&fields=id,school.name,school.city,school.state,latest.cost.tuition.in_state,latest.cost.tuition.out_of_state,latest.cost.avg_net_price.public,latest.cost.attendance.academic_year"
# DEMO_KEY is rate-limited; get a free key at https://api.data.gov/signup/ for production.
```

## 8. Transfer articulation and program-map tools

- **ASSIST** (https://assist.org): per its resource center (https://resource.assist.org/), ASSIST is the official repository of articulation and transferability information for California public colleges and universities, plus participating AICCU independent institutions.
  - It shows how courses completed at a community college count toward elective, general education and major requirements at a CSU or UC campus.
  - **Foothold use:** deep-link only, e.g. a "Check transfer credit on ASSIST" button. Do not scrape. assist.org is a JavaScript app, and the resource center has an ASSIST data/file-access page for official data requests.
- **Program Pathways Mapper** (CCC program-map tool, vendor site https://programmapper.org/). Verified HTTP 200 on 2026-10-24:

| College | URL | Page title |
|---|---|---|
| San Joaquin Delta College | https://programmap.deltacollege.edu/ | San Joaquin Delta College \| Program Pathways Mapper |
| Modesto Junior College | https://programmap.mjc.edu/ | Modesto Junior College \| Program Pathways Mapper |
| Reedley College | https://programmap.reedleycollege.edu/ | Reedley College \| Program Pathways Mapper |
| Madera College | https://programmap.maderacollege.edu/ | Madera College \| Program Pathways Mapper |
| Clovis Community College | https://programmap.cloviscollege.edu/ | Program Mapper |
| Bakersfield College | https://programmap.bakersfieldcollege.edu/ | Bakersfield College \| Program Pathways Mapper |

No connection from our network (DNS/TLS failure, so existence is **UNVERIFIED**, not disproven): https://programmap.mercedcollege.edu/, https://programmap.fresnocitycollege.edu/, https://programmap.gocolumbia.edu/, https://programmap.cos.edu/, https://programmap.portervillecollege.edu/.

URL patterns for builders:

- Category: `https://programmap.deltacollege.edu/category/technical-careers-and-trades/`. Delta's other category slugs: `agriculture`, `arts-humanities-and-multimedia`, `business-and-law`, `communication-and-languages`, `health-and-fitness`, `science-engineering-computer-science-and-math`, `social-science-education-and-public-service`.
- Program: `https://programmap.deltacollege.edu/program/<slug>/`. The HTML carries `data-control-number` (CCC program control number) and `data-top-code`.
- Delta apply link (from mapper header): `https://www.opencccapply.net/gateway/apply?cccMisCode=551`.

## 9. Reproduce the wage/outlook pulls (CKAN SQL API, no key needed)

```bash
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
# OEWS (wages): SOC column is numeric without dash (537062); Wage Type is "Hourly Wage" / "Annual Wage or Salary"
SQL='SELECT * FROM "aef4c53a-7e17-418c-acc1-d189e39b6caa" WHERE "Area Name" = '"'"'Stockton-Lodi MSA'"'"' AND "Year" = 2026 AND "Standard Occupational Classification" IN (531047,131081,291141,493031,493042,493041,514121,472111,151252,119013,173024,537062)'
curl -sG -A "$UA" --ssl-no-revoke "https://data.ca.gov/api/3/action/datastore_search_sql" --data-urlencode "sql=$SQL"
# Projections: SOC column is text with dash in field "standard_occupational_classification__soc_"; Area Name "Stockton-Lodi MSA (San Joaquin County)"
SQL2='SELECT * FROM "274e273c-d18c-4d84-b8df-49b4d13c14ce" WHERE "Area Name" = '"'"'Stockton-Lodi MSA (San Joaquin County)'"'"' AND "standard_occupational_classification__soc_" = '"'"'47-2111'"'"''
curl -sG -A "$UA" --ssl-no-revoke "https://data.ca.gov/api/3/action/datastore_search_sql" --data-urlencode "sql=$SQL2"
```

Field names. OEWS: `Area Type, Area Name, Year, Quarter, Industry Name, Standard Occupational Classification, Occupational Title, Wage Type, Number of Employed, Mean Wage, unsafe_10th_percentile_wage, unsafe_25th_percentile_wage, unsafe_50th_percentile__median__wage, unsafe_75th_percentile_wage, unsafe_90th_percentile_wage, Mean Relative Standard Error for Wage`. Projections: `Area Type, Area Name, Period, SOC Level, standard_occupational_classification__soc_, Occupational Title, Base Year Employment Estimate, Projected Year Employment Estimate, Numeric Change, Percentage Change, Exits, Transfers, Total Job Openings, Median Hourly Wage, Median Annual Wage, Entry Level Education, Work Experience, Job Training`.

## 10. Master value table (every value, unit, source, retrieved date, status)

| # | Item | Value | Unit | Source URL | Retrieved | Status |
|---:|---|---:|---|---|---|---|
| 1 | 00-0000 Stockton-Lodi 2026Q1 employment (May 2025) | 289,660 | jobs | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 2 | 00-0000 Stockton-Lodi 2026Q1 median hourly | 24.08 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 3 | 00-0000 Stockton-Lodi 2026Q1 median annual | 50,089.32 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 4 | 00-0000 Stockton-Lodi 2026Q1 25th pct hourly | 19.42 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 5 | 00-0000 Stockton-Lodi 2026Q1 25th pct annual | 40,396.59 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 6 | 00-0000 Stockton-Lodi 2026Q1 75th pct hourly | 36.90 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 7 | 00-0000 Stockton-Lodi 2026Q1 75th pct annual | 76,754.54 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 8 | 53-1047 Stockton-Lodi 2026Q1 employment (May 2025) | 2,440 | jobs | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 9 | 53-1047 Stockton-Lodi 2026Q1 median hourly | 36.34 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 10 | 53-1047 Stockton-Lodi 2026Q1 median annual | 75,589.20 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 11 | 53-1047 Stockton-Lodi 2026Q1 25th pct hourly | 27.53 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 12 | 53-1047 Stockton-Lodi 2026Q1 25th pct annual | 57,246.28 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 13 | 53-1047 Stockton-Lodi 2026Q1 75th pct hourly | 38.50 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 14 | 53-1047 Stockton-Lodi 2026Q1 75th pct annual | 80,095.74 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 15 | 53-1047 Stockton-Lodi MSA 2023-2033 growth | 12.0 | percent over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 16 | 53-1047 Stockton-Lodi MSA 2023-2033 total openings | 2,690 | openings over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 17 | 53-1047 Stockton-Lodi MSA 2023-2033 avg annual openings | 269 | openings/yr (total/10) | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | DERIVED |
| 18 | 53-1047 BLS May 2025 MSA median wage | not read | USD | https://data.bls.gov/oes/#/area/0044700/2025 | 2026-10-24 | NOT_READ (verify) |
| 19 | 13-1081 Stockton-Lodi 2026Q1 employment (May 2025) | 350 | jobs | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 20 | 13-1081 Stockton-Lodi 2026Q1 median hourly | 37.43 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 21 | 13-1081 Stockton-Lodi 2026Q1 median annual | 77,844.41 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 22 | 13-1081 Stockton-Lodi 2026Q1 25th pct hourly | 29.68 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 23 | 13-1081 Stockton-Lodi 2026Q1 25th pct annual | 61,728.50 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 24 | 13-1081 Stockton-Lodi 2026Q1 75th pct hourly | 47.87 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 25 | 13-1081 Stockton-Lodi 2026Q1 75th pct annual | 99,572.92 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 26 | 13-1081 Stockton-Lodi MSA 2023-2033 growth | 25.7 | percent over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 27 | 13-1081 Stockton-Lodi MSA 2023-2033 total openings | 410 | openings over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 28 | 13-1081 Stockton-Lodi MSA 2023-2033 avg annual openings | 41 | openings/yr (total/10) | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | DERIVED |
| 29 | 13-1081 BLS May 2025 MSA median wage | not read | USD | https://data.bls.gov/oes/#/area/0044700/2025 | 2026-10-24 | NOT_READ (verify) |
| 30 | 29-1141 Stockton-Lodi 2026Q1 employment (May 2025) | 5,460 | jobs | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 31 | 29-1141 Stockton-Lodi 2026Q1 median hourly | 66.51 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 32 | 29-1141 Stockton-Lodi 2026Q1 median annual | 138,347.28 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 33 | 29-1141 Stockton-Lodi 2026Q1 25th pct hourly | 60.61 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 34 | 29-1141 Stockton-Lodi 2026Q1 25th pct annual | 126,073.04 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 35 | 29-1141 Stockton-Lodi 2026Q1 75th pct hourly | 82.55 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 36 | 29-1141 Stockton-Lodi 2026Q1 75th pct annual | 171,695.37 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 37 | 29-1141 Stockton-Lodi MSA 2023-2033 growth | 8.2 | percent over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 38 | 29-1141 Stockton-Lodi MSA 2023-2033 total openings | 3,010 | openings over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 39 | 29-1141 Stockton-Lodi MSA 2023-2033 avg annual openings | 301 | openings/yr (total/10) | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | DERIVED |
| 40 | 29-1141 BLS May 2025 MSA median wage | not read | USD | https://data.bls.gov/oes/#/area/0044700/2025 | 2026-10-24 | NOT_READ (verify) |
| 41 | 49-3031 Stockton-Lodi 2026Q1 employment (May 2025) | 760 | jobs | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 42 | 49-3031 Stockton-Lodi 2026Q1 median hourly | 34.81 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 43 | 49-3031 Stockton-Lodi 2026Q1 median annual | 72,400.82 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 44 | 49-3031 Stockton-Lodi 2026Q1 25th pct hourly | 26.17 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 45 | 49-3031 Stockton-Lodi 2026Q1 25th pct annual | 54,436.86 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 46 | 49-3031 Stockton-Lodi 2026Q1 75th pct hourly | 38.99 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 47 | 49-3031 Stockton-Lodi 2026Q1 75th pct annual | 81,089.74 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 48 | 49-3031 Stockton-Lodi MSA 2023-2033 growth | 8.7 | percent over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 49 | 49-3031 Stockton-Lodi MSA 2023-2033 total openings | 650 | openings over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 50 | 49-3031 Stockton-Lodi MSA 2023-2033 avg annual openings | 65 | openings/yr (total/10) | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | DERIVED |
| 51 | 49-3031 BLS May 2025 MSA median wage | not read | USD | https://data.bls.gov/oes/#/area/0044700/2025 | 2026-10-24 | NOT_READ (verify) |
| 52 | 49-3042 Stockton-Lodi 2026Q1 employment (May 2025) | 530 | jobs | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 53 | 49-3042 Stockton-Lodi 2026Q1 median hourly | 36.59 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 54 | 49-3042 Stockton-Lodi 2026Q1 median annual | 76,092.33 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 55 | 49-3042 Stockton-Lodi 2026Q1 25th pct hourly | 27.41 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 56 | 49-3042 Stockton-Lodi 2026Q1 25th pct annual | 57,007.55 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 57 | 49-3042 Stockton-Lodi 2026Q1 75th pct hourly | 40.22 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 58 | 49-3042 Stockton-Lodi 2026Q1 75th pct annual | 83,660.43 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 59 | 49-3042 Stockton-Lodi MSA 2023-2033 growth | 10.9 | percent over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 60 | 49-3042 Stockton-Lodi MSA 2023-2033 total openings | 530 | openings over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 61 | 49-3042 Stockton-Lodi MSA 2023-2033 avg annual openings | 53 | openings/yr (total/10) | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | DERIVED |
| 62 | 49-3042 BLS May 2025 MSA median wage | not read | USD | https://data.bls.gov/oes/#/area/0044700/2025 | 2026-10-24 | NOT_READ (verify) |
| 63 | 49-3041 Stockton-Lodi 2026Q1 employment (May 2025) | 250 | jobs | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 64 | 49-3041 Stockton-Lodi 2026Q1 median hourly | 25.58 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 65 | 49-3041 Stockton-Lodi 2026Q1 median annual | 53,213.21 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 66 | 49-3041 Stockton-Lodi 2026Q1 25th pct hourly | 22.64 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 67 | 49-3041 Stockton-Lodi 2026Q1 25th pct annual | 47,084.70 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 68 | 49-3041 Stockton-Lodi 2026Q1 75th pct hourly | 37.61 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 69 | 49-3041 Stockton-Lodi 2026Q1 75th pct annual | 78,241.42 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 70 | 49-3041 Stockton-Lodi MSA 2023-2033 growth | 7.7 | percent over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 71 | 49-3041 Stockton-Lodi MSA 2023-2033 total openings | 240 | openings over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 72 | 49-3041 Stockton-Lodi MSA 2023-2033 avg annual openings | 24 | openings/yr (total/10) | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | DERIVED |
| 73 | 49-3041 BLS May 2025 MSA median wage | not read | USD | https://data.bls.gov/oes/#/area/0044700/2025 | 2026-10-24 | NOT_READ (verify) |
| 74 | 51-4121 Stockton-Lodi 2026Q1 employment (May 2025) | 740 | jobs | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 75 | 51-4121 Stockton-Lodi 2026Q1 median hourly | 25.31 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 76 | 51-4121 Stockton-Lodi 2026Q1 median annual | 52,654.67 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 77 | 51-4121 Stockton-Lodi 2026Q1 25th pct hourly | 23.71 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 78 | 51-4121 Stockton-Lodi 2026Q1 25th pct annual | 49,320.29 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 79 | 51-4121 Stockton-Lodi 2026Q1 75th pct hourly | 30.31 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 80 | 51-4121 Stockton-Lodi 2026Q1 75th pct annual | 63,036.27 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 81 | 51-4121 Stockton-Lodi MSA 2023-2033 growth | 7.7 | percent over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 82 | 51-4121 Stockton-Lodi MSA 2023-2033 total openings | 710 | openings over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 83 | 51-4121 Stockton-Lodi MSA 2023-2033 avg annual openings | 71 | openings/yr (total/10) | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | DERIVED |
| 84 | 51-4121 BLS May 2025 MSA median wage | not read | USD | https://data.bls.gov/oes/#/area/0044700/2025 | 2026-10-24 | NOT_READ (verify) |
| 85 | 47-2111 Stockton-Lodi 2026Q1 employment (May 2025) | 1,180 | jobs | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 86 | 47-2111 Stockton-Lodi 2026Q1 median hourly | 37.74 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 87 | 47-2111 Stockton-Lodi 2026Q1 median annual | 78,480.00 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 88 | 47-2111 Stockton-Lodi 2026Q1 25th pct hourly | 28.95 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 89 | 47-2111 Stockton-Lodi 2026Q1 25th pct annual | 60,218.33 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 90 | 47-2111 Stockton-Lodi 2026Q1 75th pct hourly | 50.59 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 91 | 47-2111 Stockton-Lodi 2026Q1 75th pct annual | 105,225.44 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 92 | 47-2111 Stockton-Lodi MSA 2023-2033 growth | 25.8 | percent over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 93 | 47-2111 Stockton-Lodi MSA 2023-2033 total openings | 1,490 | openings over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 94 | 47-2111 Stockton-Lodi MSA 2023-2033 avg annual openings | 149 | openings/yr (total/10) | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | DERIVED |
| 95 | 47-2111 BLS May 2025 MSA median wage | not read | USD | https://data.bls.gov/oes/#/area/0044700/2025 | 2026-10-24 | NOT_READ (verify) |
| 96 | 15-1252 Stockton-Lodi 2026Q1 employment (May 2025) | 570 | jobs | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 97 | 15-1252 Stockton-Lodi 2026Q1 median hourly | 68.47 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 98 | 15-1252 Stockton-Lodi 2026Q1 median annual | 142,428.41 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 99 | 15-1252 Stockton-Lodi 2026Q1 25th pct hourly | 59.57 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 100 | 15-1252 Stockton-Lodi 2026Q1 25th pct annual | 123,914.26 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 101 | 15-1252 Stockton-Lodi 2026Q1 75th pct hourly | 87.57 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 102 | 15-1252 Stockton-Lodi 2026Q1 75th pct annual | 182,160.33 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 103 | 15-1252 Stockton-Lodi MSA 2023-2033 growth | 16.9 | percent over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 104 | 15-1252 Stockton-Lodi MSA 2023-2033 total openings | 430 | openings over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 105 | 15-1252 Stockton-Lodi MSA 2023-2033 avg annual openings | 43 | openings/yr (total/10) | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | DERIVED |
| 106 | 15-1252 BLS May 2025 MSA median wage | not read | USD | https://data.bls.gov/oes/#/area/0044700/2025 | 2026-10-24 | NOT_READ (verify) |
| 107 | 11-9013 Stockton-Lodi 2026Q1 employment (May 2025) | 100 | jobs | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 108 | 11-9013 Stockton-Lodi 2026Q1 median hourly | 49.85 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 109 | 11-9013 Stockton-Lodi 2026Q1 median annual | 103,701.04 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 110 | 11-9013 Stockton-Lodi 2026Q1 25th pct hourly | 44.96 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 111 | 11-9013 Stockton-Lodi 2026Q1 25th pct annual | 93,523.10 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 112 | 11-9013 Stockton-Lodi 2026Q1 75th pct hourly | 64.77 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 113 | 11-9013 Stockton-Lodi 2026Q1 75th pct annual | 134,712.72 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 114 | 11-9013 Stockton-Lodi MSA 2023-2033 growth | -8.0 | percent over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 115 | 11-9013 Stockton-Lodi MSA 2023-2033 total openings | 1,980 | openings over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 116 | 11-9013 Stockton-Lodi MSA 2023-2033 avg annual openings | 198 | openings/yr (total/10) | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | DERIVED |
| 117 | 11-9013 BLS May 2025 MSA median wage | not read | USD | https://data.bls.gov/oes/#/area/0044700/2025 | 2026-10-24 | NOT_READ (verify) |
| 118 | 17-3024 Sacramento-Roseville-Folsom MSA 2026Q1 employment | 40 | jobs | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 119 | 17-3024 Sacramento-Roseville-Folsom MSA 2026Q1 median hourly | 38.85 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 120 | 17-3024 Sacramento-Roseville-Folsom MSA 2026Q1 median annual | 80,789.96 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 121 | 17-3024 California 2026Q1 employment | 1,850 | jobs | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 122 | 17-3024 California 2026Q1 median hourly | 40.31 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 123 | 17-3024 California 2026Q1 median annual | 83,832.82 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 124 | 17-3024 California 2024-2034 growth | 5.3 | percent over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 125 | 17-3024 California 2024-2034 total openings | 1,700 | openings over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 126 | 17-3024 California 2024-2034 avg annual openings | 170 | openings/yr (total/10) | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | DERIVED |
| 127 | 17-3024 BLS May 2025 MSA median wage | not read | USD | https://data.bls.gov/oes/#/area/0044700/2025 | 2026-10-24 | NOT_READ (verify) |
| 128 | 53-7062 Stockton-Lodi 2026Q1 employment (May 2025) | 15,030 | jobs | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 129 | 53-7062 Stockton-Lodi 2026Q1 median hourly | 23.25 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 130 | 53-7062 Stockton-Lodi 2026Q1 median annual | 48,366.05 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 131 | 53-7062 Stockton-Lodi 2026Q1 25th pct hourly | 20.63 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 132 | 53-7062 Stockton-Lodi 2026Q1 25th pct annual | 42,909.16 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 133 | 53-7062 Stockton-Lodi 2026Q1 75th pct hourly | 27.67 | USD/hour | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 134 | 53-7062 Stockton-Lodi 2026Q1 75th pct annual | 57,563.06 | USD/year | https://data.ca.gov/dataset/oews | 2026-10-24 | REAL |
| 135 | 53-7062 Stockton-Lodi MSA 2023-2033 growth | 8.5 | percent over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 136 | 53-7062 Stockton-Lodi MSA 2023-2033 total openings | 23,630 | openings over 10 yrs | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | REAL |
| 137 | 53-7062 Stockton-Lodi MSA 2023-2033 avg annual openings | 2,363 | openings/yr (total/10) | https://data.ca.gov/dataset/long-term-occupational-employment-projections | 2026-10-24 | DERIVED |
| 138 | 53-7062 BLS May 2025 MSA median wage | not read | USD | https://data.bls.gov/oes/#/area/0044700/2025 | 2026-10-24 | NOT_READ (verify) |
| 139 | CCC enrollment fee | 46 | USD/unit | https://www.deltacollege.edu/admission-aid/tuition-fees | 2026-10-24 | REAL |
| 140 | Delta Nonresident tuition (effective Summer 2026) | 328 | USD per unit, plus $46/unit enrollment fee | https://www.deltacollege.edu/admission-aid/tuition-fees | 2026-10-24 | REAL |
| 141 | Delta Student activity fee (Mustang Pass) | 10 | USD per semester | https://www.deltacollege.edu/admission-aid/tuition-fees | 2026-10-24 | REAL |
| 142 | Delta Student representation fee | 2 | USD per semester | https://www.deltacollege.edu/admission-aid/tuition-fees | 2026-10-24 | REAL |
| 143 | Delta Student health fee | 26 | USD per semester (22 for summer) | https://www.deltacollege.edu/admission-aid/tuition-fees | 2026-10-24 | REAL |
| 144 | Delta Parking permit (automobile) | 30 | USD per semester | https://www.deltacollege.edu/admission-aid/tuition-fees | 2026-10-24 | REAL |
| 145 | Delta Course audit | 15 | USD per unit | https://www.deltacollege.edu/admission-aid/tuition-fees | 2026-10-24 | REAL |
| 146 | Delta Nursing R.N. - Major Courses Only (Associate in Science) units | 36.5 | semester units | https://programmap.deltacollege.edu/program/nursing-r-n/ | 2026-10-24 | REAL |
| 147 | Delta Nursing R.N. - Major Courses Only terms | 4 | terms to award | https://programmap.deltacollege.edu/program/nursing-r-n/ | 2026-10-24 | REAL |
| 148 | Delta Nursing R.N. - Pre-Nursing Prereqs & Additional Courses (Associate in Science) units | 47-50 | semester units | https://programmap.deltacollege.edu/program/nursing-r-n/ | 2026-10-24 | REAL |
| 149 | Delta Nursing R.N. - Pre-Nursing Prereqs & Additional Courses terms | 4 | terms to award | https://programmap.deltacollege.edu/program/nursing-r-n/ | 2026-10-24 | REAL |
| 150 | MJC Nursing: ADN Program (RN) - LVN Certified already to Nursing Program (Associate of Science) units | 95-101 | semester units | https://programmap.mjc.edu/program/nursing-adn-program-rn/ | 2026-10-24 | REAL |
| 151 | MJC Nursing: ADN Program (RN) - LVN Certified already to Nursing Program terms | 12 | terms to award | https://programmap.mjc.edu/program/nursing-adn-program-rn/ | 2026-10-24 | REAL |
| 152 | MJC Nursing: ADN Program (RN) - Prereq with Nursing Program Coursework (Associate of Science) units | 105.5 | semester units | https://programmap.mjc.edu/program/nursing-adn-program-rn/ | 2026-10-24 | REAL |
| 153 | MJC Nursing: ADN Program (RN) - Prereq with Nursing Program Coursework terms | 13 | terms to award | https://programmap.mjc.edu/program/nursing-adn-program-rn/ | 2026-10-24 | REAL |
| 154 | MJC Nursing: ADN Program (RN) - Nurs. Prereq & CSU GE Cert for RN Prog Appl (Associate of Science) units | 69.5 | semester units | https://programmap.mjc.edu/program/nursing-adn-program-rn/ | 2026-10-24 | REAL |
| 155 | MJC Nursing: ADN Program (RN) - Nurs. Prereq & CSU GE Cert for RN Prog Appl terms | 9 | terms to award | https://programmap.mjc.edu/program/nursing-adn-program-rn/ | 2026-10-24 | REAL |
| 156 | Delta Welding Technology (Certificate of Achievement) units | 42.5 | semester units | https://programmap.deltacollege.edu/program/welding-technology/ | 2026-10-24 | REAL |
| 157 | Delta Welding Technology terms | 3 | terms to award | https://programmap.deltacollege.edu/program/welding-technology/ | 2026-10-24 | REAL |
| 158 | Delta Oxy-Fuel Processes and Shielded Metal Arc Welding (SMAW) (Certificate of Achievement) units | 20 | semester units | https://programmap.deltacollege.edu/program/oxy-fuel-processes-and-shielded-metal-arc-welding-smaw/ | 2026-10-24 | REAL |
| 159 | Delta Oxy-Fuel Processes and Shielded Metal Arc Welding (SMAW) terms | 2 | terms to award | https://programmap.deltacollege.edu/program/oxy-fuel-processes-and-shielded-metal-arc-welding-smaw/ | 2026-10-24 | REAL |
| 160 | Delta Gas Metal Arc Welding (GMAW)/Flux Core Arc Welding (FCAW) (Certificate of Achievement) units | 20 | semester units | https://programmap.deltacollege.edu/program/gas-metal-arc-welding-gmaw-flux-core-arc-welding-fcaw/ | 2026-10-24 | REAL |
| 161 | Delta Gas Metal Arc Welding (GMAW)/Flux Core Arc Welding (FCAW) terms | 2 | terms to award | https://programmap.deltacollege.edu/program/gas-metal-arc-welding-gmaw-flux-core-arc-welding-fcaw/ | 2026-10-24 | REAL |
| 162 | MJC Welding (Associate of Science) units | 61.5-63 | semester units | https://programmap.mjc.edu/program/welding/ | 2026-10-24 | REAL |
| 163 | MJC Welding terms | 6 | terms to award | https://programmap.mjc.edu/program/welding/ | 2026-10-24 | REAL |
| 164 | Delta Diesel Equipment Technician (Certificate of Achievement) units | 42.5 | semester units | https://programmap.deltacollege.edu/program/diesel-equipment-technician/ | 2026-10-24 | REAL |
| 165 | Delta Diesel Equipment Technician terms | 5 | terms to award | https://programmap.deltacollege.edu/program/diesel-equipment-technician/ | 2026-10-24 | REAL |
| 166 | Delta Diesel Equipment Technician (Associate in Science) units | 66.5 | semester units | https://programmap.deltacollege.edu/program/diesel-equipment-technician-2/ | 2026-10-24 | REAL |
| 167 | Delta Diesel Equipment Technician terms | 5 | terms to award | https://programmap.deltacollege.edu/program/diesel-equipment-technician-2/ | 2026-10-24 | REAL |
| 168 | Delta Diesel Bus Technician (Certificate of Achievement) units | 32.5 | semester units | https://programmap.deltacollege.edu/program/diesel-bus-technician/ | 2026-10-24 | REAL |
| 169 | Delta Diesel Bus Technician terms | 4 | terms to award | https://programmap.deltacollege.edu/program/diesel-bus-technician/ | 2026-10-24 | REAL |
| 170 | Delta Heavy Equipment Technician (Certificate of Achievement) units | 31 | semester units | https://programmap.deltacollege.edu/program/heavy-equipment-technician-2/ | 2026-10-24 | REAL |
| 171 | Delta Heavy Equipment Technician terms | 3 | terms to award | https://programmap.deltacollege.edu/program/heavy-equipment-technician-2/ | 2026-10-24 | REAL |
| 172 | Delta Heavy Equipment Technician (Associate in Science) units | 60-69 | semester units | https://programmap.deltacollege.edu/program/heavy-equipment-technician/ | 2026-10-24 | REAL |
| 173 | Delta Heavy Equipment Technician terms | 5 | terms to award | https://programmap.deltacollege.edu/program/heavy-equipment-technician/ | 2026-10-24 | REAL |
| 174 | Delta Heavy Equipment Mechanic (Certificate of Achievement) units | 24 | semester units | https://programmap.deltacollege.edu/program/heavy-equipment-mechanic/ | 2026-10-24 | REAL |
| 175 | Delta Heavy Equipment Mechanic terms | 3 | terms to award | https://programmap.deltacollege.edu/program/heavy-equipment-mechanic/ | 2026-10-24 | REAL |
| 176 | Delta Caterpillar Dealer Service Technician Apprenticeship (Associate in Science) units | 81 | semester units | https://programmap.deltacollege.edu/program/caterpillar-dealer-service-technician-apprenticeship/ | 2026-10-24 | REAL |
| 177 | Delta Caterpillar Dealer Service Technician Apprenticeship terms | 5 | terms to award | https://programmap.deltacollege.edu/program/caterpillar-dealer-service-technician-apprenticeship/ | 2026-10-24 | REAL |
| 178 | MJC Basic Heavy Equipment Technician (Certificate of Achievement) units | 18 | semester units | https://programmap.mjc.edu/program/basic-heavy-equipment-technician/ | 2026-10-24 | REAL |
| 179 | MJC Basic Heavy Equipment Technician terms | 1 | terms to award | https://programmap.mjc.edu/program/basic-heavy-equipment-technician/ | 2026-10-24 | REAL |
| 180 | MJC Advanced Heavy Equipment Technician (Certificate of Achievement) units | 16 | semester units | https://programmap.mjc.edu/program/advanced-heavy-equipment-technician/ | 2026-10-24 | REAL |
| 181 | MJC Advanced Heavy Equipment Technician terms | 2 | terms to award | https://programmap.mjc.edu/program/advanced-heavy-equipment-technician/ | 2026-10-24 | REAL |
| 182 | Delta Agriculture Mechanics (Certificate of Achievement) units | 16.5 | semester units | https://programmap.deltacollege.edu/program/agriculture-mechanics/ | 2026-10-24 | REAL |
| 183 | Delta Agriculture Mechanics terms | 2 | terms to award | https://programmap.deltacollege.edu/program/agriculture-mechanics/ | 2026-10-24 | REAL |
| 184 | MJC Mechanized Agriculture Technician (Certificate of Achievement) units | 30 | semester units | https://programmap.mjc.edu/program/mechanized-agriculture-technician/ | 2026-10-24 | REAL |
| 185 | MJC Mechanized Agriculture Technician terms | 3 | terms to award | https://programmap.mjc.edu/program/mechanized-agriculture-technician/ | 2026-10-24 | REAL |
| 186 | MJC Agriculture Mechanics (Associate of Science) units | 61-66 | semester units | https://programmap.mjc.edu/program/agriculture-mechanics/ | 2026-10-24 | REAL |
| 187 | MJC Agriculture Mechanics terms | 5 | terms to award | https://programmap.mjc.edu/program/agriculture-mechanics/ | 2026-10-24 | REAL |
| 188 | Delta Electrical Technology - General Electrician Trainee (Certificate of Achievement) units | 43 | semester units | https://programmap.deltacollege.edu/program/electrical-technology-general-electrician-trainee/ | 2026-10-24 | REAL |
| 189 | Delta Electrical Technology - General Electrician Trainee terms | 4 | terms to award | https://programmap.deltacollege.edu/program/electrical-technology-general-electrician-trainee/ | 2026-10-24 | REAL |
| 190 | Delta Electrical Technology (Associate in Science) units | 67-76 | semester units | https://programmap.deltacollege.edu/program/electrical-technology/ | 2026-10-24 | REAL |
| 191 | Delta Electrical Technology terms | 5 | terms to award | https://programmap.deltacollege.edu/program/electrical-technology/ | 2026-10-24 | REAL |
| 192 | Delta Electrical Technology - Electrical Maintenance (Certificate of Achievement) units | 30-33 | semester units | https://programmap.deltacollege.edu/program/electrical-technology-electrical-maintenance/ | 2026-10-24 | REAL |
| 193 | Delta Electrical Technology - Electrical Maintenance terms | 3 | terms to award | https://programmap.deltacollege.edu/program/electrical-technology-electrical-maintenance/ | 2026-10-24 | REAL |
| 194 | MJC Electrician (Certificate of Achievement) units | 34 | semester units | https://programmap.mjc.edu/program/electrician/ | 2026-10-24 | REAL |
| 195 | MJC Electrician terms | 4 | terms to award | https://programmap.mjc.edu/program/electrician/ | 2026-10-24 | REAL |
| 196 | Delta Automation Technician - Mechatronics (Certificate of Achievement) units | 33.5 | semester units | https://programmap.deltacollege.edu/program/automation-technician-mechatronics/ | 2026-10-24 | REAL |
| 197 | Delta Automation Technician - Mechatronics terms | 3 | terms to award | https://programmap.deltacollege.edu/program/automation-technician-mechatronics/ | 2026-10-24 | REAL |
| 198 | Delta Automation Technology - Mechatronics (Associate in Science) units | 60 | semester units | https://programmap.deltacollege.edu/program/automation-technology-mechatronics/ | 2026-10-24 | REAL |
| 199 | Delta Automation Technology - Mechatronics terms | 4 | terms to award | https://programmap.deltacollege.edu/program/automation-technology-mechatronics/ | 2026-10-24 | REAL |
| 200 | Delta Electronics Technology (Certificate of Achievement) units | 21-22 | semester units | https://programmap.deltacollege.edu/program/electronics-technology/ | 2026-10-24 | REAL |
| 201 | Delta Electronics Technology terms | 2 | terms to award | https://programmap.deltacollege.edu/program/electronics-technology/ | 2026-10-24 | REAL |
| 202 | MJC Automation Technician (Certificate of Achievement) units | 19 | semester units | https://programmap.mjc.edu/program/automation-technician/ | 2026-10-24 | REAL |
| 203 | MJC Automation Technician terms | 2 | terms to award | https://programmap.mjc.edu/program/automation-technician/ | 2026-10-24 | REAL |
| 204 | MJC Electro-Mechanic (Certificate of Achievement) units | 35 | semester units | https://programmap.mjc.edu/program/electro-mechanic/ | 2026-10-24 | REAL |
| 205 | MJC Electro-Mechanic terms | 4 | terms to award | https://programmap.mjc.edu/program/electro-mechanic/ | 2026-10-24 | REAL |
| 206 | MJC Industrial Electronics (Certificate of Achievement) units | 34 | semester units | https://programmap.mjc.edu/program/industrial-electronics-2/ | 2026-10-24 | REAL |
| 207 | MJC Industrial Electronics terms | 4 | terms to award | https://programmap.mjc.edu/program/industrial-electronics-2/ | 2026-10-24 | REAL |
| 208 | MJC Industrial Electronics (Associate of Science) units | 58.5-59 | semester units | https://programmap.mjc.edu/program/industrial-electronics/ | 2026-10-24 | REAL |
| 209 | MJC Industrial Electronics terms | 5 | terms to award | https://programmap.mjc.edu/program/industrial-electronics/ | 2026-10-24 | REAL |
| 210 | Delta Computer Science (Associate in Science for Transfer) units | 63-64 | semester units | https://programmap.deltacollege.edu/program/computer-science-2/ | 2026-10-24 | REAL |
| 211 | Delta Computer Science terms | 5 | terms to award | https://programmap.deltacollege.edu/program/computer-science-2/ | 2026-10-24 | REAL |
| 212 | Delta Computer Science (Associate in Science) units | 60-61 | semester units | https://programmap.deltacollege.edu/program/computer-science/ | 2026-10-24 | REAL |
| 213 | Delta Computer Science terms | 4 | terms to award | https://programmap.deltacollege.edu/program/computer-science/ | 2026-10-24 | REAL |
| 214 | Delta Computer Science (Certificate of Achievement) units | 50.5-53.5 | semester units | https://programmap.deltacollege.edu/program/computer-science-3/ | 2026-10-24 | REAL |
| 215 | Delta Computer Science terms | 4 | terms to award | https://programmap.deltacollege.edu/program/computer-science-3/ | 2026-10-24 | REAL |
| 216 | Delta Computer Programming (Certificate of Achievement) units | 44.5-48.5 | semester units | https://programmap.deltacollege.edu/program/computer-programming/ | 2026-10-24 | REAL |
| 217 | Delta Computer Programming terms | 4 | terms to award | https://programmap.deltacollege.edu/program/computer-programming/ | 2026-10-24 | REAL |
| 218 | MJC Computer Science for Transfer Degree - Two-Year Plan (Associate of Science for Transfer) units | 68-75 | semester units | https://programmap.mjc.edu/program/computer-science-for-transfer-degree/ | 2026-10-24 | REAL |
| 219 | MJC Computer Science for Transfer Degree - Two-Year Plan terms | 6 | terms to award | https://programmap.mjc.edu/program/computer-science-for-transfer-degree/ | 2026-10-24 | REAL |
| 220 | MJC Computer Science for Transfer Degree - Three Year Plan (Associate of Science for Transfer) units | 69-74 | semester units | https://programmap.mjc.edu/program/computer-science-for-transfer-degree/ | 2026-10-24 | REAL |
| 221 | MJC Computer Science for Transfer Degree - Three Year Plan terms | 8 | terms to award | https://programmap.mjc.edu/program/computer-science-for-transfer-degree/ | 2026-10-24 | REAL |
| 222 | MJC Computer Science for Transfer Degree - Calculus & Physics Ready (Associate of Science for Transfer) units | 59-64 | semester units | https://programmap.mjc.edu/program/computer-science-for-transfer-degree/ | 2026-10-24 | REAL |
| 223 | MJC Computer Science for Transfer Degree - Calculus & Physics Ready terms | 6 | terms to award | https://programmap.mjc.edu/program/computer-science-for-transfer-degree/ | 2026-10-24 | REAL |
| 224 | MJC Computer Science - Information Systems (Associate of Science) units | 60.5-63.5 | semester units | https://programmap.mjc.edu/program/computer-science/ | 2026-10-24 | REAL |
| 225 | MJC Computer Science - Information Systems terms | 7 | terms to award | https://programmap.mjc.edu/program/computer-science/ | 2026-10-24 | REAL |
| 226 | MJC Computer Science - Programming (Associate of Science) units | 60.5-63.5 | semester units | https://programmap.mjc.edu/program/computer-science/ | 2026-10-24 | REAL |
| 227 | MJC Computer Science - Programming terms | 7 | terms to award | https://programmap.mjc.edu/program/computer-science/ | 2026-10-24 | REAL |
| 228 | MJC Computer Science - Networking (Associate of Science) units | 60-61 | semester units | https://programmap.mjc.edu/program/computer-science/ | 2026-10-24 | REAL |
| 229 | MJC Computer Science - Networking terms | 7 | terms to award | https://programmap.mjc.edu/program/computer-science/ | 2026-10-24 | REAL |
| 230 | Delta Agriculture Business (Certificate of Achievement) units | 59-61 | semester units | https://programmap.deltacollege.edu/program/agriculture-business/ | 2026-10-24 | REAL |
| 231 | Delta Agriculture Business terms | 4 | terms to award | https://programmap.deltacollege.edu/program/agriculture-business/ | 2026-10-24 | REAL |
| 232 | Delta Agriculture Plant Science (Associate in Science for Transfer) units | 60-61.5 | semester units | https://programmap.deltacollege.edu/program/agriculture-plant-science/ | 2026-10-24 | REAL |
| 233 | Delta Agriculture Plant Science terms | 4 | terms to award | https://programmap.deltacollege.edu/program/agriculture-plant-science/ | 2026-10-24 | REAL |
| 234 | MJC Agriculture Business for Transfer Degree (Associate of Science for Transfer) units | 60-62 | semester units | https://programmap.mjc.edu/program/agriculture-business-for-transfer-degree/ | 2026-10-24 | REAL |
| 235 | MJC Agriculture Business for Transfer Degree terms | 5 | terms to award | https://programmap.mjc.edu/program/agriculture-business-for-transfer-degree/ | 2026-10-24 | REAL |
| 236 | Delta Logistics and Transportation Supervisor (Certificate of Achievement) units | 24 | semester units | https://programmap.deltacollege.edu/program/logistics-and-transportation-supervisor/ | 2026-10-24 | REAL |
| 237 | Delta Logistics and Transportation Supervisor terms | 2 | terms to award | https://programmap.deltacollege.edu/program/logistics-and-transportation-supervisor/ | 2026-10-24 | REAL |
| 238 | Delta Traffic Shipping and Receiving Technician (Certificate of Achievement) units | 15-16 | semester units | https://programmap.deltacollege.edu/program/traffic-shipping-and-receiving-technician/ | 2026-10-24 | REAL |
| 239 | Delta Traffic Shipping and Receiving Technician terms | 1 | terms to award | https://programmap.deltacollege.edu/program/traffic-shipping-and-receiving-technician/ | 2026-10-24 | REAL |
| 240 | Delta Logistics and Transportation (Associate in Science) units | 60-64 | semester units | https://programmap.deltacollege.edu/program/logistics-and-transportation/ | 2026-10-24 | REAL |
| 241 | Delta Logistics and Transportation terms | 4 | terms to award | https://programmap.deltacollege.edu/program/logistics-and-transportation/ | 2026-10-24 | REAL |
| 242 | MJC Logistics and Supply Chain Management (Certificate of Achievement) units | 24-30 | semester units | https://programmap.mjc.edu/program/logistics-and-supply-chain-management-2/ | 2026-10-24 | REAL |
| 243 | MJC Logistics and Supply Chain Management terms | 3 | terms to award | https://programmap.mjc.edu/program/logistics-and-supply-chain-management-2/ | 2026-10-24 | REAL |
| 244 | MJC Logistics and Supply Chain Management (Associate of Science) units | 56-60 | semester units | https://programmap.mjc.edu/program/logistics-and-supply-chain-management/ | 2026-10-24 | REAL |
| 245 | MJC Logistics and Supply Chain Management terms | 6 | terms to award | https://programmap.mjc.edu/program/logistics-and-supply-chain-management/ | 2026-10-24 | REAL |
| 246 | Delta Logistics and Transportation (Associate in Science) units | 60-64 | semester units | https://programmap.deltacollege.edu/program/logistics-and-transportation/ | 2026-10-24 | REAL |
| 247 | Delta Logistics and Transportation terms | 4 | terms to award | https://programmap.deltacollege.edu/program/logistics-and-transportation/ | 2026-10-24 | REAL |
| 248 | Delta Business Administration for Transfer 2.0 (Associate in Science for Transfer) units | 60-64 | semester units | https://programmap.deltacollege.edu/program/business-administration-for-transfer-2-0/ | 2026-10-24 | REAL |
| 249 | Delta Business Administration for Transfer 2.0 terms | 4 | terms to award | https://programmap.deltacollege.edu/program/business-administration-for-transfer-2-0/ | 2026-10-24 | REAL |
| 250 | MJC Logistics and Supply Chain Management (Associate of Science) units | 56-60 | semester units | https://programmap.mjc.edu/program/logistics-and-supply-chain-management/ | 2026-10-24 | REAL |
| 251 | MJC Logistics and Supply Chain Management terms | 6 | terms to award | https://programmap.mjc.edu/program/logistics-and-supply-chain-management/ | 2026-10-24 | REAL |
| 252 | Delta Traffic Shipping and Receiving Technician (Certificate of Achievement) units | 15-16 | semester units | https://programmap.deltacollege.edu/program/traffic-shipping-and-receiving-technician/ | 2026-10-24 | REAL |
| 253 | Delta Traffic Shipping and Receiving Technician terms | 1 | terms to award | https://programmap.deltacollege.edu/program/traffic-shipping-and-receiving-technician/ | 2026-10-24 | REAL |
| 254 | SJETI inside wireman length | 60 | months | https://www.dir.ca.gov/databases/das/results_aigdetail.asp?varOccId=9810 | 2026-10-24 | REAL |
| 255 | SJETI starting wage | 21.35 | USD/hour | https://www.dir.ca.gov/databases/das/results_aigdetail.asp?varOccId=9810 | 2026-10-24 | REAL |
| 256 | SJETI related training | ~200 | hours/year | https://sjeti.org/ | 2026-10-24 | REAL |
| 257 | California State University, Stanislaus (Turlock) tuition fee >6 units (Fall 2026) | 3,419.00 | USD/semester | https://www.csustan.edu/tuition-fees/fee-schedules-deadlines#fall-26 | 2026-10-24 | REAL |
| 258 | California State University, Stanislaus (Turlock) total >6 units (Fall 2026) | 4,815.00 | USD/semester | https://www.csustan.edu/tuition-fees/fee-schedules-deadlines#fall-26 | 2026-10-24 | REAL |
| 259 | California State University, Stanislaus (Turlock) total 0-6 units (Fall 2026) | 3,257.00 | USD/semester | https://www.csustan.edu/tuition-fees/fee-schedules-deadlines#fall-26 | 2026-10-24 | REAL |
| 260 | California State University, Fresno tuition fee >6 units (Fall 2026) | 3,419.00 | USD/semester | https://adminfinance.fresnostate.edu/accountingservices/students/tuitionfees.html | 2026-10-24 | REAL |
| 261 | California State University, Fresno total >6 units (Fall 2026) | 4,317.50 | USD/semester | https://adminfinance.fresnostate.edu/accountingservices/students/tuitionfees.html | 2026-10-24 | REAL |
| 262 | California State University, Fresno total 0-6 units (Fall 2026) | 2,879.50 | USD/semester | https://adminfinance.fresnostate.edu/accountingservices/students/tuitionfees.html | 2026-10-24 | REAL |
| 263 | California State University, Sacramento tuition fee >6 units (Fall 2026 & Spring 2027) | 3,419.00 | USD/semester | https://www.csus.edu/administration-business-affairs/bursar/tuition-living-costs.html | 2026-10-24 | REAL |
| 264 | California State University, Sacramento total >6 units (Fall 2026 & Spring 2027) | 4,828.00 | USD/semester | https://www.csus.edu/administration-business-affairs/bursar/tuition-living-costs.html | 2026-10-24 | REAL |
| 265 | California State University, Sacramento total 0-6 units (Fall 2026 & Spring 2027) | 3,390.00 | USD/semester | https://www.csus.edu/administration-business-affairs/bursar/tuition-living-costs.html | 2026-10-24 | REAL |
| 266 | CSU nonresident tuition | 471.00 | USD/unit | https://adminfinance.fresnostate.edu/accountingservices/students/tuitionfees.html | 2026-10-24 | REAL |
| 267 | CSU systemwide tuition 2026-27 | 6,838 | USD/year (2 x 3,419) | https://www.csus.edu/administration-business-affairs/bursar/tuition-living-costs.html | 2026-10-24 | DERIVED |
| 268 | UC Tuition 2027-28 new CA resident (systemwide) | 16,278 | USD/year | https://admission.universityofcalifornia.edu/tuition-financial-aid/tuition-cost-of-attendance/ | 2026-10-24 | REAL |
| 269 | UC campus fees avg 2027-28 | 1,900 | USD/year | https://admission.universityofcalifornia.edu/tuition-financial-aid/tuition-cost-of-attendance/ | 2026-10-24 | REAL |
| 270 | UC total cost on campus 2027-28 (avg) | 49,078 | USD/year | https://admission.universityofcalifornia.edu/tuition-financial-aid/tuition-cost-of-attendance/ | 2026-10-24 | REAL |
| 271 | UC Merced 2026-27 total tuition+fees | 8,462 | USD/semester | https://studentbilling.ucmerced.edu/tuition-fees/tuition | 2026-10-24 | SAMPLE |
| 272 | Scorecard San Joaquin Delta College in-state tuition | 1,180 | USD/year | https://api.data.gov/ed/collegescorecard/v1/schools | 2026-10-24 | REAL |
| 273 | Scorecard San Joaquin Delta College avg net price (public) | 2,451 | USD/year | https://api.data.gov/ed/collegescorecard/v1/schools | 2026-10-24 | REAL |
| 274 | Scorecard Modesto Junior College in-state tuition | 1,276 | USD/year | https://api.data.gov/ed/collegescorecard/v1/schools | 2026-10-24 | REAL |
| 275 | Scorecard Modesto Junior College avg net price (public) | 5,954 | USD/year | https://api.data.gov/ed/collegescorecard/v1/schools | 2026-10-24 | REAL |
| 276 | Scorecard California State University-Stanislaus in-state tuition | 8,690 | USD/year | https://api.data.gov/ed/collegescorecard/v1/schools | 2026-10-24 | REAL |
| 277 | Scorecard California State University-Stanislaus avg net price (public) | 3,565 | USD/year | https://api.data.gov/ed/collegescorecard/v1/schools | 2026-10-24 | REAL |
| 278 | Scorecard California State University-Fresno in-state tuition | 8,224 | USD/year | https://api.data.gov/ed/collegescorecard/v1/schools | 2026-10-24 | REAL |
| 279 | Scorecard California State University-Fresno avg net price (public) | 5,418 | USD/year | https://api.data.gov/ed/collegescorecard/v1/schools | 2026-10-24 | REAL |
| 280 | Scorecard California State University-Sacramento in-state tuition | 9,014 | USD/year | https://api.data.gov/ed/collegescorecard/v1/schools | 2026-10-24 | REAL |
| 281 | Scorecard California State University-Sacramento avg net price (public) | 11,186 | USD/year | https://api.data.gov/ed/collegescorecard/v1/schools | 2026-10-24 | REAL |
| 282 | Scorecard University of California-Merced in-state tuition | 16,271 | USD/year | https://api.data.gov/ed/collegescorecard/v1/schools | 2026-10-24 | REAL |
| 283 | Scorecard University of California-Merced avg net price (public) | 11,583 | USD/year | https://api.data.gov/ed/collegescorecard/v1/schools | 2026-10-24 | REAL |

## 11. Open items and caveats

- **BLS May 2025 MSA values were not read.** Before a demo, a human can open `https://data.bls.gov/oes/#/area/0044700/2025` in a browser and paste the medians into `wages.json` under `bls_may2025_msa` if federal numbers are preferred. EDD values are official and fine to show; cite "CA EDD OEWS, 2026 Q1".
- **Small-cell wages have high RSE.** Examples: 11-9013 (100 jobs, RSE 5.5%) and 49-3041 (250 jobs). Show the RSE or a "small sample" badge.
- **11-9013 projections base (2,120) vs OEWS employment (100).** Projections cover self-employed farmers, while OEWS covers only wage-and-salary jobs in non-farm establishments. This is our interpretation of the program scopes and is UNVERIFIED on an EDD page. Do not mix the two numbers in one sentence.
- **UC Merced campus-specific fees are SAMPLE** (official pages blocked us). The UC systemwide 2027-28 estimate is REAL.
- **Mapper "terms" are not semesters.** MJC counts appear to include intersessions. For the Plan solver, use units/term load (e.g. 12-15 units per fall/spring term) rather than raw term counts. This is a modeling suggestion, not a source fact.
- **Nothing was copied from source pages except numbers and program names.** Prose above is our own summary.
