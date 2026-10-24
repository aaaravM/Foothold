#!/usr/bin/env bash
# Static Next.js export for Netlify -> web/out
# Usage: scripts/build_web_static.sh [fallback public API url]
#
# The site discovers the API at runtime (web/src/lib/api.ts): ?api=<url> -> localStorage ->
# Supabase public_config 'api_url' -> NEXT_PUBLIC_API_URL -> http://localhost:8000.
# So the URL argument is only a fallback; a new tunnel URL needs scripts/register_api_url.sh, not a rebuild.
# Uses a separate distDir (.next-export) so a running `next dev` (.next) is untouched.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Read KEY from the environment, else web/.env.local, else the repo .env (value never printed).
read_var() {
  local name="$1" fallback_name="${2:-}" v="${!1:-}"
  if [ -z "$v" ] && [ -f "$ROOT/web/.env.local" ]; then
    v="$(grep -E "^${name}=" "$ROOT/web/.env.local" | tail -1 | cut -d= -f2- | tr -d '\r"' || true)"
  fi
  if [ -z "$v" ] && [ -n "$fallback_name" ] && [ -f "$ROOT/.env" ]; then
    v="$(grep -E "^${fallback_name}=" "$ROOT/.env" | tail -1 | cut -d= -f2- | tr -d '\r"' || true)"
  fi
  printf '%s' "$v"
}

API_URL="${1:-$(read_var NEXT_PUBLIC_API_URL)}"
API_URL="${API_URL%/}"
SUPA_URL="$(read_var NEXT_PUBLIC_SUPABASE_URL SUPABASE_URL)"
SUPA_KEY="$(read_var NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY SUPABASE_PUBLISHABLE_KEY)"
case "$SUPA_KEY" in
  ""|sb_publishable_*) ;;
  *) echo "refusing to bundle: NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY does not look like a publishable key" >&2; exit 2 ;;
esac

cd "$ROOT/web"
rm -rf out .next-export
echo "Building static export"
echo "  fallback NEXT_PUBLIC_API_URL=${API_URL:-<none: localhost>}"
echo "  NEXT_PUBLIC_SUPABASE_URL=${SUPA_URL:-<none: Supabase discovery off>}"
echo "  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=$([ -n "$SUPA_KEY" ] && echo set || echo '<none>')"
NEXT_OUTPUT=export NEXT_DIST_DIR=.next-export \
  NEXT_PUBLIC_API_URL="$API_URL" \
  NEXT_PUBLIC_SUPABASE_URL="$SUPA_URL" \
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY="$SUPA_KEY" \
  npm run build
# With output:"export" + a custom distDir, Next writes the static site into distDir.
if [ -f .next-export/index.html ]; then mv .next-export out; fi
if [ ! -f out/index.html ]; then
  echo "build finished but web/out/index.html is missing" >&2
  exit 1
fi
echo "OK: $(find out -name '*.html' | wc -l) HTML pages in web/out (publish this folder)"
