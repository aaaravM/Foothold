#!/usr/bin/env bash
# Shared helper (sourced by dev.sh / run_api.sh / reset.sh): resolves the project Python.
# Order: $FOOTHOLD_PY, FOOTHOLD_PY in repo-root .env (only that line is read, nothing is
# printed), .venv (Windows or POSIX layout), ~/.venvs/foothold, then python3/python on PATH.

foothold_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
}

foothold_python() {
  local root candidate
  root="$(foothold_root)"
  candidate="${FOOTHOLD_PY:-}"
  if [ -z "$candidate" ] && [ -f "$root/.env" ]; then
    candidate="$(grep -E '^[[:space:]]*FOOTHOLD_PY=' "$root/.env" | tail -n 1 | cut -d= -f2- | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/")"
  fi
  for c in "$candidate" \
           "$root/.venv/Scripts/python.exe" "$root/.venv/Scripts/python" "$root/.venv/bin/python" \
           "$HOME/.venvs/foothold/Scripts/python.exe" "$HOME/.venvs/foothold/bin/python"; do
    if [ -n "$c" ] && [ -x "$c" ]; then
      printf '%s\n' "$c"
      return 0
    fi
  done
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1; then
      command -v "$c"
      return 0
    fi
  done
  echo "error: no Python found; set FOOTHOLD_PY" >&2
  return 1
}
