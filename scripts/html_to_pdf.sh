#!/usr/bin/env sh
# Build SINGLE_SCREEN_REPORT.pdf from the latest dashboard HTML.
# Syncs embeds from watchlist artifacts, then prints with Chrome headless.
# Output: <repo>/docs/SINGLE_SCREEN_REPORT.pdf
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${PY:-python3}"
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; fi
HTML="$ROOT/research/watchlists/SINGLE_SCREEN_REPORT.html"
DOCS="$ROOT/docs"
PDF="$DOCS/SINGLE_SCREEN_REPORT.pdf"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"

if ! test -x "$CHROME"; then
  echo "Set CHROME to your Google Chrome binary." >&2
  exit 1
fi

echo "Syncing dashboard HTML from latest watchlist artifacts…" >&2
"$PY" scripts/fi_embed_single_screen.py >&2
"$PY" scripts/fi_embed_discover_weights.py >&2 || true
"$PY" scripts/fi_embed_industry_themes.py >&2 || true
"$PY" scripts/fi_embed_shortlist_proposed.py >&2 || true
"$PY" scripts/fi_embed_qualitative_core.py >&2 || true
"$PY" scripts/fi_embed_value_tables.py >&2 || true
"$PY" scripts/fi_embed_value_js.py >&2 || true
"$PY" scripts/fi_embed_decide_matrix.py >&2 || true
"$PY" scripts/fi_embed_shortlist_changelog.py >&2 || true
"$PY" scripts/fi_embed_executive_summary.py >&2 || true
"$PY" scripts/fi_embed_deep_dive_runtime.py >&2 || true
"$PY" scripts/fi_embed_deep_dive_layout.py >&2 || true
"$PY" scripts/fi_restructure_monitor_html.py >&2 || true
if [ -f research/watchlists/dcf_sensitivity.csv ]; then
  "$PY" scripts/fi_embed_dcf_grids.py >&2 || true
fi

mkdir -p "$DOCS"
# virtual-time-budget lets inline JS (SCENARIOS, filters) finish before paint-to-PDF
"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer \
  --run-all-compositor-stages-before-draw \
  --virtual-time-budget=15000 \
  --print-to-pdf="$PDF" "file://$HTML"
echo "$PDF"
