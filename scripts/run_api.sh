#!/usr/bin/env bash
# Run the API in the foreground with auto-reload.
#   scripts/run_api.sh                 # port 8000 (API_PORT to override)
#   scripts/run_api.sh --log-level debug
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_py.sh"
ROOT="$(foothold_root)"
PY="$(foothold_python)"
cd "$ROOT"
# --timeout-graceful-shutdown: open SSE streams must not stall reloads/shutdown.
exec "$PY" -m uvicorn main:app --app-dir api --reload --reload-dir api \
  --timeout-graceful-shutdown 2 --port "${API_PORT:-8000}" "$@"
