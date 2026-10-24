# Foothold research: verified statistics and links

Retrieved: **2026-10-24** (run date; `date` on the research machine: Sat Oct 24 2026, PDT). All items were read from the original publisher pages and, where possible, from the data files behind their charts.

Method note: WebFetch got HTTP 403 from ppic.org, so pages were fetched with `curl` using a browser user agent. The chart numbers come from the publishers' own Datawrapper / dashboard CSV files (commands are in section 6).

Rule for builders (from CONTRACTS section 1): show only items marked VERIFIED or PARTIALLY VERIFIED below, word for word, with the source link and the label `REAL`.

## 1. Display table (copy these sentences exactly)

| id | Verdict | Display sentence | Source label + URL |
|---|---|---|---|
| `ppic_sjv_ba_path` | VERIFIED | At current rates, only 26% of San Joaquin Valley ninth graders are on a path to a bachelor's degree, compared with 35% in the rest of California. | PPIC, *Pathways to College Completion in the San Joaquin Valley* (Aug 2024): https://www.ppic.org/publication/pathways-to-college-completion-in-the-san-joaquin-valley/ |
| `ppic_sjv_ba_share` | VERIFIED | Among California's regions, the San Joaquin Valley has the lowest share of adults ages 25–54 with at least a bachelor's degree: 19%, vs. 40% statewide (2021 data). | Same PPIC report (text plus Figure 3 data) |
| `p2p_sjv_attainment` | VERIFIED | In the San Joaquin Valley, associate's degree attainment is on par with the state (9% vs. 8% of adults ages 25–54), but bachelor's attainment is about half (18% vs. 37%). Gaps by race and ethnicity are wide: 10% of Latinx adults hold a bachelor's degree or higher, vs. 38% of Asian adults. | California Competes, *Postsecondary to Prosperity* dashboard (American Community Survey 2019 data): https://p2p.californiacompetes.org/p2p/regions?region=san-joaquin-valley-region |
| `lifeline_988` | VERIFIED | You don't have to go through this alone. Call or text 988, or chat at chat.988lifeline.org, to reach the 988 Suicide & Crisis Lifeline. It's free and available 24/7. En español: marque 988 y luego presione 2, o envíe AYUDA al 988 por mensaje de texto. You can also reach out to someone you trust. | 988 Suicide & Crisis Lifeline: https://988lifeline.org/ (chat: https://chat.988lifeline.org/; Spanish: https://988lifeline.org/es/inicio/) |
| `ppm_companion` | VERIFIED | Your college may already publish official program maps. Check its Program Pathways Mapper before you plan classes; Foothold works alongside it and does not replace your counselor. | Program Pathways Mapper: https://programmapper.org/ (college links in section 5) |
| `ppm_origin` | VERIFIED (origin wording corrected) | The Program Pathways Mapper began at Bakersfield College (Kern Community College District) with the California Community Colleges Chancellor's Office. | https://programmapper.org/about/ |

## 2. PPIC: college completion in the San Joaquin Valley

- **Title:** *Pathways to College Completion in the San Joaquin Valley*. Type: Report, **August 2024**.
- **Authors:** Hans Johnson, Olga Rodriguez, Cesar Alesi Perez, Marisol Cuellar Mejia.
- **URL:** https://www.ppic.org/publication/pathways-to-college-completion-in-the-san-joaquin-valley/ (canonical; `https://ppic.org/?p=80145` redirects here).
  - Technical appendix: https://www.ppic.org/wp-content/uploads/0824hjr-appendix.pdf
  - Policy brief: https://www.ppic.org/publication/policy-brief-pathways-to-college-completion-in-the-san-joaquin-valley/
- **Region:** 8 counties: San Joaquin, Stanislaus, Merced, Madera, Fresno, Kings, Tulare and Kern (report figure notes).

**Claim A: 26% vs 35% on a path to a bachelor's degree.** VERIFIED, numbers exact.
- Quote (Key Takeaways): "only 26 percent of San Joaquin Valley ninth graders are on a path to earning a bachelor’s degree, compared to 35 percent…" The sentence ends "in the rest of the state".
- Qualifier in the same sentence: "At current rates of high school graduation, college enrollment, and college completion". Keep "at current rates" in the UI. This is a projection, not a measured outcome for one class.
- The comparison group is the **rest of the state** (California minus the Valley), not the statewide average.
- Figure 5 data (synthetic cohort of 1,000 ninth graders), Valley vs rest of state:

  | Step | Valley | Rest of state |
  |---|---:|---:|
  | Graduate from high school | 868 | 873 |
  | Enroll in college | 512 | 567 |
  | Attend a 4-year college | 298 | 385 |
  | Earn a BA | 257 | 353 |

  257 rounds to 26% and 353 to 35%.

**Claim B: lowest share of adults 25-54 with a bachelor's degree.** VERIFIED, with a wording fix.
- Quote: "the San Joaquin Valley has the lowest share of California’s adults (ages 25–54) with at least a bachelor’s degree"
- Fix: say "**at least** a bachelor's degree", meaning a bachelor's or higher.
- Figure 3 data ("Percent of 25–54 year olds with at least a bachelor's degree, 2021"; source: ACS):

  | Region | Share |
  |---|---:|
  | Bay Area | 57% |
  | Orange County | 48% |
  | San Diego County | 45% |
  | Los Angeles County | 42% |
  | Sacramento Metro | 39% |
  | Inland Empire | 25% |
  | **San Joaquin Valley** | **19%** |
  | State | 40% |

- Figure 3 shows only these 7 regions. An independent check with the California Competes data (ACS 2019, same age range, all 12 of its regions) also puts the Valley lowest: Valley 18.1%, Imperial 19.1%, Central Sierra 19.4%. This supports "among California's regions".

Other REAL figures in the report, usable later with the same citation:
- College-going rate of recent high school graduates: Valley 57%, rest of state 65%.
- High school graduation: Valley 85.1%, rest of state 86.4%.

## 3. California Competes: Postsecondary to Prosperity

- **Claim source:** news post "Postsecondary to Prosperity: Expanding Opportunity Across the San Joaquin Valley", California Competes, **December 10, 2020**: https://californiacompetes.org/postsecondary-to-prosperity-expanding-opportunity-across-the-san-joaquin-valley/
- **Dashboard (Valley page):** https://p2p.californiacompetes.org/p2p/regions?region=san-joaquin-valley-region. Home: https://p2p.californiacompetes.org/
- **Chart:** "What is the highest level of education attained?" The chart's help text: "Percentage distribution of highest educational attainment among individuals 25-54 years old… Source: American Community Survey 2019." Bachelor's includes graduate degrees.
- **Region:** 8 counties: Fresno, Kern, Kings, Madera, Merced, San Joaquin, Stanislaus, Tulare. Population 4,266,253 (11% of the state); 14 community colleges, 3 CSU campuses, 1 UC campus.
- **Verdict:** VERIFIED. The quoted claim is in the post, and the current dashboard data agree with it.
- **Quote:** "Associate’s degree attainment matches the statewide average, but bachelor’s degree attainment is nearly half the statewide average with dramatic differences by race and ethnicity."

Dashboard data, adults 25-54, ACS 2019. Data file `upload-11-17-22/pctschatt/San-Joaquin-Valley-region_pctschatt.csv`:

| Group | Associate's (Valley) | Associate's (state) | Bachelor's or higher (Valley) | Bachelor's or higher (state) |
|---|---:|---:|---:|---:|
| All adults 25-54 | 9.0% | 7.8% | 18.1% | 37.1% |
| Latinx | 7.4% | 6.9% | 10.1% | 16.0% |
| White | 11.7% | 8.7% | 26.1% | 50.3% |
| Asian | 10.5% | 7.0% | 37.7% | 63.4% |
| Black | 6.3% | 9.2% | 17.9% | 29.9% |
| Native American or Alaska Native | 6.5% | 7.8% | 10.7% | 17.3% |

The Valley's bachelor's rate is 0.49x the state rate (DERIVED: 18.1 / 37.1).

**Do NOT display** the 2020 post's example "just 8 percent of Latinx residents hold a bachelor’s degree compared with 32 percent of Asian residents". The current dashboard data say 10.1% vs 37.7%, so the post's numbers are an older vintage.

The race/ethnicity labels (Latinx, etc.) are the dashboard's own terms.

## 4. 988 Suicide & Crisis Lifeline

**Verdict:** VERIFIED (https://988lifeline.org/ and https://988lifeline.org/get-help/).

- **Call or text:** the home page links `tel:988` and `sms:988`. Quote: "Call, text, or chat with a 988 Lifeline counselor for help during difficult moments anytime, day or night."
- **Hours and cost:** "The 988 Lifeline is available 24/7/365. Your conversations are free and confidential."
- **Official chat:** https://chat.988lifeline.org/
  - This is the link the official site uses; `https://988lifeline.org/chat/` redirects there. HTTP 200 on 2026-10-24.
  - Chat FAQ: https://988lifeline.org/faq/988-lifeline-chat/
- **Spanish:** "To call a Spanish-speaking counselor, dial 988 and then press 2. To text with a Spanish-speaking counselor, text AYUDA to 988."
  - For Spanish chat, the site says to "start a chat in Spanish".
  - Spanish site: https://988lifeline.org/es/inicio/ ("La línea 988 está disponible 24/7/365").
- **Also on the site:**
  - Veterans: call 988 and press 1, or text 838255.
  - Deaf and hard of hearing: 988 Videophone, https://988lifeline.org/deaf-hard-of-hearing-hearing-loss/
- **Safety notes for the UI:**
  - The display sentence leaves out "confidential" on purpose. CONTRACTS says Foothold never makes confidentiality claims, so Foothold should not repeat 988's own claim in its voice.
  - "911" does not appear on the pages read, so it was not verified here.

## 5. Program Pathways Mapper (complementary tool)

**Verdict:** VERIFIED. The tool is real, and every link below returned HTTP 200 on 2026-10-24.

**Origin, with a wording fix.** The original claim said the tool was built by "Central Valley community colleges". Say instead that it began at one Valley college (Bakersfield College, Kern CCD) together with the state Chancellor's Office. It is now a statewide tool.
- Quote: "The Program Pathways Mapper began as a collaborative effort of Bakersfield College … and the California Community Colleges Chancellor’s Office" (https://programmapper.org/about/).
- The same page says KCCD received state funding in 2023 to roll PPM out to all public colleges in California. The Foundation for California Community Colleges administers the statewide expansion.
- Program list: https://programmapper.org/ppm-schools/. The main site describes "clear, faculty-approved program maps".

Central Valley sites, taken from the official PPM schools list:

| Institution | URL | Check |
|---|---|---|
| San Joaquin Delta College (Stockton) | https://programmap.deltacollege.edu/ | 200, title "San Joaquin Delta College \| Program Pathways Mapper" |
| Modesto Junior College | https://programmap.mjc.edu/ | 200, own title |
| Merced College | https://merced.programmapper.com/ | 200; JavaScript app, the PPM API maps this host to `merced` |
| Madera College | https://programmap.maderacollege.edu/ | 200, own title |
| Clovis Community College | https://programmap.cloviscollege.edu/ | 200; JavaScript app, API id `clovis` |
| Reedley College | https://programmap.reedleycollege.edu/ | 200, own title |
| Coalinga College (West Hills CCD) | https://programmapper.coalingacollege.edu/academics | 200; JavaScript app, API id `west_hills_coalinga` |
| Porterville College | https://pathwaysmap.portervillecollege.edu/ | 200; JavaScript app, API id `porterville` |
| Bakersfield College | https://programmap.bakersfieldcollege.edu/ | 200, own title |
| CSU Bakersfield | https://programmap.csub.edu/ | 200, own title |
| UC Merced | https://programmap.ucmerced.edu/ | 200; JavaScript app, API id `uc_merced` |

Notes:
- The Clovis map content only goes up to catalog year 2023 in the API (`latestSiteContentIdsByYear` 2022–2023), so it may be stale.
- `docs/research/data-wages-programs.md` section 8 lists Merced and Porterville as UNVERIFIED at guessed hostnames. The real hostnames are the ones above.
- Fresno City College, College of the Sequoias and Columbia College are not on the PPM list, so they are not verified.

## 6. Reproduce (run date 2026-10-24)

```bash
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
curl -sL --ssl-no-revoke -A "$UA" https://www.ppic.org/publication/pathways-to-college-completion-in-the-san-joaquin-valley/   # report text
curl -sL --ssl-no-revoke -A "$UA" https://datawrapper.dwcdn.net/GwUjq/1/dataset.csv    # PPIC Fig 3 (BA+ share, 25-54, 2021)
curl -sL --ssl-no-revoke -A "$UA" https://datawrapper.dwcdn.net/fCHqC/14/dataset.csv   # PPIC Fig 5 (1,000-student pathway)
B=https://p2p.californiacompetes.org/assets/p2p-data/upload-11-17-22/pctschatt
curl -sL --ssl-no-revoke -A "$UA" $B/San-Joaquin-Valley-region_pctschatt.csv          # P2P Valley attainment
curl -sL --ssl-no-revoke -A "$UA" $B/Statewide-region_pctschatt.csv                   # P2P statewide attainment
curl -sL --ssl-no-revoke -A "$UA" https://988lifeline.org/get-help/                   # 988 Spanish, chat, 24/7
curl -sG --ssl-no-revoke -A "$UA" https://b.api.programmapper.com/colleges --data-urlencode "url=https://merced.programmapper.com"   # PPM host -> college id
```

## 7. Machine-readable copy

```json
{
  "retrieved": "2026-10-24",
  "items": [
    {"id": "ppic_sjv_ba_path", "verdict": "VERIFIED", "provenance": "REAL",
     "text": "At current rates, only 26% of San Joaquin Valley ninth graders are on a path to a bachelor's degree, compared with 35% in the rest of California.",
     "source": "PPIC, Pathways to College Completion in the San Joaquin Valley (Aug 2024)",
     "url": "https://www.ppic.org/publication/pathways-to-college-completion-in-the-san-joaquin-valley/"},
    {"id": "ppic_sjv_ba_share", "verdict": "VERIFIED", "provenance": "REAL",
     "text": "Among California's regions, the San Joaquin Valley has the lowest share of adults ages 25–54 with at least a bachelor's degree: 19%, vs. 40% statewide (2021 data).",
     "source": "PPIC, Pathways to College Completion in the San Joaquin Valley (Aug 2024), Figure 3",
     "url": "https://www.ppic.org/publication/pathways-to-college-completion-in-the-san-joaquin-valley/"},
    {"id": "p2p_sjv_attainment", "verdict": "VERIFIED", "provenance": "REAL",
     "text": "In the San Joaquin Valley, associate's degree attainment is on par with the state (9% vs. 8% of adults ages 25–54), but bachelor's attainment is about half (18% vs. 37%). Gaps by race and ethnicity are wide: 10% of Latinx adults hold a bachelor's degree or higher, vs. 38% of Asian adults.",
     "source": "California Competes, Postsecondary to Prosperity dashboard (ACS 2019 data)",
     "url": "https://p2p.californiacompetes.org/p2p/regions?region=san-joaquin-valley-region"},
    {"id": "lifeline_988", "verdict": "VERIFIED", "provenance": "REAL",
     "text": "You don't have to go through this alone. Call or text 988, or chat at chat.988lifeline.org, to reach the 988 Suicide & Crisis Lifeline. It's free and available 24/7. En español: marque 988 y luego presione 2, o envíe AYUDA al 988 por mensaje de texto. You can also reach out to someone you trust.",
     "source": "988 Suicide & Crisis Lifeline",
     "url": "https://988lifeline.org/", "chat_url": "https://chat.988lifeline.org/", "es_url": "https://988lifeline.org/es/inicio/"},
    {"id": "ppm_origin", "verdict": "VERIFIED", "provenance": "REAL",
     "text": "The Program Pathways Mapper began at Bakersfield College (Kern Community College District) with the California Community Colleges Chancellor's Office.",
     "source": "Program Pathways Mapper, About", "url": "https://programmapper.org/about/"}
  ],
  "ppm_links": [
    {"name": "San Joaquin Delta College", "url": "https://programmap.deltacollege.edu/"},
    {"name": "Modesto Junior College", "url": "https://programmap.mjc.edu/"},
    {"name": "Merced College", "url": "https://merced.programmapper.com/"},
    {"name": "Madera College", "url": "https://programmap.maderacollege.edu/"},
    {"name": "Clovis Community College", "url": "https://programmap.cloviscollege.edu/"},
    {"name": "Reedley College", "url": "https://programmap.reedleycollege.edu/"},
    {"name": "Coalinga College", "url": "https://programmapper.coalingacollege.edu/academics"},
    {"name": "Porterville College", "url": "https://pathwaysmap.portervillecollege.edu/"},
    {"name": "Bakersfield College", "url": "https://programmap.bakersfieldcollege.edu/"},
    {"name": "CSU Bakersfield", "url": "https://programmap.csub.edu/"},
    {"name": "UC Merced", "url": "https://programmap.ucmerced.edu/"}
  ]
}
```
