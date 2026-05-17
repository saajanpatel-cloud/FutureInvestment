#!/usr/bin/env python3
"""
Post-refresh sanity checks for core shortlist + SINGLE_SCREEN embed.

Exit 0 if required artifacts and fields look consistent; non-zero on hard failures.
Warnings (Finnhub context CSV gaps) go to stderr and do not fail unless --strict-market-context.

Run from repo root, typically after ./scripts/refresh_watchlists.sh
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
ADV_PACKS = W / "adversarial_packs.json"
UI = ROOT / "watchlist-ui"
CORE_JSON = UI / "core-shortlist.json"
CORE_TXT = W / "report_core_tickers.txt"
HTML = W / "SINGLE_SCREEN_REPORT.html"
MAN = W / "universe_manifest.csv"
ERN = W / "earnings_data.csv"
RUB = W / "rubric_scores.csv"
FH_CSV = W / "finnhub_context.csv"
EXAMPLE = UI / "watchlist.example.json"
DIM_COLS = ("growth", "margins", "balance_sheet", "durability", "tail_risks", "valuation")
PLACEHOLDER_NOTE = "Placeholder rubric"

MIN_WHY = 40
MIN_KILL = 25
PLACEHOLDER_MARKERS = (
    "No market context row yet",
    "No Finnhub context — run fi_finnhub_context.py",
    "FINNHUB_API_KEY not configured",
)


def load_core_tickers_txt(path: Path) -> list[str]:
    out: list[str] = []
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s.upper())
    return out


def proposed_shares_row_count(html: str) -> int:
    """Count data rows in the print shortlist table (class proposed-shares print-table-rubric)."""
    m = re.search(
        r'<table class="proposed-shares print-table-rubric">.*?</table>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return -1
    block = m.group(0)
    tbody = re.search(r"<tbody>(.*?)</tbody>", block, flags=re.DOTALL | re.IGNORECASE)
    if not tbody:
        return 0
    return len(re.findall(r"<tr\b", tbody.group(1), flags=re.IGNORECASE))


def decide_matrix_row_count(html: str) -> int:
    m = re.search(
        r'<table class="decide-matrix print-table-rubric">.*?</table>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return -1
    block = m.group(0)
    tbody = re.search(r"<tbody>(.*?)</tbody>", block, flags=re.DOTALL | re.IGNORECASE)
    if not tbody:
        return 0
    return len(re.findall(r"<tr\b", tbody.group(1), flags=re.IGNORECASE))


def scenario_assumption_tickers(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    with path.open(encoding="utf-8", newline="") as f:
        return {(r.get("ticker") or "").strip().upper() for r in csv.DictReader(f) if (r.get("ticker") or "").strip()}


def table_ticker_set(html: str, table_pattern: str) -> set[str]:
    m = re.search(table_pattern, html, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        return set()
    block = m.group(0)
    return {x.upper() for x in re.findall(r"<strong>([A-Z0-9.\-]+)</strong>", block)}


def scenarios_js_keys(html: str) -> set[str]:
    m = re.search(r"var SCENARIOS\s*=\s*\{([\s\S]*?)\n  \};", html)
    if not m:
        return set()
    return set(re.findall(r'\n\s*"([A-Z0-9.\-]+)":', m.group(1)))


def meta_js_keys(html: str) -> set[str]:
    block = html
    if "FI_VALUE_JS_START" in html:
        m = re.search(
            r"/\* FI_VALUE_JS_START \*/[\s\S]*?var META\s*=\s*\{([\s\S]*?)\n  \};",
            html,
        )
        if m:
            block = m.group(1)
    else:
        m = re.search(r"var META\s*=\s*\{([\s\S]*?)\n  \};", html)
        if m:
            block = m.group(1)
        else:
            return set()
    return set(re.findall(r'\n\s*"([A-Z0-9.\-]+)":', block))


def manifest_tickers(path: Path) -> list[str]:
    if not path.is_file():
        return []
    out: list[str] = []
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = (r.get("ticker") or "").strip().upper()
            if t:
                out.append(t)
    return out


def check_rubric_coverage() -> tuple[list[str], list[str]]:
    """Hard failures and warnings for earnings + rubric grid."""
    errors: list[str] = []
    warns: list[str] = []
    manifest = manifest_tickers(MAN)
    if not manifest:
        errors.append(f"No tickers in {MAN.name}")
        return errors, warns

    earn_set: set[str] = set()
    if ERN.is_file():
        with ERN.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                t = (r.get("ticker") or "").strip().upper()
                if t and not (r.get("error") or "").strip():
                    earn_set.add(t)
    missing_earn = [t for t in manifest if t not in earn_set]
    if missing_earn:
        errors.append(
            f"earnings_data.csv missing {len(missing_earn)}/{len(manifest)} manifest tickers "
            f"(e.g. {', '.join(missing_earn[:8])})"
        )

    rub_by: dict[str, dict[str, str]] = {}
    if RUB.is_file():
        with RUB.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                t = (r.get("ticker") or "").strip().upper()
                if t:
                    rub_by[t] = r

    for t in manifest:
        row = rub_by.get(t)
        if not row:
            errors.append(f"rubric_scores.csv missing row for {t}")
            continue
        note = (row.get("note") or "").strip()
        if PLACEHOLDER_NOTE in note or not note:
            errors.append(f"{t}: rubric note still placeholder or empty")
        for c in DIM_COLS:
            v = (row.get(c) or "").strip()
            if not v.isdigit() or not (1 <= int(v) <= 5):
                errors.append(f"{t}: invalid rubric dim {c}={v!r}")

    return errors, warns


def node_check_value_js(html: str) -> str | None:
    m = re.search(
        r"/\* FI_VALUE_JS_START \*/([\s\S]*?)/\* FI_VALUE_JS_END \*/",
        html,
    )
    if not m:
        return "FI_VALUE_JS_START/END block missing in SINGLE_SCREEN_REPORT.html"
    snippet = "(function(){\n" + m.group(1) + "\n})();\n"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tf:
        tf.write(snippet)
        path = tf.name
    try:
        proc = subprocess.run(
            ["node", "--check", path],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return None
    finally:
        Path(path).unlink(missing_ok=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "node --check failed").strip()
        return f"Value JS syntax error (node --check): {err[:400]}"
    return None


def growth_review_warns(items: list[dict], rub_by: dict[str, dict[str, str]]) -> list[str]:
    warns: list[str] = []
    for it in items:
        t = (it.get("ticker") or "").strip().upper()
        if not t:
            continue
        g = (rub_by.get(t, {}).get("growth") or "").strip()
        if g != "1":
            continue
        memo = (it.get("selection_memo") or {}) if isinstance(it.get("selection_memo"), dict) else {}
        if memo.get("exception"):
            continue
        sw = (it.get("why_this_name") or "").lower()
        if "tier 3" in sw or "weak scorecard" in sw:
            warns.append(
                f"{t}: core shortlist has Growth=1 with weak tier signal — quarterly swap review "
                "(see CLAUDE.md growth policy)"
            )
    return warns


def finnhub_context_tickers(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    keys = {"ticker", "symbol", "TICKER"}
    out: set[str] = set()
    with path.open(encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        if not r.fieldnames:
            return set()
        col = next((c for c in r.fieldnames if c in keys or c.lower() == "ticker"), r.fieldnames[0])
        for row in r:
            t = (row.get(col) or "").strip().upper()
            if t:
                out.add(t)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--strict-market-context",
        action="store_true",
        help="Fail if any core ticker is missing from finnhub_context.csv",
    )
    ap.add_argument(
        "--strict-sentiment",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = ap.parse_args()
    strict_ctx = args.strict_market_context or args.strict_sentiment
    errors: list[str] = []
    warns: list[str] = []

    try:
        from fi_yahoo import ping as yahoo_ping

        yp = yahoo_ping()
        if yp.ok:
            print(f"OK: Yahoo Finance (yfinance {yp.version}) probe {yp.probe_ticker}")
        else:
            warns.append(f"Yahoo Finance unreachable: {yp.error}")
    except Exception as exc:
        warns.append(f"Yahoo Finance check skipped: {exc}")

    if not CORE_JSON.is_file():
        errors.append(f"Missing {CORE_JSON.relative_to(ROOT)}")
        print("\n".join(errors), file=sys.stderr)
        return 2

    data = json.loads(CORE_JSON.read_text(encoding="utf-8"))
    items = data.get("items") or []
    tickers_json = [(it.get("ticker") or "").strip().upper() for it in items]
    tickers_json = [t for t in tickers_json if t]

    memo = data.get("selection_memo") or {}
    if memo.get("composite_five_signal") or memo.get("valuation_first"):
        rankp = W / "universe_valuation_rank.csv"
        compp = W / "universe_composite_rank.csv"
        suru = W / "scenario_results_universe.csv"
        if rankp.is_file() and suru.is_file():
            if suru.stat().st_mtime + 15 < rankp.stat().st_mtime:
                warns.append(
                    "scenario_results_universe.csv is older than universe_valuation_rank.csv — "
                    "re-run fi_scenarios on scenario_assumptions_universe.csv before trusting rank."
                )
        if memo.get("composite_five_signal") and not compp.is_file():
            warns.append("composite_five_signal memo but missing universe_composite_rank.csv")
        elif compp.is_file() and suru.is_file():
            if suru.stat().st_mtime + 15 < compp.stat().st_mtime:
                warns.append(
                    "universe CSVs older than universe_composite_rank.csv — re-run full universe pass."
                )

    txt_list = load_core_tickers_txt(CORE_TXT)
    set_txt = set(txt_list)
    set_js = set(tickers_json)

    if set_txt != set_js:
        errors.append(
            f"Ticker mismatch: report_core_tickers.txt ({sorted(set_txt - set_js) or len(set_txt)} names) "
            f"vs core-shortlist.json ({sorted(set_js - set_txt) or len(set_js)} names). "
            f"symmetric diff: txt-only={sorted(set_txt - set_js)} json-only={sorted(set_js - set_txt)}"
        )

    n_meta = data.get("shortlist_n")
    if n_meta is not None and int(n_meta) != len(tickers_json):
        errors.append(f"shortlist_n={n_meta} but items has {len(tickers_json)} tickers")

    missing_fields: list[str] = []
    context_placeholder = 0
    for it in items:
        t = (it.get("ticker") or "").strip().upper()
        if not t:
            continue
        why = (it.get("why_this_name") or "").strip()
        kill = (it.get("key_risk_kill") or "").strip()
        ctx = (it.get("market_context") or it.get("social_sentiment") or "").strip()
        if len(why) < MIN_WHY:
            missing_fields.append(f"{t}: why_this_name too short ({len(why)} chars)")
        if len(kill) < MIN_KILL:
            missing_fields.append(f"{t}: key_risk_kill too short ({len(kill)} chars)")
        if not ctx:
            missing_fields.append(f"{t}: market_context empty")
        elif any(m in ctx for m in PLACEHOLDER_MARKERS):
            context_placeholder += 1
        for field in ("research_thesis", "qual_bull", "qual_bear"):
            val = (it.get(field) or "").strip()
            if not val or val == "—":
                missing_fields.append(f"{t}: {field} empty")
        if why and "·" not in why and len(why) > 80:
            warns.append(f"{t}: why_this_name has no bullet separator (expected middle-dot narratives)")

    if missing_fields:
        errors.extend(missing_fields[:25])
        if len(missing_fields) > 25:
            errors.append(f"... and {len(missing_fields) - 25} more field issues")

    if ADV_PACKS.is_file():
        try:
            adv_doc = json.loads(ADV_PACKS.read_text(encoding="utf-8"))
            adv_packs = adv_doc.get("packs") if isinstance(adv_doc, dict) else {}
            if not isinstance(adv_packs, dict):
                adv_packs = {}
        except json.JSONDecodeError:
            adv_packs = {}
            warns.append(f"Could not parse {ADV_PACKS.name}")
        for t in set_js:
            p = adv_packs.get(t) if isinstance(adv_packs.get(t), dict) else None
            if not p or not p.get("workflow_e_complete"):
                warns.append(
                    f"{t}: missing completed Workflow E pack in {ADV_PACKS.name} "
                    "(re-run refresh without FI_SKIP_ADVERSARIAL=1)"
                )
        for it in items:
            t = (it.get("ticker") or "").strip().upper()
            prem = (it.get("research_premortem") or "").strip()
            if t in set_js and "[Auto stub]" in prem:
                warns.append(
                    f"{t}: research_premortem still auto-stub — adversarial pack may not be merged (re-run enrich)"
                )
    else:
        warns.append(
            f"Missing {ADV_PACKS.name} — run refresh without FI_SKIP_ADVERSARIAL=1 for Workflow E packs"
        )

    fh_cov = finnhub_context_tickers(FH_CSV)
    if fh_cov:
        for t in set_js:
            if t not in fh_cov:
                msg = f"Ticker {t} missing from {FH_CSV.name} (Finnhub context scan incomplete)"
                if strict_ctx:
                    errors.append(msg)
                else:
                    warns.append(msg)
    else:
        warns.append(f"No readable tickers in {FH_CSV.name} — Finnhub context CSV absent or empty")

    if context_placeholder:
        warns.append(
            f"{context_placeholder} core row(s) still have placeholder market-context text. "
            "Set FINNHUB_API_KEY in .env and re-run fi_finnhub_context.py / refresh."
        )

    html_rows = -1
    if not HTML.is_file():
        errors.append(f"Missing {HTML.relative_to(ROOT)}")
    else:
        html = HTML.read_text(encoding="utf-8", errors="replace")
        html_rows = proposed_shares_row_count(html)
        if html_rows < 0:
            errors.append("SINGLE_SCREEN_REPORT.html: could not find proposed-shares print table")
        elif html_rows != len(tickers_json):
            errors.append(
                f"SINGLE_SCREEN shortlist table has {html_rows} data rows; core-shortlist has {len(tickers_json)} — re-run fi_embed_shortlist_proposed.py"
            )
        core_mtime = CORE_JSON.stat().st_mtime
        html_mtime = HTML.stat().st_mtime
        if html_mtime + 2 < core_mtime:
            errors.append(
                "SINGLE_SCREEN_REPORT.html looks older than core-shortlist.json — embed step may not have run after enrich"
            )
        if html_rows >= 0 and tickers_json:
            t_low = min(5, len(tickers_json))
            for t in tickers_json[:t_low]:
                if f"<strong>{t}</strong>" not in html:
                    errors.append(
                        f"SINGLE_SCREEN shortlist table missing <strong>{t}</strong> — embed out of sync with core-shortlist.json"
                    )
                    break

        dm_rows = decide_matrix_row_count(html)
        if dm_rows >= 0 and dm_rows != len(tickers_json):
            errors.append(
                f"SINGLE_SCREEN Decide matrix has {dm_rows} data rows; core-shortlist has {len(tickers_json)} "
                "— re-run fi_embed_decide_matrix.py"
            )

        scen_path = W / "scenario_assumptions.csv"
        scen_set = scenario_assumption_tickers(scen_path)
        if scen_set and set_js != scen_set:
            errors.append(
                "scenario_assumptions.csv ticker set does not match report_core_tickers / core-shortlist.json — "
                "run python3 scripts/fi_sync_scenario_assumptions_from_core.py (then fi_scenarios / fi_monte_carlo / "
                "fi_risk_metrics as needed). "
                f"scenario_only={sorted(scen_set - set_js)[:8]} core_only={sorted(set_js - scen_set)[:8]}"
            )

        val_scen = table_ticker_set(
            html,
            r'<table[^>]*scenario-model-table[^>]*>[\s\S]*?</table>',
        )
        if val_scen:
            missing_val = set_js - val_scen
            extra_val = val_scen - set_js
            if missing_val:
                errors.append(
                    f"Value scenario table missing core tickers: {sorted(missing_val)[:6]} — "
                    "re-run fi_embed_value_tables.py"
                )
            for t in sorted(extra_val)[:5]:
                warns.append(f"Value scenario table has non-core ticker {t} (stale row?)")

        js_keys = scenarios_js_keys(html)
        if js_keys:
            missing_js = set_js - js_keys
            extra_js = js_keys - set_js
            if missing_js:
                errors.append(
                    f"SCENARIOS JS missing core tickers: {sorted(missing_js)[:6]} — "
                    "re-run fi_embed_value_js.py"
                )
            for t in sorted(extra_js)[:5]:
                warns.append(f"SCENARIOS JS has non-core ticker {t}")

        meta_keys = meta_js_keys(html)
        if meta_keys and meta_keys != js_keys and js_keys:
            warns.append("META and SCENARIOS key sets differ — re-run fi_embed_value_js.py")

        if "<!-- FI_SHORTLIST_CHANGELOG_START -->" not in html:
            warns.append(
                "Shortlist changelog section missing — re-run fi_embed_shortlist_changelog.py"
            )

        if "FI_VALUE_JS_START" not in html and "FI_VALUE_JS_END" not in html and not js_keys:
            warns.append(
                "Value deep-dive JS not regenerated — run fi_embed_value_js.py after refresh"
            )

        if "FINNHUB_BY_TICKER" not in html:
            warns.append("FINNHUB_BY_TICKER missing — re-run fi_embed_value_js.py after fi_finnhub_context.py")
        elif "var CORE_TICKERS" not in html:
            warns.append("CORE_TICKERS missing — re-run fi_embed_value_js.py")
        if 'id="monitor"' not in html and 'id="stock-deep-dive"' in html:
            errors.append("Monitor section still id=stock-deep-dive — re-run fi_embed_deep_dive_layout.py")
        if "<!-- FI_MARKET_CONTEXT_EMBED_START -->" in html:
            warns.append(
                "Legacy aggregate Finnhub embed still present — re-run fi_embed_single_screen.py"
            )

    if not EXAMPLE.is_file():
        warns.append(f"Missing {EXAMPLE.relative_to(ROOT)} (copy step from refresh?)")

    cov_err, cov_warn = check_rubric_coverage()
    errors.extend(cov_err)
    warns.extend(cov_warn)

    if HTML.is_file():
        js_err = node_check_value_js(HTML.read_text(encoding="utf-8", errors="replace"))
        if js_err:
            errors.append(js_err)

    rub_by: dict[str, dict[str, str]] = {}
    if RUB.is_file():
        with RUB.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                t = (r.get("ticker") or "").strip().upper()
                if t:
                    rub_by[t] = r
    warns.extend(growth_review_warns(items, rub_by))

    for w in warns:
        print(f"WARN: {w}", file=sys.stderr)
    if errors:
        print("VERIFY FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1

    print(
        f"OK: verify_watchlist_refresh — {len(tickers_json)} core names, "
        f"proposed-shares rows={html_rows if html_rows >= 0 else '?'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
