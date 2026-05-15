#!/usr/bin/env python3
"""
Patch SINGLE_SCREEN_REPORT.html qualitative bull/bear/watch table for core shortlist tickers.

Reads qual_bull, qual_bear, qual_watch from watchlist-ui/core-shortlist.json.
Run via refresh_watchlists.sh after fi_enrich_core_shortlist.py.

Not investment advice.
"""
from __future__ import annotations

import csv
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "research" / "watchlists" / "SINGLE_SCREEN_REPORT.html"
CORE_TXT = ROOT / "research" / "watchlists" / "report_core_tickers.txt"
CORE_JSON = ROOT / "watchlist-ui" / "core-shortlist.json"
MAN = ROOT / "research" / "watchlists" / "universe_manifest.csv"
RU = ROOT / "research" / "watchlists" / "rubric_universe.csv"

STALE_NOTE = (
    '<p class="muted" style="margin-top:0.5rem;">'
    "<strong>Live shortlist.</strong> Rows match the Shortlist / Decide core set and refresh on each full pipeline run. "
    "Use this table as the source of truth.</p>"
)


def load_core_tickers() -> list[str]:
    out: list[str] = []
    for line in CORE_TXT.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s.upper())
    return out


def load_manifest() -> dict[str, dict[str, str]]:
    by_t: dict[str, dict[str, str]] = {}
    with MAN.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = (r.get("ticker") or "").strip().upper()
            if t:
                by_t[t] = r
    return by_t


def load_short_names() -> dict[str, str]:
    if not RU.is_file():
        return {}
    with RU.open(encoding="utf-8", newline="") as f:
        return {
            (r.get("ticker") or "").strip().upper(): (r.get("short_name") or "").strip()
            for r in csv.DictReader(f)
            if (r.get("ticker") or "").strip()
        }


def sort_tickers_by_theme_then_symbol(
    tickers: list[str], man: dict[str, dict[str, str]]
) -> list[str]:
    def key(sym: str) -> tuple[str, str]:
        row = man.get(sym, {})
        theme = (row.get("theme_label") or row.get("theme_slug") or "").strip().lower()
        return (theme, sym.upper())

    return sorted(tickers, key=key)


def load_items() -> dict[str, dict]:
    if not CORE_JSON.is_file():
        return {}
    doc = json.loads(CORE_JSON.read_text(encoding="utf-8"))
    return {
        (it.get("ticker") or "").strip().upper(): it
        for it in (doc.get("items") or [])
        if it.get("ticker")
    }


def build_tbody(
    tickers: list[str],
    items: dict[str, dict],
    man: dict[str, dict[str, str]],
    names: dict[str, str],
) -> str:
    rows: list[str] = []
    for t in tickers:
        it = items.get(t, {})
        row_m = man.get(t, {})
        theme = (row_m.get("theme_label") or row_m.get("theme_slug") or "—").strip()
        company = (names.get(t) or t).strip()
        if len(company) > 56:
            company = company[:53] + "…"
        bull = (it.get("qual_bull") or "—").strip()
        bear = (it.get("qual_bear") or "—").strip()
        watch = (it.get("qual_watch") or "—").strip()
        if len(bull) > 220:
            bull = bull[:217] + "…"
        if len(bear) > 220:
            bear = bear[:217] + "…"
        if len(watch) > 220:
            watch = watch[:217] + "…"
        rows.append(
            f"            <tr><td>{html.escape(t)}</td>"
            f"<td>{html.escape(theme)}</td>"
            f"<td>{html.escape(company)}</td>"
            f"<td>{html.escape(bull)}</td>"
            f"<td>{html.escape(bear)}</td>"
            f"<td>{html.escape(watch)}</td></tr>"
        )
    return "\n".join(rows) + "\n"


TABLE_HEAD = (
    '<table class="print-value-qual-table print-table-rubric">\n'
    "          <thead><tr><th>Ticker</th><th>Theme</th><th>Company</th>"
    "<th>Bull</th><th>Bear</th><th>Watch</th></tr></thead>\n"
    "          <tbody>\n"
)


def patch_qual_table(doc: str, tbody: str) -> str:
    pat = re.compile(
        r'(<h3 class="print-research-matrix-title">Qualitative bull / bear</h3>\s*)'
        r"(?:<p class=\"muted\"[^>]*>[\s\S]*?</p>\s*)?"
        r'<table class="print-value-qual-table print-table-rubric">\s*'
        r"<thead>[\s\S]*?</thead>\s*<tbody>\s*\n"
        r"[\s\S]*?"
        r"(\s*</tbody>\s*\n\s*</table>)",
        re.MULTILINE,
    )
    m = pat.search(doc)
    if not m:
        print("Could not find print-value-qual-table", file=sys.stderr)
        sys.exit(2)
    return pat.sub(r"\1" + STALE_NOTE + "\n        " + TABLE_HEAD + tbody + r"\2", doc, count=1)


def main() -> int:
    man = load_manifest()
    tickers = sort_tickers_by_theme_then_symbol(load_core_tickers(), man)
    if not tickers:
        print(f"No tickers in {CORE_TXT}", file=sys.stderr)
        return 2
    items = load_items()
    names = load_short_names()
    tbody = build_tbody(tickers, items, man, names)
    text = HTML.read_text(encoding="utf-8")
    text = patch_qual_table(text, tbody)
    HTML.write_text(text, encoding="utf-8")
    print(f"Patched qualitative bull/bear table ({len(tickers)} rows) → {HTML}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
