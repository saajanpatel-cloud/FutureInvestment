#!/usr/bin/env python3
"""Write _shortlist_prior.json after a successful refresh for next-run delta."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fi_embed_core import CORE_JSON, PRIOR_JSON, load_core_tickers, load_csv_index
from fi_select_shortlist_growth import rubric_total, safe_float

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
RUB = W / "rubric_scores.csv"
ERN = W / "earnings_data.csv"
RANK = W / "universe_valuation_rank.csv"
COMPOSITE = W / "universe_composite_rank.csv"
FH = W / "finnhub_context.csv"
SCEN = W / "scenario_results.csv"
MC = W / "monte_carlo_results.csv"


def main() -> int:
    tickers = load_core_tickers()
    if not tickers:
        print("No core tickers to snapshot", file=sys.stderr)
        return 2

    rub = load_csv_index(RUB)
    earn = load_csv_index(ERN)
    rk = load_csv_index(RANK)
    ck = load_csv_index(COMPOSITE)
    fh = load_csv_index(FH)
    scen = load_csv_index(SCEN)
    mc = load_csv_index(MC)

    scores: dict[str, float] = {}
    if CORE_JSON.is_file():
        doc = json.loads(CORE_JSON.read_text(encoding="utf-8"))
        memo = doc.get("selection_memo") or {}
        scores = {k: float(v) for k, v in (memo.get("per_ticker_borda") or {}).items()}

    by_ticker: dict[str, dict] = {}
    for t in tickers:
        r = rub.get(t, {})
        yoy = safe_float(earn.get(t, {}).get("rev_yoy_pct"))
        row = {
            "rubric_total": rubric_total(r),
            "borda": scores.get(t),
            "rev_yoy_pct": round(yoy, 1) if yoy is not None else None,
            "in_shortlist": True,
        }
        if t in rk:
            row["valuation_rank"] = (rk[t].get("valuation_rank") or "").strip()
            try:
                row["valuation_score"] = float(rk[t].get("valuation_score") or 0)
            except (TypeError, ValueError):
                pass
        if t in ck:
            row["composite_rank"] = (ck[t].get("composite_rank") or "").strip()
            try:
                row["composite_score"] = float(ck[t].get("composite_score") or 0)
            except (TypeError, ValueError):
                pass
            for k in ("pct_scenario", "pct_rubric", "pct_risk", "pct_mc", "pct_dcf"):
                v = (ck[t].get(k) or "").strip()
                if v:
                    row[k] = v
        if t in fh:
            row["analyst_skew"] = (fh[t].get("analyst_skew") or "").strip()
            row["insider_mspr"] = (fh[t].get("insider_mspr") or "").strip()
        if t in scen:
            row["weighted_upside"] = (scen[t].get("weighted_upside") or "").strip()
        if t in mc:
            row["prob_50pct_up"] = (mc[t].get("prob_50pct_up") or "").strip()
            row["prob_30pct_down"] = (mc[t].get("prob_30pct_down") or "").strip()
        row["rubric_tail"] = r.get("tail_risks", "")
        by_ticker[t] = row

    payload = {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "tickers": tickers,
        "by_ticker": by_ticker,
    }
    PRIOR_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {PRIOR_JSON} ({len(tickers)} tickers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
