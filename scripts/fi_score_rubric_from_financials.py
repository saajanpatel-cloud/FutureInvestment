#!/usr/bin/env python3
"""
Rule-based six-dimension rubric scores from earnings_data.csv (+ optional snapshot).

Runs after fi_earnings_pull.py on every refresh. Ensures rubric_scores.csv has one row
per manifest ticker with dims 1–5 and review metadata.

Not investment advice.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from fi_manifest import load_manifest
from fi_sync_rubric_from_earnings import yoy_to_growth_dim, safe_float

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
RUB = W / "rubric_scores.csv"
MAN = W / "universe_manifest.csv"
ERN = W / "earnings_data.csv"
SNAP = W / "rubric_universe.csv"

PLACEHOLDER = "Placeholder rubric"
DIM_COLS = ("growth", "margins", "balance_sheet", "durability", "tail_risks", "valuation")
EXTRA_COLS = ("filing_review_as_of", "review_depth")
DEFAULT_NOTE = "Awaiting earnings pull — run refresh_watchlists.sh"


def clamp_dim(v: int) -> str:
    return str(max(1, min(5, v)))


def margin_dim(gm: float | None, om: float | None) -> int:
    if gm is None and om is None:
        return 3
    g = gm if gm is not None else om
    o = om if om is not None else gm
    if g is None or o is None:
        score = g if g is not None else o
    else:
        score = (g + o) / 2.0
    if score >= 0.45:
        return 5
    if score >= 0.30:
        return 4
    if score >= 0.15:
        return 3
    if score >= 0.05:
        return 2
    return 1


def balance_sheet_dim(net_cash: float | None, total_debt: float | None, mcap: float | None) -> int:
    if net_cash is None and total_debt is None:
        return 3
    if net_cash is not None and net_cash > 0:
        if mcap and mcap > 0 and net_cash / mcap > 0.15:
            return 5
        return 4
    if net_cash is not None and net_cash > -1e9:
        return 3
    if total_debt is not None and mcap and mcap > 0 and total_debt / mcap > 1.5:
        return 1
    if total_debt is not None and mcap and mcap > 0 and total_debt / mcap > 0.8:
        return 2
    return 3


def valuation_dim(fwd_pe: float | None, trail_pe: float | None) -> int:
    pe = fwd_pe if fwd_pe and fwd_pe > 0 else trail_pe
    if pe is None or pe <= 0 or (isinstance(pe, float) and math.isnan(pe)):
        return 3
    if pe <= 12:
        return 5
    if pe <= 20:
        return 4
    if pe <= 35:
        return 3
    if pe <= 55:
        return 2
    return 1


def durability_dim(sector: str, industry: str) -> int:
    s = f"{sector} {industry}".lower()
    if any(k in s for k in ("utilities", "regulated", "tobacco", "beverages")):
        return 4
    if any(k in s for k in ("semiconductor", "software", "internet")):
        return 4
    if any(k in s for k in ("biotechnology", "uranium", "exploration")):
        return 2
    return 3


def tail_risk_dim(
    earn: dict[str, str],
    growth: int,
    balance: int,
) -> int:
    note_l = (earn.get("error") or "").lower()
    if "error" in note_l:
        return 5
    yoy = safe_float(earn.get("rev_yoy_pct"))
    if yoy is not None and yoy < -15:
        return 5
    if growth <= 1 and balance <= 2:
        return 5
    if growth <= 2:
        return 4
    if balance <= 2:
        return 4
    rec = (earn.get("analyst_rec") or "").lower()
    if rec in ("sell", "strongsell", "underperform"):
        return 4
    return 3


def load_earnings() -> dict[str, dict[str, str]]:
    if not ERN.is_file():
        return {}
    with ERN.open(encoding="utf-8", newline="") as f:
        return {r["ticker"].strip().upper(): r for r in csv.DictReader(f)}


def load_snapshot() -> dict[str, dict[str, str]]:
    if not SNAP.is_file():
        return {}
    with SNAP.open(encoding="utf-8", newline="") as f:
        return {r["ticker"].strip().upper(): r for r in csv.DictReader(f)}


def score_row(earn: dict[str, str], snap: dict[str, str]) -> dict[str, str]:
    yoy = safe_float(earn.get("rev_yoy_pct"))
    g = yoy_to_growth_dim(yoy) or 3
    gm = safe_float(earn.get("gross_margin_pct"))
    om = safe_float(earn.get("op_margin_pct"))
    if gm is not None and abs(gm) <= 1:
        gm = gm * 100
    if om is not None and abs(om) <= 1:
        om = om * 100
    m = safe_float(earn.get("mkt_cap")) or safe_float(snap.get("market_cap"))
    nc = safe_float(earn.get("net_cash"))
    td = safe_float(earn.get("total_debt"))
    fwd = safe_float(earn.get("fwd_pe")) or safe_float(snap.get("forward_pe"))
    trail = safe_float(earn.get("trail_pe")) or safe_float(snap.get("trailing_pe"))
    sector = earn.get("sector") or snap.get("sector") or ""
    industry = earn.get("industry") or snap.get("industry") or ""
    bs = balance_sheet_dim(nc, td, m)
    return {
        "growth": clamp_dim(g),
        "margins": clamp_dim(margin_dim(gm, om)),
        "balance_sheet": clamp_dim(bs),
        "durability": clamp_dim(durability_dim(sector, industry)),
        "tail_risks": clamp_dim(tail_risk_dim(earn, g, bs)),
        "valuation": clamp_dim(valuation_dim(fwd, trail)),
        "filing_review_as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "review_depth": "auto",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=MAN)
    ap.add_argument("--rubric", type=Path, default=RUB)
    ap.add_argument("--earnings", type=Path, default=ERN)
    args = ap.parse_args()

    manifest = load_manifest(args.manifest.resolve())
    earn_by = load_earnings()
    snap_by = load_snapshot()
    existing: dict[str, dict[str, str]] = {}
    if args.rubric.is_file():
        with args.rubric.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                t0 = (r.get("ticker") or "").strip().upper()
                if t0:
                    existing[t0] = r

    fieldnames = ["ticker"] + list(DIM_COLS) + ["note"] + list(EXTRA_COLS)
    out_rows: list[dict[str, str]] = []
    n_scored = n_missing = 0
    for m in manifest:
        t = m["ticker"]
        row = dict(existing.get(t, {}))
        row["ticker"] = t
        earn = earn_by.get(t, {})
        if earn and "error" not in earn:
            scored = score_row(earn, snap_by.get(t, {}))
            for k, v in scored.items():
                row[k] = v
            n_scored += 1
        else:
            n_missing += 1
            for c in DIM_COLS:
                if not (row.get(c) or "").strip().isdigit():
                    row[c] = "3"
            row.setdefault("filing_review_as_of", "")
            row.setdefault("review_depth", "pending")
        note = (row.get("note") or "").strip()
        if not note or PLACEHOLDER in note:
            row["note"] = DEFAULT_NOTE if not earn else note
        for c in fieldnames:
            row.setdefault(c, "")
        out_rows.append({k: row.get(k, "") for k in fieldnames})

    args.rubric.parent.mkdir(parents=True, exist_ok=True)
    with args.rubric.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)
    print(
        f"Rubric scored {n_scored}/{len(manifest)} tickers from earnings; "
        f"{n_missing} missing earnings row → {args.rubric}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
