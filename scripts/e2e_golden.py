"""Golden-path end-to-end check against the running API (default http://127.0.0.1:8000).

    python scripts/e2e_golden.py                 # run, print a PASS/FAIL table, then reset demo data
    python scripts/e2e_golden.py --keep          # keep the demo data it created (no reset)
    python scripts/e2e_golden.py --api http://127.0.0.1:8000

Uses the four FICTIONAL demo accounts (credentials from api/foothold/auth.py). Calls the real API, so
LLM-backed steps use whatever LLM mode the API runs in (cached responses are reused by the API).
Exit code 0 when every step passes.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

from foothold import auth  # noqa: E402

SSE_TIMEOUT = httpx.Timeout(180.0, connect=10.0)
METRIC_KEYS = ("verifier", "career_fit", "planner", "recommender", "selector", "fairness")
REPORT_FIELDS = ("top_careers", "model", "traits", "careers", "probability_basis", "selector_posterior", "verification")


class StepFail(AssertionError):
    pass


def check(cond: Any, msg: str) -> None:
    if not cond:
        raise StepFail(msg)


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.http = httpx.Client(base_url=self.base, timeout=SSE_TIMEOUT)
        self.tokens: dict[str, str] = {}

    def h(self, who: str | None) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[who]}"} if who else {}

    def get(self, path: str, who: str | None = None, **kw: Any) -> httpx.Response:
        return self.http.get(path, headers=self.h(who), **kw)

    def post(self, path: str, who: str | None = None, **kw: Any) -> httpx.Response:
        return self.http.post(path, headers=self.h(who), **kw)

    def ok(self, r: httpx.Response, what: str) -> Any:
        check(r.status_code < 300, f"{what}: HTTP {r.status_code} {r.text[:160]}")
        return r.json()

    def sse(self, path: str, who: str, body: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        with self.http.stream("POST", path, headers={**self.h(who), "Accept": "text/event-stream"}, json=body or {}) as r:
            if r.status_code >= 300:
                r.read()
                raise StepFail(f"{path}: HTTP {r.status_code} {r.text[:160]}")
            data_lines: list[str] = []
            for line in r.iter_lines():
                if line.startswith("data:"):
                    data_lines.append(line[5:].strip())
                elif line == "" and data_lines:
                    try:
                        events.append(json.loads("\n".join(data_lines)))
                    except json.JSONDecodeError:
                        pass
                    data_lines = []
            if data_lines:
                try:
                    events.append(json.loads("\n".join(data_lines)))
                except json.JSONDecodeError:
                    pass
        errs = [e for e in events if e.get("type") == "error"]
        check(not errs, f"{path}: SSE error {errs[0].get('message') if errs else ''}")
        return events


def last(events: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
    for e in reversed(events):
        if e.get("type") == kind:
            return e
    return None


def thread_of(events: list[dict[str, Any]]) -> str:
    meta = next((e for e in events if e.get("type") == "meta"), None)
    check(meta and meta.get("thread_id"), "no meta.thread_id in SSE")
    return meta["thread_id"]


# ---------------------------------------------------------------------------
# steps
# ---------------------------------------------------------------------------

CTX: dict[str, Any] = {}


def s_login(api: Api) -> str:
    for ident in auth.DEMO_IDENTITIES:
        out = api.ok(api.post("/api/auth/login", json={"email": ident.email, "password": ident.password}), f"login {ident.persona_id}")
        check(out.get("token"), f"no token for {ident.persona_id}")
        api.tokens[ident.persona_id] = out["token"]
    return "4 accounts"


def _play_sim(api: Api, who: str, career_id: str | None, choices: int | None) -> tuple[str, list[dict[str, Any]], int]:
    ev = api.sse("/api/sim/start", who, {"career_id": career_id})
    tid = thread_of(ev)
    made = 0
    while True:
        intr = last(ev, "interrupt")
        done = last(ev, "done")
        if done or not intr:
            break
        if choices is not None and made >= choices:
            break
        payload = intr.get("payload") or {}
        opts = (payload.get("event") or {}).get("choices") or []
        check(opts, "sim interrupt without choices")
        ev = api.sse(f"/api/sim/{tid}/choose", who, {"choice_id": opts[made % len(opts)]["choice_id"]})
        made += 1
        check(made <= 12, "sim did not finish within 12 choices")
    return tid, ev, made


def s_luis_sim(api: Api) -> str:
    tid, ev, made = _play_sim(api, "luis", "diesel_mechanic", None)
    done = last(ev, "done")
    check(done, f"no report after {made} choices")
    rep = (done.get("result") or {}).get("report") or {}
    missing = [f for f in REPORT_FIELDS if f not in rep]
    check(not missing, f"report missing {missing}")
    top = rep["top_careers"]
    check(top and all("probability" in t and "probability_basis" in t and "p_overall" in t for t in top), "top_careers lacks basis fields")
    if rep["model"].get("name") == "mlp":
        check(all(isinstance(t["p_overall"], (int, float)) for t in top), "mlp report without p_overall")
        check("8 Foothold careers" in rep["probability_basis"], "probability_basis label")
    check(rep["selector_posterior"] is None or rep["selector_posterior"].get("top"), "selector_posterior shape")
    t0 = top[0]
    return (f"{made} choices; top1 {t0['career_id']} share={t0['probability']} p_overall={t0['p_overall']}; "
            f"model={rep['model'].get('name')}")


def s_luis_path(api: Api) -> str:
    sol = api.ok(api.post("/api/path/solve", "luis", json={"career_id": "diesel_mechanic", "hours_per_week": 10}), "path solve")
    check(isinstance(sol, dict) and sol, "empty solve")
    ev = api.sse("/api/path/start", "luis", {"career_id": "diesel_mechanic", "hours_per_week": 10})
    tid = thread_of(ev)
    rounds = 0
    while last(ev, "interrupt") and not last(ev, "done"):
        ev = api.sse(f"/api/path/{tid}/decision", "luis", {"approve": True})
        rounds += 1
        check(rounds <= 5, "pathway did not finish after 5 approvals")
    done = last(ev, "done")
    check(done, "pathway: no done event")
    res = done.get("result") or {}
    return f"solve keys={len(sol)}; approvals={rounds}; approved={res.get('approved')}"


def s_employer_post(api: Api) -> str:
    text = ("Tri-Valley Freight (fictional) is hiring an entry-level diesel mechanic / technician in Manteca. "
            "Required: air brakes, hydraulics, troubleshooting diesel engines, preventive maintenance and repairing "
            "trucks, OSHA safety. Preferred: MIG welding. Part-time 15 hours a week to start, weekday afternoons.")
    ev = api.sse("/api/employer/postings", "tri_valley_freight", {"title": "Diesel Technician (entry)", "text": text})
    intr = last(ev, "interrupt")
    check(intr and (intr.get("payload") or {}).get("kind") == "pick_candidates", "no pick_candidates interrupt")
    CTX["posting_id"] = intr["payload"].get("posting_id")
    CTX["emp_thread"] = thread_of(ev)
    check(CTX["posting_id"], "no posting_id")
    return f"posting {CTX['posting_id']}; shortlist {len(intr['payload'].get('shortlist_ids') or [])}"


def s_employer_talent(api: Api) -> str:
    out = api.ok(api.get("/api/employer/talent", "tri_valley_freight", params={"posting_id": CTX["posting_id"], "limit": 50}), "talent")
    inbox = api.ok(api.get("/api/employer/inbox", "luis"), "luis inbox")
    luis_pid = inbox.get("candidate_id")
    check(luis_pid, "luis has no candidate id")
    CTX["luis_pid"] = luis_pid
    ids = [c["candidate_id"] for c in out["cards"]]
    check(luis_pid in ids, "luis not in ranked talent")
    rank = ids.index(luis_pid) + 1
    rec = out.get("recommender") or {}
    check(rec.get("used"), f"recommender not used: {rec.get('note')}")
    CTX["luis_rank"] = rank
    return f"luis rank {rank}/{out['eligible']} (pool {out['pool_size']}); recommender: {rec.get('note')}"


def s_employer_request(api: Api) -> str:
    r = api.post("/api/employer/consent-requests", "tri_valley_freight",
                 json={"candidate_id": CTX["luis_pid"], "posting_id": CTX["posting_id"],
                       "message": "Hi! Your diesel sim results stood out. Open to a chat? (demo)"})
    out = api.ok(r, "consent request")
    CTX["request"] = out
    return f"request status={out.get('status') or (out.get('request') or {}).get('status')}"


def s_luis_accept(api: Api) -> str:
    inbox = api.ok(api.get("/api/employer/inbox", "luis"), "luis inbox")
    reqs = [q for q in inbox["requests"] if q["status"] == "pending" and q.get("posting_id") == CTX["posting_id"]]
    check(reqs, "luis inbox has no pending request for the posting")
    CTX["req_id"] = reqs[0]["id"]
    out = api.ok(api.post(f"/api/employer/consent/{CTX['req_id']}", "luis", json={"decision": "accept"}), "accept")
    return f"accepted {CTX['req_id']} -> {out.get('status') or (out.get('request') or {}).get('status')}"


def s_employer_contact(api: Api) -> str:
    out = api.ok(api.get(f"/api/employer/candidates/{CTX['luis_pid']}", "tri_valley_freight"), "candidate")
    check(out.get("consented"), "not consented")
    rev = out.get("revealed") or {}
    email = (rev.get("contact") or {}).get("email")
    check(rev.get("name") and email, "contact not revealed")
    return f"revealed {rev.get('name')} <{email}> (fictional)"


def s_maya_isolation(api: Api) -> str:
    inbox = api.ok(api.get("/api/employer/inbox", "maya"), "maya inbox")
    check(all(q["id"] != CTX["req_id"] for q in inbox.get("requests") or []), "maya sees luis's request")
    r = api.post(f"/api/employer/consent/{CTX['req_id']}", "maya", json={"decision": "decline"})
    check(r.status_code in (403, 404), f"maya could decide luis's request (HTTP {r.status_code})")
    r2 = api.get("/api/employer/inbox/luis", "maya")
    check(r2.status_code in (403, 404), f"maya read luis's inbox (HTTP {r2.status_code})")
    return f"inbox clean; decide -> {r.status_code}; inbox/luis -> {r2.status_code}"


def s_maya_adaptive(api: Api) -> str:
    tid, ev, made = _play_sim(api, "maya", None, 1)
    check(made == 1, "no choice made")
    check(last(ev, "interrupt") or last(ev, "done"), "no next event after choice")
    return f"adaptive thread {tid[:12]}..; 1 choice ok"


def s_dev_path(api: Api) -> str:
    sol = api.ok(api.post("/api/path/solve", "dev", json={"career_id": "robotics_tech", "hours_per_week": 45}), "dev solve")
    routes = sol.get("routes") or {}
    check(isinstance(routes, dict) and routes, "no routes")
    feas = [k for k, v in routes.items() if isinstance(v, dict) and v.get("feasible")]
    check(feas, "no feasible route at 45 h/week")
    over = [k for k in feas if (routes[k].get("peak_hours_per_week") or 0) > 45]
    check(not over, f"routes exceed 45 h/week: {over}")
    return f"feasible {len(feas)}/{len(routes)} ({', '.join(feas)}); {sol.get('request_ms')} ms"


def _coach(api: Api, who: str, text: str, mode: str = "listening", scenario: str | None = None) -> dict[str, Any]:
    ev = api.sse("/api/circle/coach", who, {"text": text, "mode": mode, "scenario_id": scenario})
    done = last(ev, "done")
    check(done, "coach: no done")
    return done.get("result") or {}


def s_coach_crisis(api: Api) -> str:
    res = _coach(api, "maya", "I can't do this anymore, I want to end my life.")
    check(res.get("crisis") is True, "crisis not detected")
    check("988" in json.dumps(res), "988 missing from crisis response")
    return "crisis -> 988 panel"


def s_coach_normal(api: Api) -> str:
    res = _coach(api, "dev", "I'm nervous about my first week at a new warehouse job. Any tips for asking questions?")
    check(res.get("crisis") is False and (res.get("reply") or "").strip(), "no coach reply")
    return f"reply {len(res['reply'])} chars"


def s_eq(api: Api) -> str:
    sc = api.ok(api.get("/api/circle/eq/scenarios", "luis"), "eq scenarios")
    items = sc.get("scenarios") or []
    check(items, "no EQ scenarios")
    out = api.ok(api.post("/api/circle/eq/feedback", "luis", json={
        "scenario_id": items[0]["id"],
        "response": "I hear that the schedule change was frustrating. Can we look at the shift list together and find a fix?",
    }), "eq feedback")
    keys = ("listening", "empathy", "assertiveness", "repair")
    flat = {**out, **(out.get("scores") or {}), **(out.get("rubric") or {} if isinstance(out.get("rubric"), dict) else {})}
    check(all(k in flat for k in keys), f"rubric keys missing: {list(out)[:8]}")
    return "rubric " + ", ".join(f"{k}={flat[k]}" for k in keys)


def s_graph(api: Api) -> str:
    parts = []
    for who in ("maya", "dev", "luis"):
        for model in ("gnn", "mf", "pop"):
            out = api.ok(api.get(f"/api/graph/recommend/{who}", who, params={"model": model}), f"graph {who} {model}")
            check(out.get("items"), f"no items for {who}/{model}")
            parts.append(f"{who}/{model}:{out.get('model_used')}")
    return f"9 calls ok ({parts[0]}, {parts[-1]})"


def s_metrics(api: Api) -> str:
    out = api.ok(api.get("/api/metrics"), "metrics")
    missing = [k for k in METRIC_KEYS if k not in out]
    check(not missing, f"metrics missing {missing}")
    return "6 keys"


# --- sign-up, profile and location (self-registered accounts; removed again at the end) ---------------

E2E_DOMAIN = "e2e-signup.example.com"


def s_register_learner(api: Api) -> str:
    email = f"learner.{int(time.time() * 1000)}@{E2E_DOMAIN}"
    CTX["new_learner_email"] = email
    r = api.post("/api/auth/register", json={"display_name": "Test Signup", "email": email, "password": "e2e-pass-123",
                                            "kind": "learner"})
    out = api.ok(r, "register learner")
    check(out.get("token") and out["account"]["kind"] == "learner", "register: no token/account")
    api.tokens["new_learner"] = out["token"]
    prof = api.ok(api.http.patch("/api/auth/me/profile", headers=api.h("new_learner"),
                                 json={"place_id": "modesto", "hours_per_week": 20}), "set place")
    check(prof.get("place_id") == "modesto" and (prof.get("place") or {}).get("name") == "Modesto", "place not saved")
    return f"{out['account']['persona_id']} @ Modesto"


def s_new_learner_path(api: Api) -> str:
    sol = api.ok(api.post("/api/path/solve", "new_learner", json={"career_id": "logistics_lead", "hours_per_week": 20}),
                 "path solve (profile place)")
    check((sol.get("origin") or {}).get("place_id") == "modesto", "solve did not use the saved place")
    commutes = {rt: r["commute"] for rt, r in sol["routes"].items() if r.get("commute")}
    check(commutes, "no per-campus commute in routes")
    rt, cm = next(iter(commutes.items()))
    return f"{len(commutes)} routes with commute; {rt}: {cm['campus']} {cm['minutes_one_way']} min"


def s_new_learner_sim(api: Api) -> str:
    ev = api.sse("/api/sim/start", "new_learner", {"career_id": "logistics_lead"})
    intr = last(ev, "interrupt")
    check(intr and ((intr.get("payload") or {}).get("event") or {}).get("choices"), "sim did not reach a choice")
    return f"thread {thread_of(ev)}"


def s_new_learner_opt_in(api: Api) -> str:
    api.ok(api.http.patch("/api/auth/me/profile", headers=api.h("new_learner"), json={"talent_opt_in": True}), "opt in")
    inbox = api.ok(api.get("/api/employer/inbox", "new_learner"), "new learner inbox")
    pid = inbox.get("candidate_id")
    check(pid and (inbox.get("card") or {}).get("region", {}).get("label") == "Modesto area", "no blind card after opt-in")
    view = api.ok(api.get(f"/api/employer/candidates/{pid}", "tri_valley_freight"), "employer views new card")
    check(not view.get("consented") and "Test Signup" not in json.dumps(view), "new card not blind")
    talent = api.ok(api.get("/api/employer/talent", "tri_valley_freight", params={"limit": 100, "region": "Modesto"}),
                    "talent (Modesto)")
    check(any(c["candidate_id"] == pid for c in talent["cards"]),
          "opted-in learner missing from talent search")
    return f"card {pid} in pool of {talent['pool_size']}"


def s_register_employer(api: Api) -> str:
    email = f"hiring.{int(time.time() * 1000)}@{E2E_DOMAIN}"
    out = api.ok(api.post("/api/auth/register", json={"display_name": "Valley Parts Hiring", "email": email,
                                                     "password": "e2e-pass-456", "kind": "employer",
                                                     "org_name": "Valley Parts", "place_id": "fresno"}), "register employer")
    api.tokens["new_employer"] = out["token"]
    text = ("Valley Parts is hiring a warehouse associate in Fresno. Required: forklift safety, inventory systems, "
            "shipping and receiving. Preferred: spreadsheets. 20 hours a week.")
    ev = api.sse("/api/employer/postings", "new_employer", {"title": "Warehouse Associate", "text": text})
    intr = last(ev, "interrupt")
    check(intr and (intr.get("payload") or {}).get("kind") == "pick_candidates", "new employer: no pick_candidates")
    near = api.ok(api.get("/api/employer/talent", "new_employer", params={"limit": 100, "max_km": 80}), "talent near")
    check((near.get("origin") or {}).get("place_id") == "fresno", "talent search ignored employer place")
    return f"org {out['account']['org']}; posting ok; {near['eligible']} within 80 km"


def s_duplicate_email(api: Api) -> str:
    r = api.post("/api/auth/register", json={"display_name": "Again", "email": CTX["new_learner_email"].upper(),
                                            "password": "e2e-pass-123", "kind": "learner"})
    check(r.status_code == 409, f"duplicate email gave HTTP {r.status_code}")
    return "409"


def cleanup_signups() -> int:
    """Remove the accounts (and opt-in cards) this run registered."""
    from foothold import db

    rows = db.query("SELECT id, persona_id FROM accounts WHERE email LIKE ?", (f"%@{E2E_DOMAIN}",))
    for r in rows:
        try:
            db.execute("DELETE FROM user_talent_cards WHERE account_id = ?", (r["id"],))
        except Exception:  # noqa: BLE001  (table may not exist yet)
            pass
        db.execute("DELETE FROM progress_log WHERE learner_id = ?", (r["persona_id"],))
        db.execute("DELETE FROM accounts WHERE id = ?", (r["id"],))
    return len(rows)


STEPS: list[tuple[str, Callable[[Api], str], tuple[str, ...]]] = [
    ("login x4", s_login, ()),
    ("luis sim diesel -> report", s_luis_sim, ("login x4",)),
    ("luis path solve + approve", s_luis_path, ("login x4",)),
    ("employer posting (SSE)", s_employer_post, ("login x4",)),
    ("employer talent ranking", s_employer_talent, ("employer posting (SSE)",)),
    ("employer consent request", s_employer_request, ("employer talent ranking",)),
    ("luis inbox -> accept", s_luis_accept, ("employer consent request",)),
    ("employer sees contact", s_employer_contact, ("luis inbox -> accept",)),
    ("maya cannot see request", s_maya_isolation, ("luis inbox -> accept",)),
    ("maya adaptive sim (1 choice)", s_maya_adaptive, ("login x4",)),
    ("dev path solve 45 h/wk", s_dev_path, ("login x4",)),
    ("coach crisis -> 988", s_coach_crisis, ("login x4",)),
    ("coach normal reply", s_coach_normal, ("login x4",)),
    ("EQ feedback rubric", s_eq, ("login x4",)),
    ("graph recommend 3x3", s_graph, ("login x4",)),
    ("metrics 6 keys", s_metrics, ()),
    ("signup learner + place", s_register_learner, ()),
    ("signup path uses place commute", s_new_learner_path, ("signup learner + place",)),
    ("signup sim start", s_new_learner_sim, ("signup learner + place",)),
    ("signup opt in -> talent pool", s_new_learner_opt_in, ("signup learner + place", "login x4")),
    ("signup employer -> posting", s_register_employer, ()),
    ("signup duplicate email 409", s_duplicate_email, ("signup learner + place",)),
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--keep", action="store_true", help="do not reset demo data at the end")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    api = Api(args.api)
    results: list[tuple[str, str, float, str]] = []
    status: dict[str, str] = {}
    t_all = time.perf_counter()
    for name, fn, deps in STEPS:
        if any(status.get(d) != "PASS" for d in deps):
            status[name] = "SKIP"
            results.append((name, "SKIP", 0.0, "dependency failed"))
            continue
        t0 = time.perf_counter()
        try:
            detail = fn(api)
            st = "PASS"
        except Exception as exc:  # noqa: BLE001
            st = "FAIL"
            detail = f"{type(exc).__name__}: {exc}"[:220]
            if args.verbose:
                traceback.print_exc()
        status[name] = st
        results.append((name, st, time.perf_counter() - t0, detail))
        print(f"  {st:<4} {name}", flush=True)
    total = time.perf_counter() - t_all

    w = max(len(r[0]) for r in results)
    print()
    print(f"{'step':<{w}}  {'result':<6} {'time':>7}  detail")
    print(f"{'-' * w}  {'-' * 6} {'-' * 7}  {'-' * 40}")
    for name, st, dt, detail in results:
        print(f"{name:<{w}}  {st:<6} {dt:>6.1f}s  {detail}")
    n_pass = sum(1 for r in results if r[1] == "PASS")
    print(f"\n{n_pass}/{len(results)} passed in {total:.1f}s")

    if not args.keep:
        import reset_demo

        try:
            print(f"removed {cleanup_signups()} sign-up test account(s)")
        except Exception as exc:  # noqa: BLE001
            print(f"sign-up cleanup skipped ({type(exc).__name__})")

        print()
        reset_demo.reset()
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
