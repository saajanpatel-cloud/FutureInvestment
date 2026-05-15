#!/usr/bin/env python3
"""
Join scenario_results (universe pass) into a single valuation-led rank CSV.

Emits research/watchlists/universe_valuation_rank.csv with:
  ticker, valuation_score, valuation_rank, tier, weighted_upside, base_upside, bear_upside

Tier rules (configurable defaults — calibrate in Open product choices):
  Tier 1: weighted_upside >= 18 and bear_upside >= -35
  Tier 2: weighted_upside >= 8  and bear_upside >= -45
  Tier 3: weighted_upside >= -5 and bear_upside >= -55
  else tier 0 (excluded from post-20 expansion)

valuation_score = weighted_upside + 0.35*base_upside + 0.15*max(bear_upside, -40)
  (documented heuristic: 3y scenario lens + base + capped bear contribution)

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
DEFAULT_SCENARIO = W / "scenario_results_universe.csv"
OUT = W / "universe_valuation_rank.csv"


def safe_float(x: str | None) -> float | None:
    if x is None or x == "":
        return None
    try:
        v = float(x)
        if math.isnan(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def tier_for(w: float, _b: float, br: float) -> int:
    if w >= 18 and br >= -35:
        return 1
    if w >= 8 and br >= -45:
        return 2
    if w >= -5 and br >= -55:
        return 3
    return 0


def score_row(w: float, b: float, br: float) -> float:
    br_c = max(br, -40.0)
    return w + 0.35 * b + 0.15 * br_c


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenario-csv", type=Path, default=DEFAULT_SCENARIO)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    if not args.scenario_csv.is_file():
        print(f"Missing {args.scenario_csv}; run fi_scenarios on universe assumptions first.", file=sys.stderr)
        return 2

    rows: list[dict[str, str]] = []
    with args.scenario_csv.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = (r.get("ticker") or "").strip().upper()
            if not t:
                continue
            w = safe_float(r.get("weighted_upside")) or 0.0
            b = safe_float(r.get("base_upside")) or 0.0
            br = safe_float(r.get("bear_upside")) or -999.0
            sc = score_row(w, b, br)
            tier = tier_for(w, b, br)
            rows.append(
                {
                    "ticker": t,
                    "valuation_score": f"{sc:.4f}",
                    "tier": str(tier),
                    "weighted_upside": f"{w:.4f}",
                    "base_upside": f"{b:.4f}",
                    "bear_upside": f"{br:.4f}",
                    "_sc": sc,
                }
            )

    rows.sort(key=lambda x: -float(x["_sc"]))
    for i, row in enumerate(rows, start=1):
        row["valuation_rank"] = str(i)
        del row["_sc"]

    fieldnames = ["ticker", "valuation_rank", "valuation_score", "tier", "weighted_upside", "base_upside", "bear_upside"]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        for row in rows:
            w.writerow({k: row[k] for k in fieldnames})
    print(f"Wrote {args.out} ({len(rows)} tickers)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
