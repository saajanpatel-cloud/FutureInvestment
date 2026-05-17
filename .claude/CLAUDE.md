# FutureInvestment (Claude Code)

## Communication style

- Keep responses short.
- Use simple, plain language.
- Build understanding progressively: start with the basics, then layer in complexity and data points.
- Do not front-load jargon.

Multi-sector **thematic equity research** project: latent real-world demand, public-company mapping (including picks-and-shovels), optional forum sentiment, and a **mandatory adversarial bear-case** pass before any **top pick** label. Outputs are **education and research**, not personalized investment advice.

## Layout

| Path | Purpose |
|------|---------|
| `.claude/skills/thematic-equity-research/SKILL.md` | Primary workflow: memos, scoring, adversarial templates |
| `.claude/skills/carousel/` | Example scaffold |
| `.claude/skills/drill/` | Example scaffold |
| `research/memoes/` | Theme and pillar latent-demand memos (Markdown or your choice) |
| `research/sources/future-impact/` | **Future Impact** PDFs + **`BASELINE.md`** (personalised sleeve, theme weights, drip cap—read first for aligned runs) |
| `research/watchlists/` | Dated shortlists, **`universe_manifest.csv`**, **`rubric_scores.csv`**, **`report_core_tickers.txt`** (Decide shortlist → PDF rubric subset), row fragments (`_*.inc.html`), **`SINGLE_SCREEN_REPORT.html`** |
| `scripts/` | Phase 2 CLI: snapshot, mentions, Markdown run scaffold |
| `watchlist-ui/` | Static HTML UI for `watchlist.json` (notes + sentiment secondary) |

Create `research/memoes/` and `research/watchlists/` when you start saving outputs.

## Future Impact baseline

When the user references **Future Impact** or this sleeve: read **`research/sources/future-impact/BASELINE.md`** first (theme weights, £7.5k cap, drip deployment, omitted climate/water bucket, seed-ticker rules). Use PDFs in the same folder only for deep pulls—do not re-ingest full PDFs every session.

## Token-efficient runs

- **Baseline-first:** `BASELINE.md` + paths to existing memos/watchlists, not pasted prior outputs.
- **Scope:** Prefer one pillar or theme per session; follow-ups = diffs or single-ticker updates.
- **Artifacts on disk:** Long memos, Workflow C/E packs under `research/`; chat = short summary + paths.
- **Tables:** `fi_snapshot.py` → CSV/MD files; link paths instead of regenerating huge tables in prose.
- **Between subtasks:** `/compact` when using Claude Code with long context.

## How to invoke

1. Open this repo from **`AI_Projects`** or **`FutureInvestment`** so project `.claude/` resolves correctly.
2. Ask the agent to **use the `thematic-equity-research` skill** (or reference `.claude/skills/thematic-equity-research/SKILL.md`).
3. For heavy synthesis (latent demand + adversarial passes), prefer your **strongest reasoning** model profile and **web verification** where available.

## Dashboard & document playbook

### Voice & fields (match PDF, not essays)

- **Tone:** Progressive, plain-language **bullets** (` · ` separator) in table cells: what the business does → growth/margins → scorecard/pool rank → risks. No `GM`/`OM`/`MSPR` jargon in reader-facing copy.
- **Narrative module:** **`scripts/fi_narrative.py`** — shared formatters for shortlist, rubric notes, research matrices, qual bull/bear/watch, and Decide verdict. **`refresh_watchlists.sh`** regenerates all rule-based text each run (`fi_sync_rubric_from_earnings.py --rewrite-notes`, then **`fi_enrich_core_shortlist.py`**, then embeds). Optional manual polish: **`scripts/fi_narrative_polish.py`** (overwritten on next refresh unless saved to overrides).
- **Shortlist columns** (`why_this_name`, `market_context`, `key_risk_kill`) plus enrich fields `research_thesis`, `research_premortem`, `research_kill`, `qual_bull`, `qual_bear`, `qual_watch` on **`core-shortlist.json`**.
- **Rubric notes:** rebuilt from earnings on every full refresh via **`--rewrite-notes`** in the refresh script.
- **DCF:** **`fi_dcf_sensitivity.py`** emits **paired WACC columns** (8–9%, 10–11%, 12%). **`fi_patch_single_screen_dcf_compact.py`** updates **`SINGLE_SCREEN_REPORT.html`** from **`dcf_sensitivity.csv`**; **`refresh_watchlists.sh`** runs it when the CSV exists. Tickers not in the scenario CSV keep legacy inline grids until the scenario is extended and DCF is regenerated.

### Pipelines, order, and verification

- **Default:** `./scripts/refresh_watchlists.sh` from repo root (network; `.venv` auto-detected). **Do not** ask the user to run scripts by hand for routine “update dashboard / shortlist / snapshot” requests—run the pipeline and interpret results.
- **Compute order (what actually runs):** snapshot + HTML row fragments → **`fi_earnings_pull.py`** (manifest-only) → **`fi_score_rubric_from_financials.py`** (six dims) → **`fi_sync_rubric_from_earnings.py --rewrite-notes`** → **`fi_sync_scenario_assumptions_from_core.py --write-universe`** (`model_tier=full` only) → **universe** scenario + risk + MC + DCF → **`fi_rank_universe.py`** + **`fi_composite_universe_rank.py`** → **`fi_adversarial_review.py`** (Workflow E packs; skip with **`FI_SKIP_ADVERSARIAL=1`**) → **`fi_select_shortlist_growth.py`** (gates pool + quantum seat from packs) → sync **core** assumptions → **core** valuation → **`fi_finnhub_context.py`** → **`fi_enrich_core_shortlist.py`** (merges packs into narratives) → rubric rows → embeds → **`fi_save_shortlist_prior.py`** → **`fi_verify_watchlist_refresh.py`** (earnings/rubric + adversarial pack coverage + `node --check` on Value JS) + **`fi_verify_report_core.py`**.
- **`FI_SKIP_UNIVERSE_VALUATION=1`:** skips the heavy universe pass and `fi_rank_universe`; shortlist falls back to **legacy Borda** unless `universe_valuation_rank.csv` is already populated from a prior full run.
- **`FI_SKIP_ADVERSARIAL=1`:** skips **`fi_adversarial_review.py`**; shortlist uses existing **`research/watchlists/adversarial_packs.json`** or empty gates (heuristic/LLM packs not refreshed).
- **Adversarial automation:** **`fi_adversarial_review.py`** writes **`adversarial_packs.json`** (+ optional **`research/memoes/adversarial/{TICKER}.md`**). Batch = theme_only sleeves (quantum/space) ∪ composite pool ∪ prior core, minus fresh complete packs. Uses **`ANTHROPIC_API_KEY`** or **`OPENAI_API_KEY`**; without keys, **heuristic** Workflow E still runs. Cap per run: **`FI_ADVERSARIAL_MAX`** (default 40). Manual polish of narrative only: **`fi_narrative_polish.py`**.
- **Narrative / reader order:** **`SINGLE_SCREEN_REPORT.html`** section order is **unchanged** (snapshot → universe → rubric → shortlist → valuation blocks, etc.); only the **data** feeding those sections updates. Selection can be valuation-first **without** reordering the HTML story.
- **End state:** Script finishes with **`fi_verify_watchlist_refresh.py`** and **`fi_verify_report_core.py`**. Reply with verifier **OK** lines, **`shortlist_n`**, path to **`research/watchlists/SINGLE_SCREEN_REPORT.html`**, and any **WARN** lines.
- **Order gotcha:** DCF grids are rebuilt by **`fi_embed_dcf_grids.py`** from core tickers only (not patch-in-place on stale HTML).
- **Executive Summary:** Regenerated each refresh via **`fi_embed_executive_summary.py`** from `core-shortlist.json`, model CSVs, and `selection_memo.shortlist_delta` (adds/drops vs prior).
- **PDF:** Not part of default refresh. Run **`./scripts/html_to_pdf.sh`** only when the user wants an updated **`docs/SINGLE_SCREEN_REPORT.pdf`** (embeds run first, including Executive Summary).

### Shortlist policy (encoded + product intent)

- **Size:** **Minimum 20** core names; up to **28** when **`fi_rank_universe`** tiers allow expansion (`selection_memo.valuation_first`). Legacy mode (no rank file): same numeric caps with Borda-only pool.
- **Composite mode** (default when universe models complete): pool ≈60 by **`universe_composite_rank.csv`** — weighted percentiles of scenario, rubric, risk, Monte Carlo, and DCF (`research/watchlists/shortlist_weights.json`); theme caps; tier expansion when **`universe_valuation_rank.csv`** present. Anchors (e.g. **`NVDA`**) can enter pool below cutoff if rubric bar clears.
- **Valuation-first fallback:** composite CSV absent but valuation rank present — scenario-only pool (older behaviour).
- **Legacy mode:** rubric pool + four-lens Borda + caps when rank files absent.
- **Market context (default):** **`fi_finnhub_context.py`** (wired in `refresh_watchlists.sh`) when **`FINNHUB_API_KEY`** is in repo-root **`.env`** ([free registration](https://finnhub.io/register)). Free-tier endpoints: analyst recommendations, insider MSPR, company-news count, earnings dates. Outputs `finnhub_context.csv` + `finnhub_context_fragment.html` → **`market_context`** on core shortlist. **Deprecated:** `fi_sentiment.py` (retail social; Finnhub social-sentiment is premium). **`.env` is gitignored.**
- **Market-context refresh:** If **`FINNHUB_API_KEY`** is missing, `market_context` rows show the enrich placeholder — check stderr and verifier WARNs; do not block the rest of refresh.

### Universe tiers (~500 screen / ~350 modelled)

- **`universe_manifest.csv`:** `model_tier=full` (≤350) gets universe scenario / MC / DCF; `screen_only` gets snapshot + earnings + rubric every refresh.
- **Expand once:** `python3 scripts/fi_setup_universe_tiers.py` then full refresh.
- **Candidates lane:** `research/watchlists/candidates.csv` (`watch` | `promote` | `rejected`) — promote appends to manifest and re-runs refresh.

### Growth = 1 (rubric) — review policy, not auto-swap

- **Growth** on the rubric tracks latest-quarter revenue YoY (mechanical). It is a **signal**, not the whole thesis.
- **Core shortlist** with Growth=1 **and** Tier 3 / weak composite / bear-dominant scenario: **review for swap** within the same theme at the next quarterly refresh; prefer a higher-growth peer from the pool.
- **Documented turnaround** (backlog, segment re-acceleration, credible base case): **keep** with an explicit note in Monitor + adversarial pass (`selection_memo.exception` suppresses verifier WARN).
- **Universe-only** Growth=1: keep on the screen list as comparator or avoid example.
- **Growth=1 and weak margins/tail** (total ≤ 10): strong **demote** candidate from `model_tier=full` when at cap.

### Full refresh + verifier pass (agent checklist)

When the user asks for this **explicitly**:

1. **`pip install -r scripts/requirements.txt`** in **`.venv`** if needed.
2. Confirm **`.env`** has **`FINNHUB_API_KEY`** for live market context; if missing, **tell the user once** to copy **`.env.example`** → **`.env`**. Still run refresh — snapshot/rubric/shortlist/embed/verify proceed without Finnhub.
3. Run **`./scripts/refresh_watchlists.sh`** from repo root (network).
4. Report **verifier OK/WARN**, **shortlist churn** (if any), **market_context** sample lines (not all placeholders if Finnhub works), yfinance noise summary, and **DCF patch** line (`Patched N…` vs `No DCF tables patched` when already compact).

### Definition of done (full refresh)

After **`./scripts/refresh_watchlists.sh`**, the same **core tickers** (20–28) should appear with fresh **rubric**, **models**, and **narratives** in:

| Tab | Live surfaces |
|-----|----------------|
| **Research** | Combined research & adversarial snapshot table; qual bull/bear from packs when present (`fi_adversarial_review.py` → enrich) |
| **Value** | Scenario / risk / MC tables (`fi_embed_value_tables.py`); deep-dive JS (`fi_embed_value_js.py`) |
| **Decide** | Matrix + verdict (`fi_embed_decide_matrix.py`) |
| **Monitor** | Finnhub context fragment (`fi_finnhub_context.py` + `fi_embed_single_screen.py`) |

**Changelog:** `selection_memo.shortlist_delta` in **`core-shortlist.json`** + HTML block (`fi_embed_shortlist_changelog.py`). Compares to **`research/watchlists/_shortlist_prior.json`** from the **previous** refresh only.

**Verifier:** `fi_verify_watchlist_refresh.py` fails if any core ticker is missing from the tables above or from `SCENARIOS` JS keys; **WARN** if a core ticker lacks `workflow_e_complete` in **`adversarial_packs.json`** or still has `[Auto stub]` premortem after enrich.

**Still manual (v1):** long qual `<details>` essays under Research; theme pillar copy.

## Commands

From `Projects/FutureInvestment`:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r scripts/requirements.txt
python scripts/fi_yahoo_health.py   # Yahoo Finance via yfinance (no API key)
```

**Indicative fundamentals snapshot** (yfinance + optional Stooq close + optional FMP price if `FMP_API_KEY` is set; not investment-grade data; SEC + regulatory lookup URLs):

```bash
python scripts/fi_snapshot.py --tickers NVDA,AMD --csv research/watchlists/snapshot.csv
python scripts/fi_snapshot.py --file scripts/example_tickers.txt --md research/watchlists/snapshot.md
```

**Tier 0 sentiment helper:** count ticker-like tokens in a pasted forum dump (stdin or `--text-file`):

```bash
python scripts/fi_mentions.py --tickers NVDA,AMD,IONQ --text-file forum_paste.txt --csv research/watchlists/mentions.csv
```

**Markdown run scaffold** (embeds snapshot table for the ticker list you pass, then placeholders for latent demand, linkage, sentiment, adversarial, watchlist):

```bash
python scripts/fi_report_scaffold.py --manifest research/watchlists/universe_manifest.csv --out research/watchlists/run-2026-05-10.md
python scripts/fi_report_scaffold.py --tickers NVDA,AMD --out research/watchlists/run-small.md
```

**One-command sleeve refresh** (snapshot → rubric → universe valuation + rank → shortlist → core valuation → embeds + `watchlist.example.json` + patch `SINGLE_SCREEN_REPORT.html` when DCF CSV exists):

```bash
./scripts/refresh_watchlists.sh
```

The script ends with **`scripts/fi_verify_watchlist_refresh.py`** (non-zero exit if core tickers, enriched fields, or the embedded shortlist table are out of sync). Optional strict Finnhub coverage: `python scripts/fi_verify_watchlist_refresh.py --strict-market-context`.

### Agent protocol: “update the watchlist / shortlist / dashboard / sleeve snapshot”

Follow **Dashboard & document playbook** above—including **market context** and **Full refresh + verifier pass** when the user asks for a **full refresh + verifier**. In short: do **not** ask the user to run shell commands; ensure **`FINNHUB_API_KEY`** in **`.env`** when doing a full refresh; run **`./scripts/refresh_watchlists.sh`** from repo root (network; `.venv` if present); fix failures and re-run until **`fi_verify_watchlist_refresh.py`** passes; report OK + WARNs + paths + Finnhub status. **PDF** only if asked (`./scripts/html_to_pdf.sh`).

**Offline PDF** of the single-screen report (Chrome headless; HTML includes print layout). Writes **`docs/SINGLE_SCREEN_REPORT.pdf`**:

```bash
./scripts/html_to_pdf.sh
```

Manual steps equivalent to the script:

```bash
python scripts/fi_snapshot.py --manifest research/watchlists/universe_manifest.csv --csv research/watchlists/rubric_universe.csv --md research/watchlists/rubric_universe.md
python scripts/fi_universe_html_rows.py --manifest research/watchlists/universe_manifest.csv --csv research/watchlists/rubric_universe.csv > research/watchlists/_universe_table_rows.inc.html
python scripts/fi_snapshot_html_rows.py --manifest research/watchlists/universe_manifest.csv --csv research/watchlists/rubric_universe.csv > research/watchlists/_snapshot_table_rows.inc.html
python scripts/fi_rubric_html_rows.py --manifest research/watchlists/universe_manifest.csv --scores research/watchlists/rubric_scores.csv > research/watchlists/_rubric_table_rows.inc.html
python scripts/fi_export_watchlist_example.py
python scripts/fi_embed_single_screen.py
```

**Tier 0 sentiment** over all manifest tickers:

```bash
python scripts/fi_mentions.py --manifest research/watchlists/universe_manifest.csv --text-file forum_paste.txt --csv research/watchlists/mentions.csv
```

**Watchlist UI:** open `watchlist-ui/index.html` in a browser (double-click), use **Load JSON** with `watchlist-ui/watchlist.example.json` (70 rows seeded from the manifest), edit notes, **Export JSON** into `research/watchlists/`.

## Rules

Add path-scoped rules under `.claude/rules/` if you introduce code (e.g. Python in `scripts/`).
