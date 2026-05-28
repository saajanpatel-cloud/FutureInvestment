#!/usr/bin/env python3
"""
Append portfolio-only tickers to core-shortlist.json before enrich.

Composite shortlist items are untouched; portfolio names get source=portfolio.
Not investment advice.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fi_portfolio_tickers import load_portfolio, load_shortlist

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "watchlist-ui"
CORE_JSON = UI / "core-shortlist.json"
W = ROOT / "research" / "watchlists"
MAN = W / "universe_manifest.csv"


def load_manifest() -> dict[str, dict[str, str]]:
    import csv

    out: dict[str, dict[str, str]] = {}
    if not MAN.is_file():
        return out
    with MAN.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = (r.get("ticker") or "").strip().upper()
            if t:
                out[t] = r
    return out


def main() -> int:
    if not CORE_JSON.is_file():
        print(f"Missing {CORE_JSON}", file=sys.stderr)
        return 2
    doc = json.loads(CORE_JSON.read_text(encoding="utf-8"))
    items = doc.get("items") or []
    existing = {(it.get("ticker") or "").strip().upper() for it in items if it.get("ticker")}
    sl = set(load_shortlist())
    man = load_manifest()
    added = 0
    for t in load_portfolio():
        if t in existing:
            continue
        m = man.get(t, {})
        items.append(
            {
                "ticker": t,
                "source": "portfolio",
                "conviction_tier": None,
                "theme_slug": (m.get("theme_slug") or "").strip(),
                "theme_label": (m.get("theme_label") or "").strip(),
                "linkage_one_liner": (m.get("linkage_one_liner") or "").strip(),
            }
        )
        existing.add(t)
        added += 1
    doc["items"] = items
    doc["portfolio_merged_n"] = added
    doc["decide_union_n"] = len(items)
    # shortlist_n stays the composite count from fi_select_shortlist_growth.py
    CORE_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Merged {added} portfolio-only items into core-shortlist ({len(items)} total)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
