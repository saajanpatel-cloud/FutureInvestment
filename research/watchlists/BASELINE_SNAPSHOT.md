# Baseline snapshot — FutureInvestment

**Established:** 2026-05-17  
**Shortlist hash:** `78c83165903b8737` (SHA-256 of sorted core tickers)  
**Core tickers (25):** B, CNC, CRUS, CVS, DIOD, EOG, FSLR, GEN, MPC, MU, NVDA, PATH, PFE, PLAB, PSX, QUBT, QRVO, SMCI, TENB, TSM, TXT, VLO, VST, VWS.CO, ZBH  

**Universe:** 481 manifest rows · ~350 `model_tier=full`  
**Dashboard:** `SINGLE_SCREEN_REPORT.html` (HTML + tracked CSV/JSON only; no PDF in this baseline)

## Quarterly playbook (manual process)

Per `research/sources/future-impact/BASELINE.md`, review each position quarterly with **INVEST / HOLD / REDUCE / SELL**. The dashboard **Monitor** tab supports per-ticker briefs and Finnhub context; it does not automate trade decisions or sleeve accounting.

## Goals vs dashboard (pass/fail)

| Intent | Section | Source | Status |
|--------|---------|--------|--------|
| £7.5k cap, drip, education-only | Discover + disclaimers | BASELINE.md, cover/exec | Pass |
| Six theme weights (32.5 / 27.5 / 10×4) | Discover weights | `fi_embed_discover_weights.py` | Pass |
| ~481 screen universe | Executive summary, Screen | `universe_manifest.csv` | Pass |
| 20–28 core, five-signal composite | Decide, `core-shortlist.json` | `fi_select_shortlist_growth.py` | Pass (25) |
| Rubric 6-dim + evidence | Rubric table | `rubric_scores.csv`, `_rubric_table_rows.inc.html` | Pass |
| Valuation stack | Value tab + JS | `fi_embed_value_tables.py`, `fi_embed_value_js.py` | Pass |
| Adversarial gate | Research + packs | `adversarial_packs.json`, enrich | Pass (25/25 in packs) |
| Finnhub market context | Monitor / shortlist | `fi_finnhub_context.py` | Pass (key in `.env`) |

## Core shortlist vs BASELINE theme targets (% of names)

| Theme slug | Target % | Actual % (25 names) | Notes |
|------------|----------|---------------------|-------|
| ai | 32.5 | 32.0 (8) | On target |
| energy | 27.5 | 28.0 (7) | On target |
| cyber | 10 | 12.0 (3) | Slightly over |
| auto | 10 | 12.0 (3) | Slightly over |
| health | 10 | 12.0 (3) | Slightly over |
| quantum | 10 | 4.0 (1) | Under; QUBT seat |

## Dynamic vs static after refresh

| Updates on `./scripts/refresh_watchlists.sh` | Client-only / manual |
|---------------------------------------------|----------------------|
| Snapshot, earnings, rubric | TradingView charts (internet) |
| Universe + core models (scenario, MC, risk, DCF) | Table sort, hash routing |
| Shortlist + narratives + Finnhub | Discover pillar essays (mostly static embeds) |
| Executive summary + changelog vs `_shortlist_prior.json` | Long qual `<details>` essays |
| `adversarial_packs.json` → enrich | BASELINE.md preference edits |

## Adversarial coverage (core)

All **25/25** core tickers have `workflow_e_complete` in `adversarial_packs.json`. Sources: **25 heuristic**, **0 LLM** (no `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` required for this baseline; packs still gate the shortlist).

## Secrets / compliance

- `.env` is gitignored; no API key patterns in tracked HTML/JSON/CSV.
- Disclaimers present on cover, executive summary, and `core-shortlist.json` disclaimer field.

## Yahoo health

Last probe: `research/watchlists/yahoo_status.json` — SPY price OK at refresh (see `checked_at_utc`).

## Candidates lane

`research/watchlists/candidates.csv` — header only (illustration row removed).

## Reproducibility

- Full refresh log: `/tmp/fi-refresh-baseline.log`
- Verifiers: `fi_verify_watchlist_refresh.py`, `fi_verify_report_core.py` — exit 0
- Embed fix: `fi_embed_deep_dive_runtime.py` patches in-place when `FI_DEEP_DIVE_RUNTIME_*` markers exist
- Monitor **Select stock** (`#dd-ticker`): options and order match Research shortlist (`load_core_tickers_display_order` + static `<option>` patch); verified on each refresh

## Changelog semantics

**GitHub baseline:** `main` @ v3.0 (2026-05-17). `_shortlist_prior.json` in this commit is the comparison point for the next `./scripts/refresh_watchlists.sh` — adds/drops and quality movers will appear in the executive summary and shortlist changelog.
