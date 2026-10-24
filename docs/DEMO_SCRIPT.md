# Foothold demo script (5:00, with a 4:30 backup)

You present with **two browser tabs**. Sessions are per tab (`sessionStorage`), so each tab stays signed into its own fictional account.

| Tab | Account | Email / password | Leave it on |
|---|---|---|---|
| 1 | Luis Navarro (learner) | luis.navarro@example.com / valley-luis-03 | Workday (`/sim`) |
| 2 | Tri-Valley Freight (employer) | hiring@trivalleyfreight.example.org / valley-freight-04 | Employers (`/employers`) |

Spare learner accounts if you need them: Maya maya.ortiz@example.com / valley-maya-01, Dev dev.sandhu@example.com / valley-dev-02. Every person and employer is fictional.

## Network note

This Wi-Fi blocks `*.netlify.app`. Present from **http://localhost:3000**, or put the laptop on a phone hotspot to use https://foothold-valley.netlify.app (it finds the API at runtime).

## Pre-demo checklist (10 min before)

1. **Both servers up**: `scripts/dev.sh` (API on :8000, web on :3000). Check http://127.0.0.1:8000/health shows `ok: true` and note the `llm` mode. `TAVILY_API_KEY` must be set for "Live in your area" and Search any career.
2. **Warm up**: `python scripts/e2e_golden.py`. It should print 25/25 PASS. It warms the AI cache for the golden path and resets afterwards.
3. **Reset**: `python scripts/reset_demo.py` (the API can stay running). It clears consent requests, postings, boards, circle posts and checkpoints for the demo accounts, in SQLite and the Supabase mirror.
4. **Sign in each tab** at `/signin`: Tab 1 Luis, Tab 2 Tri-Valley Freight. Make sure Luis's place is **Stockton** (set it in onboarding if prompted) so Path shows "Programs near Stockton". Keep a third, signed-out tab on the landing page `/` for the opening.
5. Zoom 110-125%, notifications off, do one quick test of Search any career so its research is cached.

## The 5:00 run

| Time | Tab | Click | Say |
|---|---|---|---|
| 0:00 | Landing (signed out) | Let the wordmark spread, then scroll through the stages. | "In the San Joaquin Valley, at current rates only 26% of ninth graders are on a path to a bachelor's degree, vs 35% in the rest of California (PPIC, 2024). The jobs and colleges are here; the map isn't. Foothold: try the job, prove the skill, get the foothold." (15 s) |
| 0:15 | **Tab 1 · Luis** Workday | Pick **Diesel Mechanic**. Play one moment. Answer with **Something else...** and type a short answer of your own. | "Luis plays a real workday. The moments are rewritten for him, but every choice keeps its trait math, so the Bayesian selector still picks the moment that teaches us the most. He doesn't have to pick A, B or C: he can write his own answer and the AI scores it." |
| 0:55 | Tab 1 | Open **Behind the scenes**. | "These are three AI coworkers, separate LangGraph agents reacting in parallel. You can see the nodes fire." |
| 1:20 | Tab 1 | Finish the day. On the report, show career fit and pay (hover the source tooltip), then **Picked for you**, then **Live in your area** as it streams. | "Career fit comes from a trained model, and the pay is real CA EDD data with its source. Picked for you is our graph neural network, with a one-line reason for each pick. Live in your area is a Tavily research agent: three searches in parallel, sources ranked, and a cited summary that drops any number the sources don't back up." |
| 2:20 | Tab 1 | Go to **Path**. Show "Programs near Stockton", the CP-SAT vs greedy routes and the plain-English rules. | "Path plans a real route near Stockton. He types his limits in plain English, confirms the rules, and a CP-SAT solver, not an LLM, plans every route, with a greedy baseline beside it." |
| 3:05 | **Tab 2 · Tri-Valley Freight** Employers | **Post a job** → **Fill a sample posting** → post. **Talent** → blind cards → **Request** Luis. | "Tri-Valley Freight posts a job. The agent pulls out the skills and flags prompt-injection attempts. Talent shows blind, skills-only cards with no names. To reach anyone, they have to ask." |
| 3:45 | **Tab 1 · Luis** Inbox | Wait about 4 s for the request → **Accept and share**. | "Luis decides, in his own account." |
| 4:00 | **Tab 2** | Back to the employer tab: the card unlocks. | "Only after he says yes does this one employer see who he is." |
| 4:10 | Tab 1 (optional) | Workday → **Search any career** → "dental hygienist". | "And it isn't limited to 8 careers. Any O*NET occupation: this workday is generated live from O*NET work styles plus web research." |
| 4:40 | Any | Close. | "Every number is labelled real, sample, synthetic or fictional, and our metrics, including where a baseline beats us, are in the Lab. Foothold: try the job, prove the skill, get the foothold. Thank you." |

## The 4:30 backup

Skip the optional Search any career beat and shorten Path:

| Time | Tab | Beat |
|---|---|---|
| 0:00 | Landing | Wordmark + scroll stages, problem + tagline (15 s) |
| 0:15 | Tab 1 Luis | One diesel moment, **Something else...**, Behind the scenes (1:00) |
| 1:15 | Tab 1 | Report: Picked for you + Live in your area streaming (1:00) |
| 2:15 | Tab 1 | Path near Stockton: CP-SAT vs greedy (40 s) |
| 2:55 | Tab 2 Tri-Valley | Fill a sample posting → Talent → request Luis (40 s) |
| 3:35 | Tab 1 → Tab 2 | Inbox → Accept and share → card unlocks (30 s) |
| 4:05 | Any | Close (25 s) |

## If something breaks

- **An LLM or Tavily call is slow**: rerun `python scripts/e2e_golden.py` before the demo so the path is cached. As a fallback set `DEMO_MODE=1` (cached only) or `LLM_MODE=mock` in `.env` and restart the API yourself (it reloads on `.py` changes, not `.env`). A restart drops open streams, so start that step again.
- **Live in your area is empty**: check `TAVILY_API_KEY` and the network; say "it's live web research" and move on.
- **The request isn't in Luis's inbox**: wait one poll (about 4 s), then reload Inbox. Check Tab 2 requested *Luis*.
- **Old requests or postings show up**: `python scripts/reset_demo.py`, then reload both tabs.
- **The Netlify site can't reach the API**: present from localhost:3000 (this Wi-Fi blocks `*.netlify.app` anyway).
- **Anything else**: switch to the recordings below.

## Screen-record these as a backup (after a clean reset)

1. Tab 1: one diesel moment with Something else..., Behind the scenes, through the report with Live in your area streaming (about 75 s).
2. Tab 1: Path near Stockton (about 30 s).
3. Tab 2 → Tab 1 → Tab 2 in **one continuous take**: Fill a sample posting, Talent, request Luis, Inbox accept, card unlocks (about 45 s).
4. Tab 1: Search any career → dental hygienist workday (about 30 s).
