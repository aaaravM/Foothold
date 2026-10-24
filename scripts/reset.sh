#!/usr/bin/env bash
# Reset runtime state: delete api/.runtime (sqlite db + LangGraph checkpoints), then
# re-seed with scripts/seed.py if it exists. Stop the API first on Windows: open
# sqlite files cannot be deleted while the server holds them.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_py.sh"
ROOT="$(foothold_root)"
cd "$ROOT"

if [ -d api/.runtime ]; then
  if ! rm -rf api/.runtime; then
    echo "error: could not delete api/.runtime (is the API running? stop it and retry)" >&2
    exit 1
  fi
  echo "removed api/.runtime"
else
  echo "api/.runtime not present (nothing to remove)"
fi

if [ -f scripts/seed.py ]; then
  PY="$(foothold_python)"
  echo "seeding with scripts/seed.py"
  "$PY" scripts/seed.py
else
  echo "scripts/seed.py not found (skipping seed)"
fi
