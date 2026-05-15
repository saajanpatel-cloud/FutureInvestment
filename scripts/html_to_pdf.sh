#!/usr/bin/env sh
# Build SINGLE_SCREEN_REPORT.pdf from HTML (uses print @media rules in the HTML).
# Output: <repo>/docs/SINGLE_SCREEN_REPORT.pdf
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HTML="$ROOT/research/watchlists/SINGLE_SCREEN_REPORT.html"
DOCS="$ROOT/docs"
PDF="$DOCS/SINGLE_SCREEN_REPORT.pdf"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
if ! test -x "$CHROME"; then
  echo "Set CHROME to your Google Chrome binary." >&2
  exit 1
fi
mkdir -p "$DOCS"
"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$PDF" "file://$HTML"
echo "$PDF"
