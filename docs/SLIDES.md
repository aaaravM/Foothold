# Slide text for the Canva deck (paste-ready)

**First, rename the Canva file.** It's still called "Copy of MentoLab". Rename it to **"Foothold"** (in Canva: click the file name at the top → type the new name).

The deck has 7 slides plus a new Results slide (8 total). Every number comes from `ml/artifacts/metrics.json` or `docs/research/stats.md`.

---

## Slide 1: Title

**Foothold**
Try the job. Prove the skill. Get the foothold.

*Career discovery and planning for California's Central Valley*

[Team names] · [Hackathon name] · October 2026

---

## Slide 2: The Problem

**The Central Valley has the jobs and the colleges, but no map between them.**

> At current rates, only **26%** of San Joaquin Valley ninth graders are on a path to a bachelor's degree, compared with **35%** in the rest of California.
> *Source: PPIC, "Pathways to College Completion in the San Joaquin Valley" (Aug 2024), ppic.org*

- Career quizzes ask what you *like*. Nobody lets you *try* the work first.
- Real plans have to fit your work hours, budget and bus route.
- Young people without a network don't get a foot in the door with local employers.

Optional second stat (also verified, same source): Among California's regions, the San Joaquin Valley has the lowest share of adults ages 25–54 with at least a bachelor's degree: 19%, vs. 40% statewide (2021 data).

**Design notes:**
- **Replace the "blind man" graphic.** Use a Central Valley image instead: a map of the 8 counties (San Joaquin, Stanislaus, Merced, Madera, Fresno, Kings, Tulare, Kern), or a road or field photo.
- **Delete the "prices rising" line.** It has no source.
- Keep the "at current rates" wording. It's a projection, and the comparison is with the *rest of the state*, not the statewide average.

---

## Slide 3: How it works

**Three steps, with people in charge at every one**

1. **Try the job**: a workday sim where **3 AI coworkers react in parallel** to your choices.
   - **Any career**: 8 core careers, or search any O*NET 31.0 occupation and get a workday **generated live** from its O*NET work styles plus web research.
   - **Personalized moments**: rewritten for you, while each choice keeps its trait deltas so the selector's math holds.
   - **Free-text answers**: a 4th "Something else..." option, scored by the LLM (crisis text routes to 988).
   - **Adaptive selector**: Bayesian inference that picks the next moment by expected information gain. *(This is not deep RL.)*
   - **MLP career-fit model** on O*NET 31.0's 21 work styles → your top careers.
2. **Plan the route**: type your limits in plain English, and you **confirm** the rules.
   - **OR-Tools CP-SAT solver** plans every route in milliseconds, with a greedy baseline beside it.
   - Reject a plan and your reason becomes a new rule. Approve it and it goes on your board.
3. **Get the foothold**:
   - **GNN "Picked for you"**: courses and jobs, each with a one-line reason.
   - **Tavily "Live in your area"**: a live web-research agent runs 3 searches in parallel, ranks sources and writes a cited summary that drops unsupported numbers.
   - **Consent-gated employer portal**: blind skills-only cards and a four-fifths fairness check. Employers have to ask, and the learner decides.

**Under the hood:** 5 **LangGraph** agents (sim, pathway, employer, coach, research) with **human-approval interrupts** · every LLM number fact-checked · **988 safety routing** before any AI reply

**Image:** put **`docs/images/langgraph-sim.png`** on this slide (right half, or a narrow column). It's the real LangGraph sim graph, exported from the same graph LangSmith / LangGraph Studio display. Caption: *"The sim agent graph (LangGraph): coworkers fan out in parallel; present_and_wait is a human interrupt."* The image is tall (1600 × 3811 px), so crop it to the top half (`select_event` → `update_state`) if space is tight. Other graphs: `docs/images/langgraph-pathway.png`, `langgraph-employer.png`, `langgraph-coach.png`.

---

## Slide 4: Built with

| Layer | Tools |
|---|---|
| **Frontend** | Next.js 16 · React · TypeScript · Tailwind CSS · shadcn/ui · Motion · Cult UI · Watermelon UI · Skiper UI |
| **AI agents & API** | Python · FastAPI · LangGraph · OpenAI gpt-6-luna · **Tavily** (live web-research agent) |
| **AI features** | Any-career workday generation · personalized moments · free-text answers scored by the LLM |
| **ML & optimisation** | PyTorch · PyTorch Geometric · scikit-learn · OR-Tools CP-SAT · NetworkX |
| **Data** | O*NET 31.0 (CC BY 4.0) · CA EDD OEWS wages |
| **Infra** | Netlify (foothold-valley.netlify.app) · Supabase Postgres · Cloudflare Tunnel · Git |
| **Testing** | pytest (231 passed) · golden-path end-to-end check (25/25) |

**Design note:** remove **Vite, Docker, AWS and Redis**. We don't use them.

---

## NEW slide (after Built with): Results

**Measured, not claimed** *(all on synthetic test data; no real learners yet)*

| Model | Foothold | Baseline |
|---|---|---|
| Career fit (42 occupations) | MLP top-3 **91.96%** | cosine 90.38% |
| Adaptive selector: events to a confident match | **12.8** | random 16.9 · fixed 17.1 |
| GNN recommender: new learners (NDCG@10) | **0.267** | MF 0.164 · popularity 0.181 |
| GNN recommender: course picks (NDCG@10) | 0.134 | **MF 0.169 (baseline wins)** |
| CP-SAT planner: solve time | p50 **15 ms** · p95 190 ms | |
| Fact-checker: wrong numbers caught | **563 / 563** | 0 false alarms |
| Fairness (four-fifths rule) | pooled 0.88, but **only 1 of 8 postings pass** | we show it anyway |

Footer: *Source: ml/artifacts/metrics.json. All of this was measured on synthetic data.*

(Rounding: 0.9196 → 91.96%, 12.755 → 12.8, 16.851 → 16.9, 17.133 → 17.1, 0.2669 → 0.267, 0.1635 → 0.164, 0.1809 → 0.181, 0.1342 → 0.134, 0.1686 → 0.169, 189.6 → 190, 0.8804 → 0.88.)

---

## Slide 5: Demo

**Live demo**
Two tabs: Luis tries a diesel workday → sees live local research and his route near Stockton → Tri-Valley Freight asks → Luis says yes.

*All people and employers are fictional.*

---

## Slide 6: Why it matters

**Built for the Central Valley**

- **Try before you commit.** Experience a real workday before spending a semester or your savings.
- **Plans that fit real life**: work hours, budget, bus routes, kids. Built on real local wages and college costs.
- **Peer support circles.** Learners help each other, and a coach helps with workplace conflict and EQ. Anyone in crisis is routed to the 988 Lifeline.
- **Consent-based employer connections.** Employers see skills, not names. Learners decide who sees them.
- **Honest by design.** Every number is labelled REAL, SAMPLE, SYNTHETIC or FICTIONAL.

**Design note:** replace "mentorship" everywhere with the two bullets above (peer support circles, consent-based employer connections).

---

## Slide 7: Thank you

**Thank you**
Foothold: Try the job. Prove the skill. Get the foothold.

[Demo link] · [Repo / Devpost link] · [Team names]

*O*NET® 31.0 data by USDOL/ETA, used under CC BY 4.0 and modified by Foothold. All people and employers shown are fictional.*
