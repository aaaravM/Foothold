#!/usr/bin/env bash
# Static Next.js export for Netlify -> web/out
# Usage: scripts/build_web_static.sh https://<name>.trycloudflare.com
# Uses a separate distDir (.next-export) so a running `next dev` (.next) is untouched.
set -euo pipefail
API_URL="${1:-${NEXT_PUBLIC_API_URL:-}}"
if [ -z "$API_URL" ]; then
  echo "usage: $0 <public API url, e.g. https://xyz.trycloudflare.com>" >&2
  exit 2
fi
API_URL="${API_URL%/}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/web"
rm -rf out .next-export
echo "Building static export with NEXT_PUBLIC_API_URL=$API_URL"
NEXT_OUTPUT=export NEXT_DIST_DIR=.next-export NEXT_PUBLIC_API_URL="$API_URL" npm run build
# With output:"export" + a custom distDir, Next writes the static site into distDir.
if [ -f .next-export/index.html ]; then mv .next-export out; fi
if [ ! -f out/index.html ]; then
  echo "build finished but web/out/index.html is missing" >&2
  exit 1
fi
echo "OK: $(find out -name '*.html' | wc -l) HTML pages in web/out (publish this folder)"
