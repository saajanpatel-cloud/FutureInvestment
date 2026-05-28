#!/usr/bin/env bash
# Serve SINGLE_SCREEN_REPORT.html over HTTP so Monitor TradingView charts work (file:// blocks embeds).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$ROOT/research/watchlists"
BASE_PORT="${PORT:-8765}"

pick_port() {
  local p="$1"
  while lsof -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; do
    p=$((p + 1))
  done
  echo "$p"
}

PORT="$(pick_port "$BASE_PORT")"
URL="http://127.0.0.1:${PORT}/SINGLE_SCREEN_REPORT.html#monitor"

echo "Serving FutureInvestment dashboard (charts require http, not file://)"
echo "  Directory: $DIR"
if [[ "$PORT" != "$BASE_PORT" ]]; then
  echo "  Note:      port $BASE_PORT was busy; using $PORT"
fi
echo "  Open:      $URL"
echo ""
echo "Press Ctrl+C to stop."
echo ""

cd "$DIR"
if command -v open >/dev/null 2>&1; then
  (sleep 0.4 && open "$URL") &
fi
exec python3 -m http.server "$PORT"
