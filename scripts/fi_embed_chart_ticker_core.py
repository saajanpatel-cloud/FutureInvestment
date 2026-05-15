#!/usr/bin/env python3
"""
Replace Monitor section <select id="chart-ticker"> options with the Decide core
shortlist and TradingView-compatible symbols (from yfinance exchange in
rubric_universe.csv).

Run after fi_embed_single_screen so the scaffold exists. Invoked from
refresh_watchlists.sh.

Not investment advice.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from fi_embed_core import HTML, ROOT, load_core_tickers

W = ROOT / "research" / "watchlists"
RU = W / "rubric_universe.csv"

# Yahoo / yfinance `exchange` → TradingView market prefix (equities)
YF_TO_TV = {
    "NMS": "NASDAQ",
    "NYQ": "NYSE",
    "NGM": "NASDAQ",
    "NCM": "NASDAQ",
    "PCX": "NYSE",
    "NYE": "NYSE",
    "ASE": "NYSE",
    "CPH": "OMXCOP",
}


def load_exchanges() -> dict[str, str]:
    if not RU.is_file():
        return {}
    with RU.open(encoding="utf-8", newline="") as f:
        return {
            (r.get("ticker") or "").strip().upper(): (r.get("exchange") or "").strip().upper()
            for r in csv.DictReader(f)
            if (r.get("ticker") or "").strip()
        }


def tv_symbol(ticker: str, ex_by: dict[str, str]) -> str:
    t = ticker.strip().upper()
    yf = ex_by.get(t, "")
    market = YF_TO_TV.get(yf, "NASDAQ")
    if t.endswith(".CO"):
        return f"{market}:{t[:-3]}"
    if "." in t:
        return f"{market}:{t.split('.')[0]}"
    return f"{market}:{t}"


def main() -> int:
    tickers = load_core_tickers()
    if not tickers:
        print("No core tickers", file=sys.stderr)
        return 2
    ex_by = load_exchanges()
    opts = "\n".join(
        f'          <option value="{tv_symbol(t, ex_by)}">{t}</option>' for t in tickers
    )
    doc = HTML.read_text(encoding="utf-8")
    pat = re.compile(
        r'(<select id="chart-ticker"[^>]*>\s*\n)[\s\S]*?'
        r'(\n\s*</select>\s*\n\s*Interval:\s*<select id="chart-interval")',
        re.IGNORECASE,
    )
    m = pat.search(doc)
    if not m:
        print("Could not find chart-ticker select block", file=sys.stderr)
        return 2
    new_doc = pat.sub(r"\1" + opts + r"\2", doc, count=1)
    if new_doc == doc:
        print("No substitution made", file=sys.stderr)
        return 1
    HTML.write_text(new_doc, encoding="utf-8")
    print(f"Patched chart-ticker options ({len(tickers)} tickers) → {HTML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
