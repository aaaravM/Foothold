"""Clear demo activity for the four FICTIONAL demo accounts (local CLI; no HTTP endpoint on purpose).

    python scripts/reset_demo.py            # clear and print what was removed
    python scripts/reset_demo.py --dry-run  # only count

Removes, for maya / dev / luis / tri_valley_freight:
  * consent_requests (sent by the employer or addressed to the learners' talent cards)
  * postings (the employer's), progress_log, kanban
  * circle posts written by these accounts (circle_feed; plus legacy circle_posts rows by handle)
  * LangGraph checkpoints (sim / path / employer / coach threads) owned by these accounts
and mirrors the same deletions to Supabase when SUPABASE_URL + SUPABASE_SECRET_KEY are configured.
Keeps accounts, password hashes, seeds (circle seed posts live in data files), skill_demand aggregates,
the talent pool and every data file. Works with the API up or down (sqlite WAL, 30 s busy timeout).
In-process state of a running API (opt-in coach session memory) is not touched; it expires on restart.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

from foothold import auth, config, db  # noqa: E402

LEARNERS = ("maya", "dev", "luis")
EMPLOYER = "tri_valley_freight"
PERSONAS = (*LEARNERS, EMPLOYER)
OWNER_KEYS = ("learner_id", "employer_id", "account_id", "persona_id")


def _ids() -> dict[str, list[str]]:
    accounts = [f"acct_{p}" for p in PERSONAS]
    cards: list[str] = []
    handles: list[str] = []
    for p in LEARNERS:
        card = auth.candidate_for_persona(p)
        cid = auth.card_id(card) if card else None
        cards.append(cid or f"cand_{p}")
    for ident in auth.DEMO_IDENTITIES:
        if ident.kind == "learner":
            parts = ident.display_name.split()
            handles.append(parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][0]}.")
    return {"personas": list(PERSONAS), "accounts": accounts, "cards": sorted(set(cards)), "handles": handles,
            "owners": sorted(set(PERSONAS) | set(accounts))}


def _ph(values: list[str]) -> str:
    return ",".join("?" for _ in values)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


# (table, where-sql builder, remote column spec) -- remote: list of (column, id-set name)
LOCAL_RULES: list[tuple[str, str, list[str]]] = [
    ("consent_requests", "employer_id IN ({o}) OR candidate_id IN ({c})", ["owners", "cards"]),
    ("postings", "employer_id IN ({o})", ["owners"]),
    ("progress_log", "learner_id IN ({o})", ["owners"]),
    ("kanban", "learner_id IN ({o})", ["owners"]),
    ("circle_posts", "handle IN ({h})", ["handles"]),
    ("circle_feed", "author_id IN ({o})", ["owners"]),
]
REMOTE_RULES: list[tuple[str, str, str]] = [
    ("consent_requests", "employer_id", "owners"),
    ("consent_requests", "candidate_id", "cards"),
    ("postings", "employer_id", "owners"),
    ("progress_log", "learner_id", "owners"),
    ("kanban", "learner_id", "owners"),
    ("circle_posts", "handle", "handles"),
]


def clear_local(ids: dict[str, list[str]], dry_run: bool) -> dict[str, int]:
    out: dict[str, int] = {}
    db.init_db()
    with sqlite3.connect(str(config.db_path()), timeout=30) as conn:
        for table, where, sets in LOCAL_RULES:
            if not _table_exists(conn, table):
                continue
            params: list[str] = []
            fmt: dict[str, str] = {}
            for name, key in (("owners", "o"), ("cards", "c"), ("handles", "h")):
                if name in sets:
                    fmt[key] = _ph(ids[name])
            # params must follow placeholder order in the WHERE clause
            for name in sets:
                params.extend(ids[name])
            sql_where = where.format(**fmt)
            n = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {sql_where}", params).fetchone()[0]
            if n and not dry_run:
                conn.execute(f"DELETE FROM {table} WHERE {sql_where}", params)
            out[table] = int(n)
        conn.commit()
    return out


def clear_checkpoints(ids: dict[str, list[str]], dry_run: bool) -> dict[str, int]:
    path = config.checkpoint_db_path()
    counts: dict[str, int] = {}
    if not path.exists():
        return counts
    from foothold.checkpoint import make_checkpointer

    saver = make_checkpointer(path)
    owners = set(ids["owners"])
    try:
        with saver.lock:
            tids = [r[0] for r in saver.conn.execute("SELECT DISTINCT thread_id FROM checkpoints").fetchall()]
        for tid in tids:
            try:
                tup = saver.get_tuple({"configurable": {"thread_id": tid}})
            except Exception:  # noqa: BLE001 - unreadable checkpoint: leave it alone
                continue
            values: dict[str, Any] = ((tup.checkpoint or {}).get("channel_values") or {}) if tup else {}
            if not any(isinstance(values.get(k), str) and values.get(k) in owners for k in OWNER_KEYS):
                continue
            kind = tid.split("_", 1)[0] if "_" in tid else "other"
            counts[kind] = counts.get(kind, 0) + 1
            if not dry_run:
                saver.delete_thread(tid)
    finally:
        try:
            saver.conn.close()
        except Exception:  # noqa: BLE001
            pass
    return counts


def _api_mirror_count(api: str) -> int | None:
    """The running API's Supabase mirror write count (from /health), or None when it is down / not mirroring."""
    try:
        import httpx

        st = httpx.get(f"{api}/health", timeout=2.0).json().get("db") or {}
        return int(st.get("mirrored", 0)) if st.get("backend") == "supabase" else None
    except Exception:  # noqa: BLE001
        return None


def wait_for_mirror(api: str = "http://127.0.0.1:8000", quiet_s: float = 1.5, max_s: float = 12.0) -> None:
    """Let a running API finish queued Supabase mirror writes (count unchanged for ``quiet_s``)."""
    t_end = time.monotonic() + max_s
    last = _api_mirror_count(api)
    if last is None:
        return
    stable_since = time.monotonic()
    while time.monotonic() < t_end:
        time.sleep(0.5)
        cur = _api_mirror_count(api)
        if cur != last:
            last, stable_since = cur, time.monotonic()
        elif time.monotonic() - stable_since >= quiet_s:
            return


def clear_remote(ids: dict[str, list[str]], dry_run: bool) -> dict[str, Any]:
    out = _clear_remote_once(ids, dry_run)
    if out.get("status") in ("ok", "partial"):
        # A running API mirrors writes asynchronously; a late write could re-create a row after the first
        # pass (and the next API start would sync it back), so wait for the mirror to go quiet and repeat.
        wait_for_mirror()
        again = _clear_remote_once(ids, dry_run)
        for k, v in again.items():
            if k != "status" and isinstance(v, int) and isinstance(out.get(k), int):
                out[k] += v
    return out


def _clear_remote_once(ids: dict[str, list[str]], dry_run: bool) -> dict[str, Any]:
    client = db.remote_client()
    if client is None:
        return {"status": "skipped (Supabase not configured)"}
    if dry_run:
        client.close()
        return {"status": "skipped (dry run)"}
    out: dict[str, Any] = {"status": "ok"}
    try:
        for table, column, name in REMOTE_RULES:
            try:
                rows = client.delete_in(table, column, ids[name])
                out[table] = out.get(table, 0) + len(rows)
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)[:40] if isinstance(exc, RuntimeError) else type(exc).__name__
                if "404" in msg:
                    msg += " (table missing: run supabase/schema.sql)"
                out[table] = f"failed: {msg}"
                out["status"] = "partial"
    finally:
        client.close()
    return out


def reset(dry_run: bool = False, *, quiet: bool = False) -> dict[str, Any]:
    ids = _ids()
    if not dry_run:
        wait_for_mirror()  # let queued mirror writes land before deleting them remotely
    result = {
        "local": clear_local(ids, dry_run),
        "checkpoints": clear_checkpoints(ids, dry_run),
        "supabase": clear_remote(ids, dry_run),
        "dry_run": dry_run,
    }
    if not quiet:
        verb = "would clear" if dry_run else "cleared"
        print(f"Demo reset ({verb}) for: {', '.join(PERSONAS)}")
        for table, n in result["local"].items():
            print(f"  sqlite  {table:<17} {n}")
        ck = result["checkpoints"]
        print(f"  checkpoints        {sum(ck.values())}" + (f"  ({', '.join(f'{k}: {v}' for k, v in sorted(ck.items()))})" if ck else ""))
        sb = result["supabase"]
        print(f"  supabase           {sb.get('status')}")
        for k, v in sb.items():
            if k != "status":
                print(f"    {k:<17} {v}")
        print("Kept: accounts, seeds, talent pool, skill_demand, data files.")
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="count only, delete nothing")
    args = ap.parse_args(argv)
    reset(args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
