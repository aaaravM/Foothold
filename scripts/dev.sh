#!/usr/bin/env bash
# Start the API (uvicorn --reload, port 8000) and the web dev server (Next.js) together.
# Logs: .logs/api.log and .logs/web.log. Ctrl+C stops both.
#   API_PORT=8000 WEB_PORT=3000 scripts/dev.sh
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_py.sh"
ROOT="$(foothold_root)"
PY="$(foothold_python)"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
cd "$ROOT"
mkdir -p .logs

echo "python: $PY"
"$PY" -m uvicorn main:app --app-dir api --reload --reload-dir api --timeout-graceful-shutdown 2 \
  --port "$API_PORT" >> .logs/api.log 2>&1 &
API_PID=$!
(cd web && exec npm run dev -- --port "$WEB_PORT") >> .logs/web.log 2>&1 &
WEB_PID=$!

stop() {
  trap - INT TERM EXIT
  for pid in "$API_PID" "$WEB_PID"; do
    # Git Bash: kill the whole Windows process tree (npm spawns node children).
    if [ -r "/proc/$pid/winpid" ] && command -v taskkill >/dev/null 2>&1; then
      taskkill //F //T //PID "$(cat "/proc/$pid/winpid")" >/dev/null 2>&1 || true
    fi
    kill "$pid" >/dev/null 2>&1 || true
  done
}
trap stop INT TERM EXIT

echo "API  http://localhost:$API_PORT  (docs: /docs, log: .logs/api.log)"
echo "Web  http://localhost:$WEB_PORT  (log: .logs/web.log)"
echo "Ctrl+C to stop both."
wait
