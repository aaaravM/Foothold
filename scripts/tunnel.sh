#!/usr/bin/env bash
# Public HTTPS URL for the local Foothold API via a Cloudflare quick tunnel (no account).
#   scripts/tunnel.sh            # tunnels http://127.0.0.1:8000, prints https://*.trycloudflare.com
#   scripts/tunnel.sh --check    # only download/verify cloudflared, then exit
#   TUNNEL_PROVIDER=ssh scripts/tunnel.sh   # fallback: localhost.run over plain ssh (no download)
# Leave it running while the Netlify site is in use; Ctrl+C stops the tunnel.
# The URL changes every time the tunnel restarts -> rebuild + redeploy the static site.
set -euo pipefail
TARGET="${TUNNEL_TARGET:-http://127.0.0.1:8000}"

if [ "${TUNNEL_PROVIDER:-cloudflared}" = "ssh" ]; then
  echo "Opening a localhost.run tunnel over ssh (the https://....lhr.life URL is printed below) ..."
  exec ssh -tt -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes     -R "80:${TARGET#http://}" nokey@localhost.run
fi
BIN_DIR="${CLOUDFLARED_DIR:-$HOME/.venvs/bin}"
EXE="$BIN_DIR/cloudflared.exe"
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) ASSET="cloudflared-windows-amd64.exe" ;;
  Linux*) ASSET="cloudflared-linux-amd64"; EXE="$BIN_DIR/cloudflared" ;;
  Darwin*) ASSET=""; EXE="$(command -v cloudflared || echo "")" ;;
esac
URL="https://github.com/cloudflare/cloudflared/releases/latest/download/$ASSET"

if command -v cloudflared >/dev/null 2>&1; then
  EXE="$(command -v cloudflared)"
elif [ ! -x "$EXE" ]; then
  if [ -z "$ASSET" ]; then echo "install cloudflared: brew install cloudflared" >&2; exit 1; fi
  mkdir -p "$BIN_DIR"
  echo "Downloading cloudflared from the official GitHub release ..."
  curl -fL --retry 4 --retry-delay 2 --connect-timeout 15 -o "$EXE.part" "$URL"
  mv "$EXE.part" "$EXE"
  chmod +x "$EXE"
fi
"$EXE" --version

[ "${1:-}" = "--check" ] && exit 0

if ! curl -fsS --max-time 5 "$TARGET/health" >/dev/null; then
  echo "API is not answering at $TARGET/health - start it first (scripts/run_api.sh)" >&2
  exit 1
fi

LOG="$(mktemp)"
"$EXE" tunnel --no-autoupdate --url "$TARGET" >"$LOG" 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null || true; rm -f "$LOG"' EXIT INT TERM
PUBLIC=""
for _ in $(seq 1 60); do
  PUBLIC="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -n 1 || true)"
  [ -n "$PUBLIC" ] && break
  kill -0 $PID 2>/dev/null || { cat "$LOG" >&2; exit 1; }
  sleep 1
done
if [ -z "$PUBLIC" ]; then echo "no tunnel URL after 60 s:" >&2; tail -20 "$LOG" >&2; exit 1; fi
echo
echo "TUNNEL_URL=$PUBLIC"
echo "Next: scripts/build_web_static.sh $PUBLIC   (then deploy web/out to Netlify)"
echo "Keep this window open. Ctrl+C stops the tunnel."
[ "${TUNNEL_ONESHOT:-0}" = "1" ] && { sleep 8; curl -fsS --max-time 15 "$PUBLIC/health" | head -c 200; echo; exit 0; }
wait $PID
