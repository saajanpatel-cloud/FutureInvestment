#!/usr/bin/env sh
# Regenerate sleeve snapshot CSV/MD and HTML row fragments from universe_manifest.csv.
# Run from repo root: Projects/FutureInvestment
# Usage: ./scripts/refresh_watchlists.sh
# Requires: .venv with scripts/requirements.txt (yfinance).
#
# Compute order: snapshot → earnings pull → rubric score (6 dims) → rubric notes → universe valuation →
#   adversarial review (Workflow E) → shortlist → Finnhub context → fi_enrich → embeds → verify → prior snapshot.
# Set FI_SKIP_ADVERSARIAL=1 to skip LLM/heuristic adversarial pass before shortlist.
# Definition of done: same core tickers + fresh rubric/models/narratives in Research, Value, Decide, Monitor.
# Optional LLM polish: scripts/fi_narrative_polish.py (manual).
# Set FI_SKIP_UNIVERSE_VALUATION=1 to skip the heavy universe pass (legacy Borda shortlist).
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${PY:-python3}"
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; fi
"$PY" scripts/fi_yahoo_health.py || echo "WARN: Yahoo Finance (yfinance) unreachable — snapshot/earnings may fail" >&2
MAN="research/watchlists/universe_manifest.csv"
CSV="research/watchlists/rubric_universe.csv"

MD="research/watchlists/rubric_universe.md"
CORE_TXT="research/watchlists/report_core_tickers.txt"
SCEN_U="research/watchlists/scenario_assumptions_universe.csv"

"$PY" scripts/fi_snapshot.py --manifest "$MAN" --csv "$CSV" --md "$MD"
# Default table order: company name A–Z, then theme label A–Z (uses rubric_universe short_name).
"$PY" scripts/fi_sort_manifest_order.py --manifest "$MAN" --names-csv "$CSV"
"$PY" scripts/fi_universe_html_rows.py --manifest "$MAN" --csv "$CSV" \
  > research/watchlists/_universe_table_rows.inc.html
"$PY" scripts/fi_snapshot_html_rows.py --manifest "$MAN" --csv "$CSV" \
  > research/watchlists/_snapshot_table_rows.inc.html
"$PY" scripts/fi_earnings_pull.py || echo "WARN: fi_earnings_pull had failures — see stderr" >&2
"$PY" scripts/fi_score_rubric_from_financials.py
"$PY" scripts/fi_sync_rubric_from_earnings.py --rewrite-notes

"$PY" scripts/fi_sync_scenario_assumptions_from_core.py --write-universe --universe-out "$SCEN_U"

if [ "${FI_SKIP_UNIVERSE_VALUATION:-}" = "1" ]; then
  echo "WARN: FI_SKIP_UNIVERSE_VALUATION=1 — skipping universe valuation + fi_rank_universe; shortlist uses legacy pool if rank file missing." >&2
else
  "$PY" scripts/fi_scenarios.py --assumptions "$SCEN_U" \
    --csv research/watchlists/scenario_results_universe.csv \
    --html research/watchlists/scenario_fragment_universe.html
  "$PY" scripts/fi_monte_carlo.py --assumptions "$SCEN_U" \
    --csv research/watchlists/monte_carlo_results_universe.csv \
    --html research/watchlists/monte_carlo_fragment_universe.html --sims 2000 || true
  "$PY" scripts/fi_risk_metrics.py --assumptions "$SCEN_U" \
    --csv research/watchlists/risk_metrics_universe.csv \
    --html research/watchlists/risk_fragment_universe.html || true
  "$PY" scripts/fi_dcf_sensitivity.py --assumptions "$SCEN_U" \
    --csv research/watchlists/dcf_sensitivity_universe.csv \
    --html research/watchlists/dcf_sensitivity_fragment_universe.html || true
  "$PY" scripts/fi_rank_universe.py || true
  "$PY" scripts/fi_composite_universe_rank.py || true
fi

if [ "${FI_SKIP_ADVERSARIAL:-}" != "1" ]; then
  "$PY" scripts/fi_adversarial_review.py || echo "WARN: fi_adversarial_review had failures — see stderr" >&2
fi
"$PY" scripts/fi_select_shortlist_growth.py
"$PY" scripts/fi_sync_scenario_assumptions_from_core.py

"$PY" scripts/fi_scenarios.py --assumptions research/watchlists/scenario_assumptions.csv \
  --csv research/watchlists/scenario_results.csv \
  --html research/watchlists/scenario_fragment.html || true
"$PY" scripts/fi_monte_carlo.py --assumptions research/watchlists/scenario_assumptions.csv \
  --csv research/watchlists/monte_carlo_results.csv \
  --html research/watchlists/monte_carlo_fragment.html --sims 10000 || true
"$PY" scripts/fi_risk_metrics.py --assumptions research/watchlists/scenario_assumptions.csv \
  --csv research/watchlists/risk_metrics.csv \
  --html research/watchlists/risk_fragment.html || true
"$PY" scripts/fi_dcf_sensitivity.py --assumptions research/watchlists/scenario_assumptions.csv \
  --csv research/watchlists/dcf_sensitivity.csv \
  --html research/watchlists/dcf_sensitivity_fragment.html || true

"$PY" scripts/fi_finnhub_context.py --tickers-file "$CORE_TXT" \
  --csv research/watchlists/finnhub_context.csv \
  --html research/watchlists/finnhub_context_fragment.html \
  --news-json research/watchlists/finnhub_news.json || true
"$PY" scripts/fi_company_profile.py || true
"$PY" scripts/fi_enrich_core_shortlist.py
"$PY" scripts/fi_rubric_html_rows.py --manifest "$MAN" \
  --scores research/watchlists/rubric_scores.csv \
  > research/watchlists/_rubric_table_rows.inc.html
"$PY" scripts/fi_export_watchlist_example.py
"$PY" scripts/fi_embed_single_screen.py
"$PY" scripts/fi_embed_discover_weights.py || true
"$PY" scripts/fi_embed_industry_themes.py || true
"$PY" scripts/fi_tag_rubric_report_core.py
"$PY" scripts/fi_embed_shortlist_proposed.py
"$PY" scripts/fi_embed_qualitative_core.py
"$PY" scripts/fi_embed_value_tables.py
"$PY" scripts/fi_embed_value_js.py
"$PY" scripts/fi_embed_deep_dive_runtime.py
"$PY" scripts/fi_embed_deep_dive_layout.py
"$PY" scripts/fi_embed_deep_dive_select.py
"$PY" scripts/fi_embed_decide_matrix.py
"$PY" scripts/fi_embed_shortlist_changelog.py
if [ -f research/watchlists/dcf_sensitivity.csv ]; then
  "$PY" scripts/fi_embed_dcf_grids.py || true
fi
"$PY" scripts/fi_save_shortlist_prior.py
cp -f watchlist-ui/core-shortlist.json watchlist-ui/watchlist.example.json 2>/dev/null || true
"$PY" scripts/fi_verify_watchlist_refresh.py
"$PY" scripts/fi_verify_report_core.py
echo "OK: full refresh — rubric, models, narratives, Research/Value/Decide/Monitor embeds, changelog, prior snapshot"
