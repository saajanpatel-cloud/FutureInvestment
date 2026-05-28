#!/usr/bin/env python3
"""
Strict audit: core shortlist tickers must appear in Value/Decide embed regions;
stale non-core tickers in those regions fail the refresh.

Run after all embed scripts in refresh_watchlists.sh.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from fi_embed_core import CORE_JSON, CORE_TXT, HTML, load_core_tickers

try:
    from fi_portfolio_tickers import PORTFOLIO_CSV, load_decide_union, load_shortlist
except ImportError:
    PORTFOLIO_CSV = None  # type: ignore
    load_decide_union = None  # type: ignore
    load_shortlist = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
COMPOSITE = W / "universe_composite_rank.csv"

# Historical sleeve names that must not appear in core-only tables unless on shortlist
STALE_WATCH = frozenset(
    {"NVDA", "AMAT", "VST", "ANET", "FTNT", "ETN", "IBM", "IONQ", "LLY", "NEE", "PANW", "QBTS", "ROK", "MU"}
)


def tbody_tickers(html: str, pattern: str) -> set[str]:
    m = re.search(pattern, html, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        return set()
    block = m.group(0)
    return {x.upper() for x in re.findall(r"<strong>([A-Z0-9.\-]+)</strong>", block)}


def js_object_keys(html: str, var_name: str) -> set[str]:
    m = re.search(rf"(?:const|var)\s+{var_name}\s*=\s*\{{", html)
    if not m:
        return set()
    start = m.end() - 1
    depth = 0
    for i in range(start, min(start + 500_000, len(html))):
        c = html[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                chunk = html[start : i + 1]
                return set(re.findall(r'"([A-Z0-9.\-]+)"\s*:', chunk))
    return set()


def dcf_detail_tickers(html: str) -> set[str]:
    section = html
    i = html.find('class="dcf-company-grids')
    if i >= 0:
        j = html.find("<h3 id=\"monte-carlo\">", i)
        if j < 0:
            j = html.find('id="monte-carlo"', i)
        section = html[i:j] if j > i else html[i : i + 200_000]
    return {
        m.group(1).upper()
        for m in re.finditer(
            r"<summary><strong>([A-Z0-9.\-]+)</strong>",
            section,
            flags=re.IGNORECASE,
        )
    }


def risk_scroll_tickers(html: str) -> set[str]:
    idx = html.find('id="risk-metrics"')
    if idx < 0:
        return set()
    sub = html[idx:]
    m = re.search(
        r'<div class="scroll">\s*\n\s*<table class="print-table-rubric">'
        r"[\s\S]*?<th>Beta</th>[\s\S]*?<tbody>([\s\S]*?)</tbody>",
        sub,
        flags=re.IGNORECASE,
    )
    if not m:
        return set()
    return {x.upper() for x in re.findall(r"<strong>([A-Z0-9.\-]+)</strong>", m.group(1))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    args = ap.parse_args()
    _ = args

    core = load_core_tickers()
    if PORTFOLIO_CSV and PORTFOLIO_CSV.is_file() and load_decide_union:
        union = load_decide_union()
        if union:
            core = union
    if not core:
        print("FAIL: no core tickers in report_core_tickers.txt", file=sys.stderr)
        return 2
    core_set = set(core)
    shortlist_set = set(load_shortlist()) if load_shortlist and PORTFOLIO_CSV and PORTFOLIO_CSV.is_file() else core_set
    html = HTML.read_text(encoding="utf-8")
    errors: list[str] = []
    warns: list[str] = []

    proposed = tbody_tickers(
        html,
        r'<table class="proposed-shares print-table-rubric">[\s\S]*?</table>',
    )
    scenario = tbody_tickers(
        html,
        r'<table[^>]*scenario-model-table[^>]*>[\s\S]*?</table>',
    )
    risk = risk_scroll_tickers(html)
    mc = tbody_tickers(
        html,
        r'id="monte-carlo"[\s\S]*?<div class="scroll">[\s\S]*?</table>',
    )
    dcf = dcf_detail_tickers(html)
    scen_js = js_object_keys(html, "SCENARIOS")
    risk_js = js_object_keys(html, "RISK")
    mc_js = js_object_keys(html, "MC")
    dcf_js = js_object_keys(html, "DCF")
    narr_js = js_object_keys(html, "NARRATIVE")

    checks = [
        ("proposed-shares", proposed),
        ("scenario table", scenario),
        ("risk scroll", risk),
        ("monte-carlo table", mc),
        ("DCF details", dcf),
        ("SCENARIOS js", scen_js),
        ("RISK js", risk_js),
        ("MC js", mc_js),
        ("DCF js", dcf_js),
        ("NARRATIVE js", narr_js),
    ]

    if "openDeepDive" not in html:
        errors.append("deep-dive: openDeepDive() not in report JS")
    if "dd-meta-banner" not in html:
        errors.append("deep-dive: freshness banner CSS missing")
    if "Quality movers" in html:
        errors.append("shortlist: Quality movers block still present")

    def _csv_tickers(name: str) -> set[str]:
        p = W / name
        if not p.is_file():
            return set()
        import csv

        with p.open(encoding="utf-8", newline="") as f:
            return {
                (r.get("ticker") or "").strip().upper()
                for r in csv.DictReader(f)
                if (r.get("ticker") or "").strip()
            }

    scen_have = _csv_tickers("scenario_results.csv")
    risk_have = _csv_tickers("risk_metrics.csv")
    mc_have = _csv_tickers("monte_carlo_results.csv")
    dcf_have = _csv_tickers("dcf_sensitivity.csv")

    for label, found in checks:
        if not found and label.endswith("js"):
            warns.append(f"{label}: object not found (embed may be skipped)")
            continue
        effective = shortlist_set if label == "proposed-shares" else core_set
        missing = effective - found
        if label == "scenario table" and scen_have:
            missing = missing & scen_have
        elif label == "risk scroll" and risk_have:
            missing = missing & risk_have
        elif label == "monte-carlo table" and mc_have:
            missing = missing & mc_have
        elif "SCENARIOS" in label and scen_have:
            missing = missing & scen_have
        elif "RISK" in label and risk_have:
            missing = missing & risk_have
        elif "MC" in label and mc_have:
            missing = missing & mc_have
        elif "DCF" in label and dcf_have:
            missing = missing & dcf_have
        if missing:
            errors.append(f"{label}: missing {sorted(missing)[:12]}")
        no_data = (effective - found) - missing
        if no_data and label.endswith("js"):
            warns.append(f"{label}: no model row for {sorted(no_data)[:8]}")
        stale = (found & STALE_WATCH) - core_set
        if stale:
            errors.append(f"{label}: stale non-core {sorted(stale)}")

    if COMPOSITE.is_file() and CORE_JSON.is_file():
        doc = json.loads(CORE_JSON.read_text(encoding="utf-8"))
        if not doc.get("selection_memo", {}).get("composite_five_signal"):
            warns.append("core-shortlist.json: composite_five_signal not set (legacy selection?)")

    for w in warns:
        print(f"WARN: {w}", file=sys.stderr)
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)

    if errors:
        return 1
    print(f"OK: report core sync — {len(core)} tickers in all Value/Decide embed regions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
