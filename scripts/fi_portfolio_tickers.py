#!/usr/bin/env python3
"""Portfolio holdings vs composite shortlist — single source for decide union. Not investment advice."""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
PORTFOLIO_CSV = W / "portfolio_holdings.csv"
CORE_TXT = W / "report_core_tickers.txt"
UNION_TXT = W / "report_decide_union.txt"


def load_shortlist() -> list[str]:
    out: list[str] = []
    if not CORE_TXT.is_file():
        return out
    for line in CORE_TXT.read_text(encoding="utf-8").splitlines():
        s = line.strip().upper()
        if s and not s.startswith("#"):
            out.append(s)
    return out


def load_portfolio() -> list[str]:
    if not PORTFOLIO_CSV.is_file():
        return []
    out: list[str] = []
    with PORTFOLIO_CSV.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = (r.get("ticker") or "").strip().upper()
            if t and t != "PRIVATE":
                out.append(t)
    return out


def load_decide_union() -> list[str]:
    """Shortlist first, then portfolio-only names (stable order, deduped)."""
    shortlist = load_shortlist()
    seen = set(shortlist)
    union = list(shortlist)
    for t in load_portfolio():
        if t not in seen:
            union.append(t)
            seen.add(t)
    return union


def portfolio_only() -> list[str]:
    sl = set(load_shortlist())
    return [t for t in load_portfolio() if t not in sl]


def load_union_for_models() -> list[str]:
    """Alias for valuation / enrich / finnhub union."""
    return load_decide_union()


def write_union_file() -> Path:
    """Persist union list for finnhub and scenario sync."""
    tickers = load_decide_union()
    lines = ["# decide union — shortlist then portfolio-only", *tickers, ""]
    UNION_TXT.write_text("\n".join(lines), encoding="utf-8")
    return UNION_TXT


def load_decide_union_display_order() -> list[str]:
    import csv

    from fi_embed_shortlist_proposed import sort_tickers_by_theme_then_symbol

    man: dict[str, dict[str, str]] = {}
    man_path = W / "universe_manifest.csv"
    if man_path.is_file():
        with man_path.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                t = (r.get("ticker") or "").strip().upper()
                if t:
                    man[t] = r
    sl = load_shortlist()
    extra = portfolio_only()
    return sort_tickers_by_theme_then_symbol(sl, man) + sort_tickers_by_theme_then_symbol(extra, man)


if __name__ == "__main__":
    import sys

    p = write_union_file()
    u = load_decide_union()
    print(f"Wrote {len(u)} tickers → {p}", file=sys.stderr)
    sys.exit(0)
