# O*NET data for the Foothold career-fit model

Retrieved 2026-10-24 (`date`: Sat Oct 24 11:55:53 PDT 2026). Owner of `data/raw/onet/`: this research task.
Machine-readable summary: `data/raw/onet/SELECTION.json`.

## TL;DR for builders

- **Release:** O*NET **31.0** Database (August 2026). The releases archive lists it as the current production database (https://www.onetcenter.org/db_releases.html). The site footer says "Site updated October 6, 2026".
- **License:** **CC BY 4.0**. Use the exact credit line in section 2, and always write the version number ("O*NET 31.0 Database").
- **The taxonomy has changed. Do not code against the classic layout:**
  - **Work Styles now has 21 elements, not 16.** They use IDs `1.D.*` (no longer `1.C.*`) and sit in 4 higher-order groups. The scales are now **WI** (Work Styles Impact, -3..+3) and **DR** (Distinctiveness Rank, 0..10). The old **IM/Importance scale is not in the file.** This changed in release 30.1 (December 2025).
  - **There is no longer a single "Skills" file.** It was split into `essential_skills.csv` (10 elements, `2.A.*`) and `transferable_skills.csv` (25 elements, `2.B.*`), added in 30.3. That makes 35 skills in total, rated on IM (1-5) and LV (0-7).
  - **There is no longer an "Interests" file.** It was renamed `career_interest_types.csv` in 30.3 (RIASEC, OI 1-7, plus IH high-point codes). A new `specific_interest_areas.csv` (41 elements) was added in 30.3.
- **Downloads:** all 8 individual CSVs downloaded fine (some needed retries). The full-database zip was **not** used.
- **Codes:** I checked all 8 career codes and all 34 related codes. Each one is in Occupation Data and has the full 42 Work Styles rows (21 elements x 2 scales). Each one also has Essential Skills, Transferable Skills, Career Interest Types and Specific Interest Areas rows.

---

## 1. Files in `data/raw/onet/`

Base URL: `https://www.onetcenter.org/dl_files/database/db_31_0_csv/`. The database page also offers Excel (`db_31_0_excel/<Name>.xlsx`) and JSON (`db_31_0_json/<name>.json`) for every file.

| file | data rows | bytes | sha256 (first 16) | contents |
|---|---:|---:|---|---|
| occupation_data.csv | 1,016 | 268,030 | a09eae1d6609686e | O*NET-SOC code, Title, Description |
| work_styles.csv | 37,422 | 4,329,846 | a3e5331df515dbc9 | Work Styles (1.D): WI + DR |
| essential_skills.csv | 18,200 | 2,328,135 | 68c4d31d8c550772 | Essential Skills (2.A): IM + LV |
| transferable_skills.csv | 45,500 | 6,081,245 | f17d0419e818a3bf | Transferable Skills (2.B): IM + LV |
| career_interest_types.csv | 8,307 | 1,136,078 | 19f452d51b81a4d5 | RIASEC (1.B.1): OI + IH |
| specific_interest_areas.csv | 73,062 | 8,712,834 | 3c59c823f228d4ee | Specific Interest Areas (1.B.3): OI + DS |
| content_model_reference.csv | 3,006 | 235,856 | 370033744006dbd5 | Element ID, Element Name, Description |
| scales_reference.csv | 33 | 1,006 | bcba23858ce21eca | Scale ID, Scale Name, Minimum, Maximum |

`SELECTION.json` has the full SHA-256 hashes. Row counts match the counts printed on the database page.

**Re-download command (Git Bash).** The server sometimes reset the connection (`curl: (35)/(56) Recv failure: Connection was reset`, `curl: (28)` connect timeout). Run the downloads one after another with retries:

```bash
cd data/raw/onet
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
for f in occupation_data work_styles essential_skills transferable_skills career_interest_types specific_interest_areas content_model_reference scales_reference; do
  curl -sS -L -A "$UA" --retry 4 --retry-delay 4 --retry-all-errors --connect-timeout 20 \
       -o "$f.csv" "https://www.onetcenter.org/dl_files/database/db_31_0_csv/$f.csv"; sleep 2
done
```

All files are plain ASCII CSV with a header row and quoted fields where needed. Read `O*NET-SOC Code` as a **string** (for example `"29-1141.00"`).

### Column layouts (verified from file headers and the 31.0 data dictionary)

- `occupation_data.csv`: `O*NET-SOC Code, Title, Description`
- `work_styles.csv`, `career_interest_types.csv`, `specific_interest_areas.csv`: `O*NET-SOC Code, Title, Element ID, Element Name, Scale ID, Scale Name, Data Value, Date, Domain Source`
- `essential_skills.csv`, `transferable_skills.csv`: `O*NET-SOC Code, Title, Element ID, Element Name, Scale ID, Scale Name, Data Value, N, Standard Error, Lower CI Bound, Upper CI Bound, Recommend Suppress, Not Relevant, Date, Domain Source`
- `scales_reference.csv`: `Scale ID, Scale Name, Minimum, Maximum`
- `content_model_reference.csv`: `Element ID, Element Name, Description`

### Coverage (computed from the files)

| domain | occupations | elements | scales (min..max) | Domain Source | Date values |
|---|---:|---:|---|---|---|
| Work Styles | 891 | 21 | WI Work Styles Impact (-3..3; observed -1.42..3.00); DR Distinctiveness Rank (0..10) | `AI/Expert` (all rows) | `12/2025` (all rows) |
| Essential Skills | 910 | 10 | IM Importance (1..5); LV Level (0..7; observed max 6.0) | `Analyst` | 06/2010 to 08/2026 (17 distinct; 08/2026 most common) |
| Transferable Skills | 910 | 25 | IM (1..5); LV (0..7; observed max 5.75) | `Analyst` | 06/2010 to 08/2026 (17 distinct; 08/2026 most common) |
| Career Interest Types | 923 | 9 (6 RIASEC + 3 high-points) | OI Occupational Interests (1..7); IH High-Point (0..6) | `Machine Learning/Expert` (7,839 rows), `Machine Learning` (468) | 02/2026, 11/2023 |
| Specific Interest Areas | 891 | 41 | OI (1..7); DS Summary Display Rank (0..100 per scales file; observed 0..8) | `AI/Expert` | 05/2026 |

- **125 of the 1,016 occupations have no Work Styles rows.** 77 of them are "All Other" titles; the rest are mostly specialty detail codes.
- **878 occupations have all of Work Styles, Essential Skills, Transferable Skills and Career Interest Types.** Use this set as the training universe for the career-fit model.
- **13 occupations have Work Styles but no Skills data.** One of them is `29-2042.00` Emergency Medical Technicians, so I used `29-2043.00` Paramedics in the related list instead.
- Essential Skills and Transferable Skills cover the same set of occupations. Specific Interest Areas covers the same set as Work Styles.

**IH high-point codes:** 0 = none, 1 = Realistic, 2 = Investigative, 3 = Artistic, 4 = Social, 5 = Enterprising, 6 = Conventional. This is from the 31.0 data dictionary for Career Interest Types. The elements are `1.B.1.g` (first), `1.B.1.h` (second) and `1.B.1.i` (third high-point). The RIASEC OI elements are `1.B.1.a`..`1.B.1.f`.

**Skills flags:**
- `Not Relevant = Y` appears only on LV rows (298 essential, 3,217 transferable). Treat LV as 0 for those rows.
- `Recommend Suppress = Y` (21 essential, 136 transferable) marks low-precision estimates. Down-weight or drop them.

---

## 2. License and required attribution (verified)

- License page: https://www.onetcenter.org/license_db.html (also the "Usage License" tab on https://www.onetcenter.org/database.html).
- The license is CC BY 4.0: https://creativecommons.org/licenses/by/4.0/. It covers "the downloadable files of the O*NET 31.0 Database". Other O*NET site content falls under a separate page: https://www.onetcenter.org/license_agreements.html.
- **Conditions:**
  - Credit the O*NET 31.0 Database and USDOL/ETA as the source.
  - Link to the license.
  - Say where changes were made.
- **Version number is required in the credit:** write "O*NET 31.0 Database", not "O*NET Database".

**Exact credit line, as supplied by the licensor, for verbatim use:**

> This page includes information from the O*NET 31.0 Database by the U.S. Department of Labor, Employment and Training Administration (USDOL/ETA). Used under the CC BY 4.0 license. O*NET® is a trademark of USDOL/ETA.

**Exact credit line for edits or additions.** This is the one Foothold needs, because we compute derived fit scores. `[Your name or company]` is replaced with "Foothold":

> This page includes information from the O*NET 31.0 Database by the U.S. Department of Labor, Employment and Training Administration (USDOL/ETA). Used under the CC BY 4.0 license. O*NET® is a trademark of USDOL/ETA. Foothold has modified all or some of this information. USDOL/ETA has not approved, endorsed, or tested these modifications.

Both strings are stored in `SELECTION.json` as `attribution` (modified version) and `attribution_unmodified`.

**UI and implementation rules, summarized from the license page:**
- Make "CC BY 4.0" a link to the license URL.
- Show the ® symbol when you name O*NET.
- Use "O*NET" only as an adjective, as in "O*NET data" or "the O*NET database". Do not use it as a noun or verb, or in plural or possessive form.
- The page recommends a list of changes, or a contact, so readers can tell what is ours. Suggestion: link a short "How Foothold uses O*NET data" note from the footer.
- Developer registration is optional: https://www.onetcenter.org/register.

Suggested placement: a footer on the Prove, Plan and Learn pages, and on any screen that shows O*NET-derived scores or titles.

---

## 3. Work Styles in 31.0: revised taxonomy

**Answer: the current release has 21 Work Styles elements, not the classic 16.**
- The data dictionary for 31.0 says ratings cover 891 occupations, with 21 rated elements on 2 scales.
- The file history lists 30.1 as the "most recent content update". In 30.1 the N, Standard Error, CI bounds and Recommend Suppress columns were also removed.

**Scales present:**
- `WI` = "Work Styles Impact", from -3.00 to +3.00. The dictionary describes it as the impact of the style on performance of the occupation's work, ranging from very detrimental to very beneficial.
- `DR` = "Distinctiveness Rank", from 0 to 10. It holds up to 10 beneficial styles that set the occupation apart from others. 1 = most distinctive and 0 = not ranked.

**No `IM` (Importance) rows exist in `work_styles.csv`.** In this file, each occupation has 1 to 10 non-zero DR values. 99 occupations have the full 10.

### The 21 elements (IDs and names exactly as in the file)

| group ID | group name | element_id | name |
|---|---|---|---|
| 1.D.1 | Proactive and Growth Oriented | 1.D.1.a | Innovation |
| | | 1.D.1.b | Achievement Orientation |
| | | 1.D.1.c | Intellectual Curiosity |
| | | 1.D.1.d | Tolerance for Ambiguity |
| | | 1.D.1.e | Initiative |
| | | 1.D.1.f | Adaptability |
| | | 1.D.1.g | Self-Confidence |
| | | 1.D.1.h | Perseverance |
| | | 1.D.1.i | Leadership Orientation |
| 1.D.2 | Interpersonally Oriented | 1.D.2.a | Humility |
| | | 1.D.2.b | Sincerity |
| | | 1.D.2.c | Empathy |
| | | 1.D.2.d | Cooperation |
| | | 1.D.2.e | Optimism |
| | | 1.D.2.f | Social Orientation |
| 1.D.3 | Conscientious and Rule Oriented | 1.D.3.a | Cautiousness |
| | | 1.D.3.b | Attention to Detail |
| | | 1.D.3.c | Dependability |
| | | 1.D.3.d | Integrity |
| 1.D.4 | Emotionally Resilient | 1.D.4.a | Stress Tolerance |
| | | 1.D.4.b | Self-Control |

The parent `1.D` is named "Work Styles" in `content_model_reference.csv`. Element descriptions are in that file's `Description` column, so load them at runtime instead of hard-coding them. Under CC BY 4.0 they can be shown in the UI with the credit line.

### Classic 16 compared with the new 21

**This mapping is our own name-similarity heuristic, not an official O*NET crosswalk (UNVERIFIED).** I found no old-to-new mapping on the Work Styles report page (https://www.onetcenter.org/reports/Work_Styles_New.html, "Revisiting the Work Styles Domain of the O*NET Content Model", HumRRO / National Center for O*NET Development, August 2024).

| classic name | 31.0 element (heuristic) | relation |
|---|---|---|
| Achievement/Effort | 1.D.1.b Achievement Orientation | renamed (similar) |
| Persistence | 1.D.1.h Perseverance | renamed (similar) |
| Initiative | 1.D.1.e Initiative | same name |
| Leadership | 1.D.1.i Leadership Orientation | renamed (similar) |
| Cooperation | 1.D.2.d Cooperation | same name |
| Concern for Others | 1.D.2.c Empathy | renamed (similar) |
| Social Orientation | 1.D.2.f Social Orientation | same name |
| Self-Control | 1.D.4.b Self-Control | same name |
| Stress Tolerance | 1.D.4.a Stress Tolerance | same name |
| Adaptability/Flexibility | 1.D.1.f Adaptability | renamed (similar) |
| Dependability | 1.D.3.c Dependability | same name |
| Attention to Detail | 1.D.3.b Attention to Detail | same name |
| Integrity | 1.D.3.d Integrity | same name |
| Independence | none | no same-named element |
| Innovation | 1.D.1.a Innovation | same name |
| Analytical Thinking | none (Intellectual Curiosity 1.D.1.c is the nearest in spirit) | no same-named element |

**New in 31.0 with no classic counterpart:** Intellectual Curiosity, Tolerance for Ambiguity, Self-Confidence, Humility, Sincerity, Optimism, Cautiousness.

**Discrepancy, UNVERIFIED:** WebFetch's summary of the August 2024 report page described 21 lower-order styles in **7** higher-order dimensions. The 31.0 database uses **4** groups (`1.D.1` to `1.D.4`). The dictionary also links a later report, "Updating Higher-order Work Style Dimensions in the O*NET Work Styles Taxonomy" (https://www.onetcenter.org/reports/Higher_Order_Styles.html), which I did not read. Code against the 4 groups in the CSV.

Related reports linked from the Work Styles dictionary page:
- https://www.onetcenter.org/reports/Work_Styles_New.html. PDF: https://www.onetcenter.org/dl_files/Work_Styles_New.pdf. Names spreadsheet: https://www.onetcenter.org/dl_files/Work_Styles_New_Names.xlsx.
- https://www.onetcenter.org/reports/Hybrid_AI_Ratings.html
- https://www.onetcenter.org/reports/Higher_Order_Styles.html

---

## 4. Career mapping (8 careers, all verified)

| career_id | Foothold title | O*NET-SOC | O*NET title | RIASEC (IH) | notes |
|---|---|---|---|---|---|
| logistics_lead | Logistics Operations Lead | 11-3071.00 | Transportation, Storage, and Distribution Managers | EC | See below |
| registered_nurse | Registered Nurse | 29-1141.00 | Registered Nurses | SCI | Detail codes 29-1141.01 to .04 exist; .00 is the general one |
| diesel_mechanic | Diesel and Heavy-Equipment Mechanic | 49-3031.00 | Bus and Truck Mechanics and Diesel Engine Specialists | RCI | Heavy-equipment side is 49-3042.00 (in related) |
| welder | Welder and Fabricator | 51-4121.00 | Welders, Cutters, Solderers, and Brazers | RC | Fabricator side is 51-2041.00 (in related) |
| electrician | Electrician (Apprenticeship Route) | 47-2111.00 | Electricians | RC | Entry and apprentice proxy is 47-3013.00 Helpers--Electricians (in related) |
| software_dev | Software Developer | 15-1252.00 | Software Developers | IC | |
| farm_ops_manager | Farm Operations Manager | 11-9013.00 | Farmers, Ranchers, and Other Agricultural Managers | ERC | First result in O*NET OnLine keyword search for "farm operations manager" |
| robotics_tech | Robotics and Automation Technician | 17-3024.01 | Robotics Technicians | RCI | Has full data. Broader parent 17-3024.00 is in related |

**Why logistics_lead maps to 11-3071.00.** For the phrase "logistics operations lead", O*NET OnLine keyword search ranks 11-3071.00 first. Logistics Analysts (13-1081.02), Logistics Engineers (13-1081.01) and Logisticians (13-1081.00) follow. Its Work Styles profile also fits a lead role: Initiative, Leadership Orientation and Adaptability are its top 3 DR styles, and its RIASEC code is E-C. Logisticians score as C-E-I, with Achievement Orientation and Cooperation most distinctive. Swap options, all in related with full data:
- 13-1081.00 Logisticians: a planner or analyst version of the role.
- 53-1042.00 or 53-1043.00 first-line supervisors: a warehouse-floor lead version.

**No career code needed a fallback.** All 8 are in `occupation_data.csv` with 42 Work Styles rows, 20 Essential, 50 Transferable, 9 Career Interest and 82 Specific Interest rows each.

### Work Styles WI for the 8 careers

Cells show the WI value; `(#n)` is the DR rank when it is non-zero. Computed from `work_styles.csv`.

| element_id | Work Style | logistics_lead | registered_nurse | diesel_mechanic | welder | electrician | software_dev | farm_ops_manager | robotics_tech |
|---|---|---|---|---|---|---|---|---|---|
| 1.D.1.a | Innovation | 1.25 | 1.20 | 0.84 | 0.33 | 0.82 | 2.51 (#1) | 1.36 | 1.49 |
| 1.D.1.b | Achievement Orientation | 2.11 (#4) | 1.20 | 1.12 | 0.97 | 1.35 | 2.14 (#3) | 2.01 (#3) | 1.69 |
| 1.D.1.c | Intellectual Curiosity | 1.17 | 1.41 | 0.97 | 0.49 | 0.94 | 2.33 (#4) | 1.02 | 1.82 |
| 1.D.1.d | Tolerance for Ambiguity | 1.33 | 1.41 | 0.25 | -0.63 | 0.00 | 1.72 | 1.49 | 1.01 |
| 1.D.1.e | Initiative | 2.03 (#1) | 1.32 | 0.76 | 0.33 | 1.00 | 1.59 | 1.89 | 1.05 |
| 1.D.1.f | Adaptability | 2.02 (#3) | 2.25 (#2) | 0.89 | 0.44 | 1.26 | 2.09 (#2) | 1.83 | 1.68 |
| 1.D.1.g | Self-Confidence | 1.83 | 1.66 | 0.82 | 0.80 | 1.24 | 1.47 | 1.76 | 1.13 |
| 1.D.1.h | Perseverance | 1.97 | 2.08 (#3) | 1.77 | 1.34 | 1.77 | 1.77 | 2.30 (#2) | 1.67 |
| 1.D.1.i | Leadership Orientation | 2.58 (#2) | 1.48 | -0.07 | -0.36 | 0.83 | 1.13 | 2.68 (#1) | 0.23 |
| 1.D.2.a | Humility | 0.47 | 1.28 | -0.08 | -0.20 | -0.01 | 0.56 | 0.53 | -0.08 |
| 1.D.2.b | Sincerity | 0.78 | 2.14 (#1) | 0.49 | 0.09 | 0.65 | 0.67 | 0.72 | 0.37 |
| 1.D.2.c | Empathy | 0.79 | 2.27 (#4) | -0.03 | -0.14 | 0.08 | 0.41 | 0.37 | -0.06 |
| 1.D.2.d | Cooperation | 1.77 | 2.64 (#8) | 0.71 | 0.35 | 1.00 | 1.20 | 0.51 | 0.95 |
| 1.D.2.e | Optimism | 0.69 | 1.56 | 0.34 | -0.01 | 0.52 | 0.49 | 1.01 | 0.34 |
| 1.D.2.f | Social Orientation | 1.24 | 2.24 (#7) | -0.14 | -0.27 | 0.38 | 0.86 | 0.65 | 0.07 |
| 1.D.3.a | Cautiousness | 1.99 | 2.32 (#9) | 1.96 | 2.03 (#1) | 2.50 (#1) | 1.76 | 1.47 | 1.99 |
| 1.D.3.b | Attention to Detail | 2.37 (#6) | 3.00 | 2.44 (#1) | 2.28 (#2) | 2.50 (#2) | 2.67 (#5) | 2.05 (#4) | 2.57 (#1) |
| 1.D.3.c | Dependability | 2.65 (#7) | 2.93 | 2.47 (#2) | 2.33 (#3) | 2.65 (#3) | 2.41 (#6) | 2.50 (#5) | 2.39 (#2) |
| 1.D.3.d | Integrity | 2.43 (#5) | 2.55 (#10) | 1.23 | 0.96 | 1.89 | 1.79 | 1.63 | 1.57 |
| 1.D.4.a | Stress Tolerance | 1.86 | 2.21 (#5) | 1.27 | 1.22 | 1.38 | 1.27 | 1.73 | 1.16 |
| 1.D.4.b | Self-Control | 1.70 | 2.14 (#6) | 0.75 | 0.87 | 1.31 | 0.70 | 1.34 | 0.92 |

**Model takeaway:** WI is high everywhere for Dependability and Attention to Detail (about 2.3 to 3.0). Raw WI cosine similarity will therefore over-reward those two. Use DR or z-scored WI (across the 878-occupation universe) to separate careers.

---

## 5. Related occupations (34, all verified)

All are in Occupation Data. Each has 42 Work Styles rows plus Essential, Transferable, Career Interest and Specific Interest rows. `related_groups` in `SELECTION.json` holds the grouping.

| group | onet_soc | onet_title | RIASEC | top-3 WI work styles |
|---|---|---|---|---|
| logistics | 13-1081.00 | Logisticians | CEI | Dependability 2.65, Attention to Detail 2.57, Cooperation 2.10 |
| logistics | 13-1081.02 | Logistics Analysts | CEI | Attention to Detail 2.57, Dependability 2.47, Cautiousness 1.82 |
| logistics | 11-3071.04 | Supply Chain Managers | EC | Dependability 2.65, Attention to Detail 2.44, Adaptability 2.30 |
| logistics | 53-1043.00 | First-Line Supervisors of Material-Moving Machine and Vehicle Operators | ECR | Dependability 2.62, Leadership Orientation 2.52, Cautiousness 2.21 |
| logistics | 53-3032.00 | Heavy and Tractor-Trailer Truck Drivers | RC | Dependability 2.65, Cautiousness 2.62, Attention to Detail 2.11 |
| logistics | 43-5071.00 | Shipping, Receiving, and Inventory Clerks | CRE | Dependability 2.47, Attention to Detail 2.37, Integrity 1.73 |
| warehouse_material_moving | 53-1042.00 | First-Line Supervisors of Helpers, Laborers, and Material Movers, Hand | ECS | Leadership Orientation 2.96, Dependability 2.56, Cooperation 2.22 |
| warehouse_material_moving | 53-7062.00 | Laborers and Freight, Stock, and Material Movers, Hand | RC | Dependability 2.11, Attention to Detail 1.26, Cautiousness 0.95 |
| warehouse_material_moving | 53-7051.00 | Industrial Truck and Tractor Operators | RC | Dependability 2.25, Cautiousness 2.03, Attention to Detail 1.69 |
| warehouse_material_moving | 53-7065.00 | Stockers and Order Fillers | CRE | Dependability 2.11, Attention to Detail 1.92, Integrity 1.40 |
| trades | 49-3042.00 | Mobile Heavy Equipment Mechanics, Except Engines | RCI | Dependability 2.65, Attention to Detail 2.50, Cautiousness 2.03 |
| trades | 49-3041.00 | Farm Equipment Mechanics and Service Technicians | RCI | Dependability 2.47, Attention to Detail 2.37, Cautiousness 1.79 |
| trades | 51-2041.00 | Structural Metal Fabricators and Fitters | RC | Attention to Detail 2.47, Dependability 2.37, Cautiousness 1.96 |
| trades | 47-3013.00 | Helpers--Electricians | RC | Dependability 2.14, Attention to Detail 1.86, Cooperation 1.57 |
| trades | 47-2152.00 | Plumbers, Pipefitters, and Steamfitters | RC | Dependability 2.56, Attention to Detail 2.19, Cautiousness 2.03 |
| trades | 49-9021.00 | Heating, Air Conditioning, and Refrigeration Mechanics and Installers | RC | Dependability 2.65, Attention to Detail 2.50, Cautiousness 2.06 |
| trades | 47-2231.00 | Solar Photovoltaic Installers | RC | Dependability 2.65, Attention to Detail 2.44, Cautiousness 2.35 |
| automation_manufacturing | 17-3024.00 | Electro-Mechanical and Mechatronics Technologists and Technicians | RCI | Attention to Detail 2.67, Dependability 2.47, Cautiousness 2.03 |
| automation_manufacturing | 49-9041.00 | Industrial Machinery Mechanics | RCI | Dependability 2.65, Attention to Detail 2.57, Cautiousness 2.10 |
| automation_manufacturing | 49-9071.00 | Maintenance and Repair Workers, General | RC | Dependability 2.65, Attention to Detail 2.25, Cautiousness 1.76 |
| automation_manufacturing | 51-9161.00 | Computer Numerically Controlled Tool Operators | RC | Attention to Detail 2.57, Dependability 2.30, Cautiousness 1.76 |
| health | 29-2061.00 | Licensed Practical and Licensed Vocational Nurses | SCR | Dependability 2.93, Attention to Detail 2.77, Cooperation 2.60 |
| health | 31-1131.00 | Nursing Assistants | SRC | Empathy 2.97, Cooperation 2.78, Dependability 2.65 |
| health | 31-9092.00 | Medical Assistants | CSR | Attention to Detail 2.77, Dependability 2.65, Cooperation 2.47 |
| health | 29-2043.00 | Paramedics | SRI | Stress Tolerance 3.00, Self-Control 3.00, Dependability 2.93 |
| health | 29-1171.00 | Nurse Practitioners | ISC | Attention to Detail 3.00, Dependability 2.93, Integrity 2.93 |
| tech | 15-1232.00 | Computer User Support Specialists | CRI | Dependability 2.41, Attention to Detail 2.34, Cooperation 1.99 |
| tech | 15-1254.00 | Web Developers | CI | Attention to Detail 2.57, Innovation 2.30, Dependability 2.19 |
| tech | 15-1212.00 | Information Security Analysts | CI | Attention to Detail 3.00, Integrity 2.93, Cautiousness 2.78 |
| agriculture_food | 45-1011.00 | First-Line Supervisors of Farming, Fishing, and Forestry Workers | ERC | Leadership Orientation 3.00, Dependability 2.53, Perseverance 2.01 |
| agriculture_food | 45-2091.00 | Agricultural Equipment Operators | RC | Dependability 2.33, Attention to Detail 1.76, Cautiousness 1.50 |
| agriculture_food | 19-4012.01 | Precision Agriculture Technicians | RIC | Attention to Detail 2.67, Innovation 2.27, Dependability 2.19 |
| agriculture_food | 45-2092.00 | Farmworkers and Laborers, Crop, Nursery, and Greenhouse | RC | Dependability 2.30, Perseverance 1.74, Attention to Detail 1.57 |
| agriculture_food | 51-3092.00 | Food Batchmakers | RC | Dependability 2.59, Attention to Detail 2.41, Cautiousness 1.82 |

**Substitution made:** `29-2042.00` Emergency Medical Technicians exists and has Work Styles rows, but has no Essential or Transferable Skills rows. I used `29-2043.00` Paramedics, which has full data.

**Codes that do not exist in O*NET-SOC 2019 (do not use):** `53-1047.00`. The 2019 taxonomy uses 53-1042.00, 53-1043.00, 53-1044.00 and 53-1049.00 instead (checked in `occupation_data.csv`).

---

## 6. How to build the career-fit features (suggested)

Stdlib-only loader. pandas also works if the ml stack already has it; do not add packages for this alone.

```python
import csv, collections
RAW = "data/raw/onet"

def rows(name):
    with open(f"{RAW}/{name}", encoding="utf-8", newline="") as fh:
        yield from csv.DictReader(fh)

ws = collections.defaultdict(dict)   # code -> {element_id: {"WI": x, "DR": y}}
for r in rows("work_styles.csv"):
    ws[r["O*NET-SOC Code"]].setdefault(r["Element ID"], {})[r["Scale ID"]] = float(r["Data Value"])

skills = collections.defaultdict(dict)  # code -> {element_id: IM}
for f in ("essential_skills.csv", "transferable_skills.csv"):
    for r in rows(f):
        if r["Scale ID"] == "IM":
            skills[r["O*NET-SOC Code"]][r["Element ID"]] = float(r["Data Value"])

riasec = collections.defaultdict(dict)  # code -> {"1.B.1.a".."1.B.1.f": OI}
for r in rows("career_interest_types.csv"):
    if r["Scale ID"] == "OI":
        riasec[r["O*NET-SOC Code"]][r["Element ID"]] = float(r["Data Value"])
```

- **Work Styles vector (21-d):**
  - Order elements by `SELECTION.json["work_styles"]`.
  - Map to [0,1] with `(WI + 3) / 6`, or z-score each element across the 878-occupation universe (better contrast; see the takeaway in section 4).
  - Optional distinctiveness weight: `w = (11 - DR) / 10` if `DR > 0`, else a small base weight such as 0.2.
- **Sim telemetry to Work Styles:** have the Try workday score the user on the same 21 IDs, so features line up one-to-one. Suggested proxies: Stress Tolerance from a crisis event, Cooperation from coworker help, Attention to Detail from error catches.
- **Skills (35-d):** IM normalized as `(IM - 1) / 4`. LV ranges 0-7; set LV to 0 where `Not Relevant = Y`.
- **Interests (6-d):** OI normalized as `(OI - 1) / 6`. IH gives a 1-3 letter Holland code for display.
- **Combined fit score:** a weighted cosine per domain, for example `0.5 * styles + 0.3 * interests + 0.2 * skills`. Calibrate the weights later.
- **Graph model (Learn):** `related_groups` and the RIASEC codes above give easy edges. O*NET also publishes `related_occupations.csv` (18,460 rows; 10 primary and 10 supplemental per occupation) if a builder wants official occupation-to-occupation edges. I did **not** download it (not in scope).

---

## 7. What failed or remains unverified

- **Download hiccups.** These first attempts failed:
  - `transferable_skills.csv`, `career_interest_types.csv`, `specific_interest_areas.csv`, `content_model_reference.csv`: `curl (35)/(56) Connection was reset`.
  - Several dictionary pages: `(35)` resets, and one `(28)` connect timeout.

  All succeeded on sequential retry with `--retry 4 --retry-all-errors`. URLs are as listed in section 1.
- **Not fetched:** https://www.onetcenter.org/whatsnew.html failed with a connection reset on the single attempt. I did not need it.
- **UNVERIFIED:**
  - The classic-to-new Work Styles mapping in section 3 is a heuristic. No official crosswalk was found.
  - The "7 higher-order dimensions" figure comes from a WebFetch summary of the 2024 report page. The 4 groups in the database are verified.
  - The 35 skill element IDs (`2.A.1.a` to `2.B.5.d`) appear to be the same IDs as the pre-30.3 combined Skills file. That is from memory and was not re-checked against an archived release.

## Sources (retrieved 2026-10-24)

- O*NET 31.0 Database page, including file list, row counts and license tab: https://www.onetcenter.org/database.html
- Releases archive (31.0 = August 2026, current production): https://www.onetcenter.org/db_releases.html
- Database license and credit lines: https://www.onetcenter.org/license_db.html
- 31.0 data dictionary pages:
  - https://www.onetcenter.org/dictionary/31.0/excel/work_styles.html
  - https://www.onetcenter.org/dictionary/31.0/excel/career_interest_types.html
  - https://www.onetcenter.org/dictionary/31.0/excel/specific_interest_areas.html
  - https://www.onetcenter.org/dictionary/31.0/excel/essential_skills.html
  - https://www.onetcenter.org/dictionary/31.0/excel/transferable_skills.html
  - https://www.onetcenter.org/dictionary/31.0/excel/occupation_data.html
- Work Styles report page: https://www.onetcenter.org/reports/Work_Styles_New.html
- O*NET OnLine keyword search:
  - https://www.onetonline.org/find/result?s=logistics%20operations%20lead
  - https://www.onetonline.org/find/result?s=farm%20operations%20manager
- CSV downloads: `https://www.onetcenter.org/dl_files/database/db_31_0_csv/<file>.csv` (8 files, section 1)

This document includes information from the O*NET 31.0 Database by the U.S. Department of Labor, Employment and Training Administration (USDOL/ETA). Used under the CC BY 4.0 license. O*NET® is a trademark of USDOL/ETA. Foothold has modified all or some of this information. USDOL/ETA has not approved, endorsed, or tested these modifications.
