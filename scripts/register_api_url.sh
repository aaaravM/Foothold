#!/usr/bin/env bash
# Register the API's public URL in Supabase public_config (key 'api_url') so the Netlify site can find it.
#   scripts/register_api_url.sh https://xyz.trycloudflare.com   # upsert
#   scripts/register_api_url.sh clear                            # delete the row
# Reads SUPABASE_URL and SUPABASE_SECRET_KEY from the environment or the repo-root .env (never printed).
# Exit 0 on success, 1 on a usage error, 2 when Supabase rejects the write (e.g. schema.sql not run yet).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARG="${1:-}"
if [ -z "$ARG" ]; then
  echo "usage: scripts/register_api_url.sh <https-url> | clear" >&2
  exit 1
fi

env_get() {  # value of KEY from the environment, else from .env (only that line is read)
  local key="$1" val="${!1:-}"
  if [ -z "$val" ] && [ -f "$ROOT/.env" ]; then
    val="$(grep -E "^[[:space:]]*$key=" "$ROOT/.env" | tail -n 1 | cut -d= -f2- | tr -d '\r' \
      | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/")"
  fi
  printf '%s' "$val"
}

SB_URL="$(env_get SUPABASE_URL)"
SB_URL="${SB_URL%/}"
SB_KEY="$(env_get SUPABASE_SECRET_KEY)"
if [ -z "$SB_URL" ] || [ -z "$SB_KEY" ]; then
  echo "register_api_url: SUPABASE_URL / SUPABASE_SECRET_KEY not set; skipped" >&2
  exit 2
fi
case "$SB_KEY" in sb_publishable_*) echo "register_api_url: a secret (sb_secret_) key is required; skipped" >&2; exit 2 ;; esac

# Headers go through a private temp file so the key never appears on a command line.
HDR="$(mktemp)"
trap 'rm -f "$HDR"' EXIT
chmod 600 "$HDR"
printf 'apikey: %s\nAuthorization: Bearer %s\nContent-Type: application/json\n' "$SB_KEY" "$SB_KEY" >"$HDR"

if [ "$ARG" = "clear" ]; then
  CODE="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 -X DELETE -H @"$HDR" \
    "$SB_URL/rest/v1/public_config?key=eq.api_url" || echo 000)"
  ACTION="cleared api_url"
else
  URL="${ARG%/}"
  case "$URL" in https://*) ;; *) echo "register_api_url: URL must start with https://" >&2; exit 1 ;; esac
  case "$URL" in *'"'*|*'\'*|*' '*) echo "register_api_url: invalid URL" >&2; exit 1 ;; esac
  NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  CODE="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 -X POST -H @"$HDR" \
    -H 'Prefer: resolution=merge-duplicates,return=minimal' \
    --data "{\"key\":\"api_url\",\"value\":\"$URL\",\"updated_at\":\"$NOW\"}" \
    "$SB_URL/rest/v1/public_config?on_conflict=key" || echo 000)"
  ACTION="api_url = $URL"
fi

case "$CODE" in
  2*) echo "public_config: $ACTION"; exit 0 ;;
  404) echo "public_config: HTTP 404 (table missing: run supabase/schema.sql in the Supabase SQL editor)" >&2; exit 2 ;;
  *) echo "public_config: write failed (HTTP $CODE)" >&2; exit 2 ;;
esac
