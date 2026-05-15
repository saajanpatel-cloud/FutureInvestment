#!/usr/bin/env python3
"""Shared helpers for SINGLE_SCREEN_REPORT.html embed scripts."""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
HTML = W / "SINGLE_SCREEN_REPORT.html"
CORE_TXT = W / "report_core_tickers.txt"
CORE_JSON = ROOT / "watchlist-ui" / "core-shortlist.json"
PRIOR_JSON = W / "_shortlist_prior.json"


def load_core_tickers() -> list[str]:
    out: list[str] = []
    if not CORE_TXT.is_file():
        return out
    for line in CORE_TXT.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s.upper())
    return out


def load_csv_index(path: Path, key: str = "ticker") -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {(r.get(key) or "").strip().upper(): r for r in csv.DictReader(f) if (r.get(key) or "").strip()}


def patch_table_tbody(doc: str, table_pattern: str, tbody: str) -> str:
    pat = re.compile(
        table_pattern + r"[\s\S]*?<tbody>\s*\n" + r"[\s\S]*?" + r"(\s*</tbody>)",
        re.MULTILINE | re.IGNORECASE,
    )
    m = pat.search(doc)
    if not m:
        return doc
    return pat.sub(lambda m: pat.pattern[:0] + table_pattern + doc[pat.search(doc).start() :], doc, count=1)


def replace_between(doc: str, start: str, end: str, inner: str) -> str:
    pat = re.compile(re.escape(start) + r"[\s\S]*?" + re.escape(end))
    if not pat.search(doc):
        return doc
    return pat.sub(start + "\n" + inner + "\n" + end, doc, count=1)


def patch_tbody_after_marker(doc: str, marker_id: str, tbody: str) -> str:
    """Replace first <tbody> in section following an id= marker (e.g. risk-metrics)."""
    idx = doc.find(f'id="{marker_id}"')
    if idx < 0:
        return doc
    sub = doc[idx:]
    pat = re.compile(r"(<tbody>\s*\n)([\s\S]*?)(\s*</tbody>)", re.MULTILINE)
    m = pat.search(sub)
    if not m:
        return doc
    new_sub = sub[: m.start()] + m.group(1) + tbody + m.group(3) + sub[m.end() :]
    return doc[:idx] + new_sub


RISK_DEF_TBODY = """      <tr><td>Beta</td><td>Sensitivity vs S&amp;P 500 over ~2y</td></tr>
      <tr><td>Ann. vol</td><td>Annualised daily return volatility</td></tr>
      <tr><td>Max DD</td><td>Peak-to-trough drawdown in window</td></tr>
      <tr><td>1Y return</td><td>Total return over last 12 months</td></tr>
      <tr><td>Sharpe</td><td>Risk-adjusted return (excess return / vol)</td></tr>
      <tr><td>SPY corr</td><td>Correlation with SPY daily returns</td></tr>
"""


def patch_tbody_scroll_data_after_marker(
    doc: str,
    marker_id: str,
    tbody: str,
    *,
    header_hint: str,
    end_marker_id: str | None = None,
) -> str:
    """Replace tbody in scroll data table after marker (section bounded by next id)."""
    idx = doc.find(f'id="{marker_id}"')
    if idx < 0:
        return doc
    end = len(doc)
    if end_marker_id:
        e = doc.find(f'id="{end_marker_id}"', idx + 1)
        if e > idx:
            end = e
    sub = doc[idx:end]
    scroll_pat = re.compile(
        r'(<div class="scroll">\s*\n\s*<table class="print-table-rubric">'
        r"[\s\S]*?"
        + re.escape(header_hint)
        + r"[\s\S]*?</thead>\s*\n\s*<tbody>\s*\n)"
        r"[\s\S]*?"
        r"(\s*</tbody>)",
        re.MULTILINE | re.IGNORECASE,
    )
    m = scroll_pat.search(sub)
    if not m:
        return doc
    new_sub = sub[: m.start()] + m.group(1) + tbody + m.group(2) + sub[m.end() :]
    return doc[:idx] + new_sub + doc[end:]


def restore_print_risk_def_table(doc: str) -> str:
    """Restore print-only risk definition tbody if corrupted by legacy embed."""
    pat = re.compile(
        r'(<table class="print-risk-def-table print-table-rubric">\s*'
        r"<thead><tr><th>Field</th><th>Meaning \(2y window\)</th></tr></thead>\s*\n)"
        r"<tbody>\s*\n([\s\S]*?)(\s*</tbody>)",
        re.MULTILINE,
    )
    m = pat.search(doc)
    if not m:
        return doc
    body = m.group(2)
    if body.strip().startswith("<tr><td>Beta</td>") and "<strong>" not in body:
        return doc
    return doc[: m.start()] + m.group(1) + "<tbody>\n" + RISK_DEF_TBODY + m.group(3) + doc[m.end() :]


def patch_tbody_by_class(doc: str, table_class: str, tbody: str) -> str:
    pat = re.compile(
        rf'(<table[^>]*\bclass="[^"]*\b{re.escape(table_class)}\b[^"]*"[^>]*>'
        rf"[\s\S]*?<tbody>\s*\n)"
        rf"[\s\S]*?"
        rf"(\s*</tbody>)",
        re.MULTILINE | re.IGNORECASE,
    )
    if not pat.search(doc):
        return doc
    return pat.sub(r"\1" + tbody + r"\2", doc, count=1)


def fmt_price(v: float) -> str:
    if v >= 1000:
        return f"${v:,.0f}"
    return f"${v:,.2f}"


def fmt_pct(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.0f}%"
