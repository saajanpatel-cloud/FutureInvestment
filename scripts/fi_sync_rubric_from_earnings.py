#!/usr/bin/env python3
"""
Fill rubric_scores.csv placeholder one-liners from research/watchlists/earnings_data.csv
(latest-quarter YoY revenue, gross/operating margins when available) plus manifest linkage.

Also sets the **growth** dimension (1–5) from YoY % when the row was still a placeholder
or had an **empty note** with a matching earnings row, leaving other dimensions unchanged.

Usage (after `python scripts/fi_earnings_pull.py`):
  python scripts/fi_sync_rubric_from_earnings.py

Not investment advice.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
RUB = W / "rubric_scores.csv"
MAN = W / "universe_manifest.csv"
ERN = W / "earnings_data.csv"

PLACEHOLDER = "Placeholder rubric"


def yoy_to_growth_dim(yoy: float | None) -> int | None:
    if yoy is None or (isinstance(yoy, float) and math.isnan(yoy)):
        return None
    if yoy >= 40:
        return 5
    if yoy >= 20:
        return 4
    if yoy >= 5:
        return 3
    if yoy >= 0:
        return 2
    return 1


def safe_float(x) -> float | None:
    if x is None or x == "":
        return None
    try:
        v = float(x)
        if math.isnan(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def build_note(ticker: str, earn: dict[str, str], linkage: str) -> str:
    from fi_narrative import format_rubric_note

    return format_rubric_note(earn, linkage)


def load_manifest_linkage() -> dict[str, str]:
    out: dict[str, str] = {}
    with MAN.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out[row["ticker"].strip().upper()] = (row.get("linkage_one_liner") or "").strip()
    return out


def load_earnings() -> dict[str, dict[str, str]]:
    if not ERN.is_file():
        print(f"Missing {ERN}; run: python scripts/fi_earnings_pull.py", file=sys.stderr)
        sys.exit(2)
    out: dict[str, dict[str, str]] = {}
    with ERN.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out[row["ticker"].strip().upper()] = row
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Sync rubric notes / growth dim from earnings_data.csv")
    ap.add_argument(
        "--rewrite-notes",
        action="store_true",
        help="Rebuild note from yfinance earnings row for every ticker that has earnings_data (not only 'Placeholder rubric').",
    )
    args = ap.parse_args()

    linkage = load_manifest_linkage()
    earn_by = load_earnings()
    rows = list(csv.DictReader(RUB.open(encoding="utf-8", newline="")))
    fieldnames = list(rows[0].keys()) if rows else []
    n_note = n_growth = 0
    for row in rows:
        t = (row.get("ticker") or "").strip().upper()
        if not t:
            continue
        note = (row.get("note") or "").strip()
        e = earn_by.get(t, {})
        link = linkage.get(t, "")
        if args.rewrite_notes:
            if not e:
                continue
            row["note"] = build_note(t, e, link)
            n_note += 1
        elif PLACEHOLDER in note or (not note and e):
            # Empty note + earnings row: treat like placeholder so sync is not silently skipped.
            row["note"] = build_note(t, e, link)
            n_note += 1
        else:
            continue
        yoy = safe_float(e.get("rev_yoy_pct"))
        gd = yoy_to_growth_dim(yoy)
        if gd is not None:
            row["growth"] = str(gd)
            n_growth += 1
    with RUB.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"Updated {n_note} rubric notes; refreshed growth dim on {n_growth} rows → {RUB}")


if __name__ == "__main__":
    main()
