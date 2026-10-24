"""Deploy the static web build (web/out) to Netlify through the Netlify REST API.

No netlify-cli needed (npm's public registry is blocked on some networks). Reads NETLIFY_AUTH_TOKEN
from the repo .env, creates the site on first run (its id is cached in .netlify/site.json), uploads
web/out as a zip, waits for the deploy to go live and prints the URL.

Usage:
    python scripts/deploy_netlify.py            # deploy web/out
    python scripts/deploy_netlify.py --name foothold-valley   # preferred site name on first run
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import zipfile
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "web" / "out"
SITE_FILE = ROOT / ".netlify" / "site.json"
API = "https://api.netlify.com/api/v1"


def zip_dir(folder: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(folder).as_posix())
    return buf.getvalue()


def get_or_create_site(client: httpx.Client, name: str) -> dict:
    if SITE_FILE.exists():
        site_id = json.loads(SITE_FILE.read_text(encoding="utf-8"))["site_id"]
        r = client.get(f"{API}/sites/{site_id}")
        if r.status_code == 200:
            return r.json()
    for candidate in (name, f"{name}-{int(time.time()) % 100000}"):
        r = client.post(f"{API}/sites", json={"name": candidate})
        if r.status_code in (200, 201):
            site = r.json()
            SITE_FILE.parent.mkdir(parents=True, exist_ok=True)
            SITE_FILE.write_text(json.dumps({"site_id": site["id"], "name": site["name"]}, indent=2), encoding="utf-8")
            return site
        if r.status_code != 422:  # 422 = name taken; try the suffixed name
            r.raise_for_status()
    raise SystemExit("could not create a Netlify site (names taken)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="foothold-valley")
    args = parser.parse_args()

    token = (dotenv_values(ROOT / ".env").get("NETLIFY_AUTH_TOKEN") or "").strip()
    if not token:
        print("NETLIFY_AUTH_TOKEN is missing from .env", file=sys.stderr)
        return 1
    if not (OUT_DIR / "index.html").exists():
        print(f"{OUT_DIR} has no index.html: run scripts/build_web_static.sh first", file=sys.stderr)
        return 1

    with httpx.Client(headers={"Authorization": f"Bearer {token}"}, timeout=120) as client:
        site = get_or_create_site(client, args.name)
        payload = zip_dir(OUT_DIR)
        print(f"site {site['name']} · uploading {len(payload) / 1e6:.1f} MB")
        r = client.post(
            f"{API}/sites/{site['id']}/deploys",
            content=payload,
            headers={"Content-Type": "application/zip"},
        )
        r.raise_for_status()
        deploy = r.json()
        for _ in range(90):
            state = client.get(f"{API}/deploys/{deploy['id']}").json()
            if state.get("state") in ("ready", "error"):
                deploy = state
                break
            time.sleep(2)
        if deploy.get("state") != "ready":
            print(f"deploy state: {deploy.get('state')} {deploy.get('error_message') or ''}", file=sys.stderr)
            return 1
        print(f"LIVE: {site.get('ssl_url') or site.get('url')}")
        print(f"deploy: {deploy.get('deploy_ssl_url') or deploy.get('deploy_url')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
