# Foothold: Try the job. Prove the skill. Get the foothold.

## Inspiration

In California's Central Valley, the jobs are here (logistics, health care, diesel and ag mechanics, electrical work), and so are the colleges. What's missing is a map between them. At current rates, only 26% of San Joaquin Valley ninth graders are on a path to a bachelor's degree, compared with 35% in the rest of California (PPIC, *Pathways to College Completion in the San Joaquin Valley*, Aug 2024). Career quizzes ask you what you *like*. We wanted something that lets you *try* a job, then shows a route you can actually take with your hours, your budget and your bus line.

## What it does

- **Sign up where you live**: pick one of 16 Central Valley places and see the nearest campuses with approximate drive minutes.
- **Try the job**: a short workday sim in one of 8 core careers, or **search any career** across every O*NET 31.0 occupation with work-style data (those workdays are generated live from O*NET work styles plus Tavily web research). Moments are rewritten for you while each choice keeps its trait math, three AI coworkers react in parallel, and you can answer in your own words with "Something else..." (scored by the LLM; crisis text routes to 988). A Bayesian selector picks each next moment to learn the most about you.
- **End-of-day report**: career fit from a trained MLP, local pay with a source tooltip, GNN **Picked for you** courses and jobs with one-line reasons, and **Live in your area**: a Tavily research agent runs 3 parallel searches, ranks sources and streams a cited summary that drops unsupported numbers.
- **Plan the route**: type your limits in plain English ("no classes before 9am, weekends off"), confirm the rules Foothold read, and a CP-SAT constraint solver plans each route (certificate, apprenticeship, transfer) in milliseconds, showing "Programs near <your place>". If you reject a plan, your reason becomes a new rule; approve it and it lands on your Track board.
- **Get the foothold**: employers post jobs (prompt-injection attempts are flagged), browse blind, skills-only cards with a distance filter, and see fairness and skill-gap insights. To reach someone, they send a consent request, and only that learner can accept it.
- **Support**: peer support circles, a coach for workplace conflict and EQ practice, and crisis routing straight to the 988 Lifeline.
- **Honesty built in**: every wage, cost and duration is labelled REAL, SAMPLE, SYNTHETIC or FICTIONAL, and LLM-written numbers are checked against the data before you see them.

## How we built it

- **Web**: Next.js 16, React, TypeScript, Tailwind, shadcn/ui, Motion, Cult UI, Watermelon UI and Skiper UI. It ships as a static export on Netlify, with per-tab sign-in sessions.
- **Agents**: Python, FastAPI and LangGraph. There are five graphs: sim, pathway, employer, coach and research (Tavily web search). They use parallel `Send` fan-out, SQLite checkpoints, SSE streaming and three human-in-the-loop interrupts. The LLM is OpenAI `gpt-6-luna`, behind a cache and a deterministic mock, so the app also runs offline.
- **ML**: PyTorch (an MLP for career fit), PyTorch Geometric (a heterogeneous GNN recommender behind "Picked for you"), scikit-learn, OR-Tools CP-SAT (planner) and NetworkX.
- **Data**: O*NET 31.0 (CC BY 4.0), CA EDD OEWS 2026 Q1 wages and projections, college fee pages and verified course listings. The training and evaluation sets are synthetic, and all people are fictional.
- **Infra**: Netlify (https://foothold-valley.netlify.app, runtime API discovery), Supabase Postgres (data mirror plus the public API-URL config), a Cloudflare / localhost.run tunnel to the laptop API, and Git.

**Results** (all on synthetic data, from `ml/artifacts/metrics.json`):

| Model | Ours | Baseline |
|---|---|---|
| Career fit (42 occupations, n = 8,400) | MLP top-1 0.7133 / top-3 0.9196 | cosine 0.7033 / 0.9038 |
| Adaptive selector (events to a confident match) | 12.755 | Thompson 13.366, random 16.851, fixed 17.133 |
| Recommender, cold start, NDCG@10 | GNN 0.2669 | MF 0.1635, popularity 0.1809 |
| Recommender, warm, recall@10 | GNN 0.3814 | **MF 0.4034 (MF wins)** |
| Recommender, courses, NDCG@10 (warm / cold) | GNN 0.1342 / 0.105 | **MF 0.1686 / 0.1212 (baselines win)** |
| Planner, months saved when both feasible (n = 250) | CP-SAT 0.832 mean, strictly better 10.4% | greedy (same feasibility, 0.4808) |
| Planner solve time | p50 15 ms, p95 189.6 ms | |
| Claim verifier (741 synthetic adversarial cases) | catch rate 1.0, false positives 0.0 | |
| Fairness, four-fifths rule | pooled 0.8804; **1 of 8 postings pass** | skill match only: 0 of 8 |

Tests: pytest 231 passed; golden-path end-to-end check (`scripts/e2e_golden.py`) 25/25.

## Challenges we ran into

- **The network filter**: the network we built on blocks github.com, registry.npmjs.org and Cloudflare's quick-tunnel API. We installed npm packages through the Yarn registry mirror, added an ssh tunnel fallback, and stored the API's public URL in Supabase so the static site can find it.
- **Usage limits**: we worked with limited model usage, so we cached LLM responses, made every LLM call fall back to a deterministic mock, and added a demo mode that runs the golden path with no live LLM calls.
- **Netlify can't run our agents**: PyTorch, OR-Tools and LangGraph don't fit in a static host, so the API runs on a laptop behind a tunnel. That's fine for a demo, not for production.
- **Honest metrics**: our GNN loses to matrix factorisation and popularity on course recommendations, and our fairness audit fails per posting. We decided to show both instead of tuning until they looked good.
- **Multi-account demo**: we wanted judges to see consent happen between two real accounts, so we built per-tab sessions (tokens in sessionStorage) and live polling between tabs.

## Accomplishments we're proud of

- A full loop from trying a job to an approved plan to a consented employer connection, across two accounts in two tabs.
- Any career, not just 8: live-generated workdays from O*NET plus web research, and a research agent that cites sources and drops numbers it can't support.
- Every number on screen has a provenance label and a source. Every model has a baseline, and we show where the baseline wins.
- Humans stay in charge at every decision: confirm the rules, approve the plan, pick who to contact, accept or decline.
- Crisis safety that doesn't depend on the LLM.

## What we learned

- Use the LLM for language and a solver for constraints. Most of the value came from that split.
- Simple baselines are strong. Cosine similarity came within about one point of our MLP, and MF beat the GNN on courses.
- With small groups, fairness metrics are noisy. A per-posting four-fifths check on a top-15 shortlist swings with one or two candidates.
- Being honest about provenance takes ongoing work: research, labels, verify links and a verifier that checks the LLM.

## What's next

- **A hosted API**, so the demo doesn't depend on a laptop and a tunnel.
- **Real learner data, with consent**: pilot with a Central Valley high school or community college, re-measure every model on real (consented) outcomes, and fix the fairness gap with larger pools and mitigation.
- **A counselor view**: let school counselors see (with permission) their students' sim profiles and plans, alongside the colleges' official Program Pathways Mapper.
- Human review of the LLM-drafted sim events, Spanish language support, and verified schedules for every SAMPLE program.
