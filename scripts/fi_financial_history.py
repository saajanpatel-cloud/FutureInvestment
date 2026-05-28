#!/usr/bin/env python3
"""
Pull 5 fiscal years of annual financials for DRAFT report tickers (FI_DRAFT_TICKERS).

Output: research/watchlists/financial_history.csv (long format)
Not investment advice.
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    print("pip install yfinance", file=sys.stderr)
    sys.exit(1)

from fi_draft_common import ROOT, W, draft_skipped, load_draft_tickers

OUTPUT = W / "financial_history.csv"
YEARS = 5
FIELDS = (
    "ticker",
    "year",
    "revenue",
    "net_income",
    "free_cash_flow",
    "gross_margin_pct",
    "operating_margin_pct",
    "total_debt",
    "stockholders_equity",
    "roe_pct",
    "as_of",
)


def _safe_float(x) -> float | None:
    if x is None:
        return None
    try:
        v = float(x)
        if v != v:
            return None
        return v
    except (TypeError, ValueError):
        return None


def _margin_pct(num, den) -> float | None:
    n, d = _safe_float(num), _safe_float(den)
    if n is None or d is None or d == 0:
        return None
    return 100.0 * n / d


def pull_ticker(ticker: str) -> list[dict[str, str | float]]:
    t = yf.Ticker(ticker)
    inc = getattr(t, "income_stmt", None)
    if inc is None or (hasattr(inc, "empty") and inc.empty):
        inc = t.financials
    cf = getattr(t, "cashflow", None)
    if cf is None or (hasattr(cf, "empty") and cf.empty):
        cf = getattr(t, "cash_flow", None)
    bal = getattr(t, "balance_sheet", None)
    if bal is None or (hasattr(bal, "empty") and bal.empty):
        bal = getattr(t, "balancesheet", None)
    if inc is None or (hasattr(inc, "empty") and inc.empty):
        return []

    rows: list[dict[str, str | float]] = []
    as_of = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cols = list(inc.columns)[:YEARS]
    for col in cols:
        try:
            year = int(str(col)[:4])
        except ValueError:
            continue
        rev = _safe_float(inc.loc["Total Revenue", col]) if "Total Revenue" in inc.index else None
        ni = _safe_float(inc.loc["Net Income", col]) if "Net Income" in inc.index else None
        gp = _safe_float(inc.loc["Gross Profit", col]) if "Gross Profit" in inc.index else None
        op = _safe_float(inc.loc["Operating Income", col]) if "Operating Income" in inc.index else None
        fcf = None
        if cf is not None and hasattr(cf, "empty") and not cf.empty and "Free Cash Flow" in cf.index:
            fcf = _safe_float(cf.loc["Free Cash Flow", col])
        debt = None
        equity = None
        if bal is not None and hasattr(bal, "empty") and not bal.empty:
            if "Total Debt" in bal.index:
                debt = _safe_float(bal.loc["Total Debt", col])
            elif "Long Term Debt" in bal.index:
                debt = _safe_float(bal.loc["Long Term Debt", col])
            if "Stockholders Equity" in bal.index:
                equity = _safe_float(bal.loc["Stockholders Equity", col])
            elif "Total Stockholder Equity" in bal.index:
                equity = _safe_float(bal.loc["Total Stockholder Equity", col])
        roe = None
        if ni is not None and equity and equity != 0:
            roe = 100.0 * ni / equity
        rows.append(
            {
                "ticker": ticker,
                "year": year,
                "revenue": rev or "",
                "net_income": ni or "",
                "free_cash_flow": fcf or "",
                "gross_margin_pct": _margin_pct(gp, rev) or "",
                "operating_margin_pct": _margin_pct(op, rev) or "",
                "total_debt": debt or "",
                "stockholders_equity": equity or "",
                "roe_pct": round(roe, 2) if roe is not None else "",
                "as_of": as_of,
            }
        )
    rows.sort(key=lambda r: int(r["year"]), reverse=True)
    return rows


def main() -> int:
    if draft_skipped():
        print("SKIP: FI_SKIP_DRAFT_REPORT=1", file=sys.stderr)
        return 0
    tickers = load_draft_tickers()
    all_rows: list[dict] = []
    for ticker in tickers:
        try:
            rows = pull_ticker(ticker)
            all_rows.extend(rows)
            print(f"  {ticker}: {len(rows)} annual rows", file=sys.stderr)
        except Exception as ex:
            print(f"WARN: {ticker}: {ex}", file=sys.stderr)
    W.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in all_rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    print(f"Wrote {len(all_rows)} rows → {OUTPUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
