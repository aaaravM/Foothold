# Foothold demo script (5:00, with a 4:30 backup)

You present by **switching browser tabs**. Each tab is signed into a different fictional account, and sessions are per tab (`sessionStorage`), so the tabs don't interfere with each other.

## Before you go on (10 min before)

1. Check the API: open http://127.0.0.1:8000/health. It should show `ok: true`. Note the `llm` mode. `DEMO_MODE=1` in `.env` serves cached LLM responses for the golden path.
2. Check the web: open http://localhost:3000, or the Netlify URL if you present the deployed site.
3. Open the presenter page `/demo` (unlinked) in a separate window. It shows the run of show and the tab list.
4. Open four tabs, in this order, and sign each one in at `/signin`:

| Tab | Account | Email / password | Leave it on |
|---|---|---|---|
| 1 | Luis Navarro (learner) | luis.navarro@example.com / valley-luis-03 | `/sim` |
| 2 | Tri-Valley Freight (employer) | hiring@trivalleyfreight.example.org / valley-freight-04 | `/employers` |
| 3 | Maya Ortiz (learner) | maya.ortiz@example.com / valley-maya-01 | `/path` |
| 4 | Dev Sandhu (learner) | dev.sandhu@example.com / valley-dev-02 | `/circle` |

5. Keep one more tab on the landing page `/` while signed out, as your opening shot.
6. Set browser zoom to 110-125% so the back row can read the screen. Turn notifications off.

## Reset between rehearsals

Runtime state (accounts db, LangGraph checkpoints, consent requests in SQLite) lives in `api/.runtime`. On Windows, the files are locked while the API runs, so:

```bash
# 1. stop the API (Ctrl+C in its terminal / stop the watchfiles supervisor)
scripts/reset.sh          # deletes api/.runtime and re-seeds
# 2. start the API again (scripts/run_api.sh or scripts/dev.sh)
```

Then sign out of every tab, or close the tabs, and sign in again. Old tokens stay valid only if `AUTH_SECRET` hasn't changed, but the accounts are re-seeded. **If Supabase is the active backend** (`/health` shows `"db":{"backend":"supabase"}`), consent requests and postings are mirrored there too. Clear `consent_requests` and `postings` in the Supabase table editor if old requests show up in Luis's inbox.

## The 5:00 run

| Time | Tab | Click | Say |
|---|---|---|---|
| 0:00 | Landing (signed out) | Nothing yet. | "In the San Joaquin Valley, at current rates only 26% of ninth graders are on a path to a bachelor's degree, compared with 35% in the rest of California (PPIC, 2024). The jobs and the colleges are here, but there's no map between them. Foothold is that map: try the job, prove the skill, get the foothold." |
| 0:25 | **Tab 1 · Luis** `/sim` | **Choose a career** → Diesel Mechanic (or **Let Foothold choose**). Answer two moments with keys **1 / 2 / 3**. Open **Behind the scenes**. | "Luis plays a real workday. Every choice is evidence for the 21 O*NET work styles. The next moment is picked by a Bayesian selector to learn the most about him. These three coworkers are separate AI agents reacting in parallel. You can see the LangGraph nodes fire live." |
| 1:20 | Tab 1 | Keep answering until the day ends (a **Crunch** event may appear). Show the report. | "This is his 21-trait profile and his top careers from our trained model. The wage is a REAL CA EDD figure, and every number has a source badge. Anything the LLM writes gets fact-checked against the data before he sees it." Click **Plan a route to this career**. |
| 2:00 | **Tab 3 · Maya** `/path` | Constraints are prefilled (10 h/week, $4,000, bus). Type *"no classes before 9am, weekends off"* → turn it into rules → **Confirm the rules Foothold read** → apply. | "Maya works and takes the bus. She types her limits in plain English. The AI turns them into rules, but she confirms them first, because a human stays in the loop. Then a CP-SAT constraint solver, not an LLM, plans every route in milliseconds. Here's CP-SAT next to a greedy baseline." |
| 2:45 | Tab 3 | Propose the plan → reject it with *"too long"* → it re-solves → **Approve this plan**. | "She says no, too long. Her reason becomes a new rule and it re-solves. When she approves, the steps land on her board." |
| 3:20 | **Tab 2 · Tri-Valley Freight** `/employers` | **Post a job** → **Fill a sample posting** → **Post job**. Show the generated skills profile, the blind cards and the four-fifths fairness check. Under **Pick who to contact**, tick Luis's card → **Send request**. | "Now the employer side. Tri-Valley Freight is fictional. They paste a posting, and the agent pulls out the skills and searches the talent pool. They only see blind cards with skills and sim results, never a name. It even audits the shortlist with the four-fifths rule. To reach anyone, they have to ask." |
| 4:00 | **Tab 1 · Luis** `/inbox` | Wait about 4 s for the request to appear (no reload) → **Accept and share**. | "Luis gets the request in his own account. He decides." |
| 4:15 | **Tab 2** | Go back to the employer tab and show the card unlocking. | "Only after he accepts does this one employer see who he is. That's consent." |
| 4:25 | **Tab 4 · Dev** `/circle` | Show a support circle, then send one coach message. | "Learners also get peer support circles and a coach for workplace conflict and EQ practice. If someone types crisis language, it skips the AI and shows the 988 Lifeline." |
| 4:45 | Any tab → `/lab` | Scroll the metrics table. | "Every model is here with its real numbers, measured on synthetic data, including where a simple baseline beats us. Foothold: try the job, prove the skill, get the foothold. Thank you." |

## The 4:30 backup (if you're short on time or something is slow)

Cut the Path rejection loop (2:45-3:20) and the Circle beat:

| Time | Tab | Beat |
|---|---|---|
| 0:00 | Landing | Problem + tagline (25 s) |
| 0:25 | Tab 1 Luis | Sim: two moments + Behind the scenes, then the report (1:20) |
| 1:45 | Tab 3 Maya | Path: type the constraint, confirm it, routes re-solve, **Approve this plan** (55 s) |
| 2:40 | Tab 2 Tri-Valley | **Fill a sample posting** → blind cards → fairness → **Send request** to Luis (50 s) |
| 3:30 | Tab 1 Luis | `/inbox` → **Accept and share**; Tab 2 card unlocks (35 s) |
| 4:05 | `/lab` | Results and the honest baseline line, then thank you (25 s) |

## If something breaks

- **An LLM call is slow or failing**: set `DEMO_MODE=1` (cached) or `LLM_MODE=mock` in `.env`. The supervisor restarts the API when a `.py` file changes, not `.env`, so restart the API yourself. A restart drops open SSE streams, so start that step again.
- **The request isn't in Luis's inbox**: wait one poll (about 4 s), then reload `/inbox`. Make sure Tab 2 picked *Luis's* card.
- **The deployed site says the API is offline**: the tunnel URL changed. Use localhost, or update `public_config.api_url` / rebuild (see docs/DEPLOY.md).
- **Anything else**: switch to the screen recordings below.

## Screen-record these as a backup (do it after a clean reset)

1. Tab 1: the Sim from career choice to the report, with Behind the scenes open (about 60 s).
2. Tab 3: Path, from the typed constraint through confirm rules, re-solve, reject "too long", re-solve and approve (about 45 s).
3. Tab 2 → Tab 1 → Tab 2: Fill a sample posting, Send request, the inbox shows it live, Accept and share, the card unlocks. Record this as **one continuous take** of the window switching (about 45 s). It's the moment you most need to have on video.
4. Tab 4: the Circle coach, plus one crisis-phrase message showing the 988 response (about 20 s).
5. `/lab` scrolling the metrics (about 15 s).
