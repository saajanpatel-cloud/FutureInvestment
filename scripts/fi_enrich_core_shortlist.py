#!/usr/bin/env python3
"""
Populate dashboard-facing narrative fields on each `core-shortlist.json` item.

Run after `fi_select_shortlist_growth.py` and `fi_finnhub_context.py` refresh.
Typically invoked from `scripts/refresh_watchlists.sh`.

Not investment advice.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from fi_narrative import (
    format_kill,
    format_premortem_stub,
    format_qual_bull_bear_watch,
    format_research_glance,
    format_research_thesis,
    format_why,
)

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
UI = ROOT / "watchlist-ui"
CORE_JSON = UI / "core-shortlist.json"
RUB = W / "rubric_scores.csv"
MAN = W / "universe_manifest.csv"
ERN = W / "earnings_data.csv"
FH_CSV = W / "finnhub_context.csv"


def load_csv_map(path: Path, key: str) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    out: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            k = (r.get(key) or "").strip().upper()
            if k:
                out[k] = r
    return out


def format_market_context_row(fh: dict[str, str] | None) -> str:
    if fh:
        line = (fh.get("context_line") or "").strip()
        if line and line != "FINNHUB_API_KEY not configured.":
            return line
    return (
        "No Finnhub context — run fi_finnhub_context.py with FINNHUB_API_KEY in .env "
        "(see refresh_watchlists.sh)."
    )


def main() -> None:
    if not CORE_JSON.is_file():
        print(f"Missing {CORE_JSON}", file=sys.stderr)
        sys.exit(2)

    doc = json.loads(CORE_JSON.read_text(encoding="utf-8"))
    items = doc.get("items") or []
    if not items:
        print("core-shortlist.json has no items", file=sys.stderr)
        sys.exit(2)

    rub_by = load_csv_map(RUB, "ticker")
    man_by = load_csv_map(MAN, "ticker")
    earn: dict[str, dict[str, str]] = {}
    if ERN.is_file():
        with ERN.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                earn[(r.get("ticker") or "").strip().upper()] = r

    fh_by = load_csv_map(FH_CSV, "ticker")

    for it in items:
        t = (it.get("ticker") or "").strip().upper()
        if not t:
            continue
        rub = rub_by.get(t, {})
        man = man_by.get(t, {})
        slug = (man.get("theme_slug") or "").strip()
        link = (man.get("linkage_one_liner") or "").strip()
        theme_lbl = (man.get("theme_label") or man.get("theme_slug") or "").strip()
        e = earn.get(t, {})

        kill = format_kill(rub, slug)
        it["why_this_name"] = format_why(link, e, rub, it)
        it["market_context"] = format_market_context_row(fh_by.get(t))
        it.pop("social_sentiment", None)
        it.pop("sentiment_note", None)
        it["key_risk_kill"] = kill
        it["research_kill"] = kill
        it["research_thesis"] = format_research_thesis(link, e, rub)
        it["research_premortem"] = format_premortem_stub(rub, slug)
        it["research_glance"] = format_research_glance(link, theme_lbl, kill)
        bull, bear, watch = format_qual_bull_bear_watch(rub, link, slug)
        it["qual_bull"] = bull
        it["qual_bear"] = bear
        it["qual_watch"] = watch

    CORE_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Enriched {len(items)} items → {CORE_JSON}", file=sys.stderr)


if __name__ == "__main__":
    main()
