#!/usr/bin/env python3
"""
Pull latest quarterly earnings and financial data for all universe tickers.
Uses yfinance (already installed). Outputs structured CSV for rubric scoring.

Usage: python scripts/fi_earnings_pull.py
Output: research/watchlists/earnings_data.csv
"""

import sys
import csv
import json
from datetime import datetime
from pathlib import Path

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    print("pip install yfinance pandas")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
WATCHLIST_DIR = SCRIPT_DIR.parent / "research" / "watchlists"
MANIFEST_PATH = WATCHLIST_DIR / "universe_manifest.csv"
OUTPUT_PATH = WATCHLIST_DIR / "earnings_data.csv"

# All tickers: existing universe + new additions
NEW_TICKERS = {
    "ai": [
        ("TSM", "TSMC", "Foundry monopoly on advanced nodes"),
        ("ARM", "Arm Holdings", "Chip architecture licensing for AI inference"),
        ("MRVL", "Marvell Technology", "Custom AI silicon and networking"),
        ("CDNS", "Cadence Design Systems", "EDA software duopoly"),
        ("ASML", "ASML Holding", "EUV lithography monopoly"),
        ("ALAB", "Astera Labs", "AI data centre connectivity solutions"),
        ("MPWR", "Monolithic Power Systems", "Power management ICs for AI servers"),
        ("COHR", "Coherent Corp", "Optical interconnects for AI data centres"),
        ("AMKR", "Amkor Technology", "Advanced chip packaging and test"),
        ("SMCI", "Super Micro Computer", "AI server assembly and integration"),
    ],
    "energy": [
        ("PWR", "Quanta Services", "Grid construction and electrical infrastructure"),
        ("GEV", "GE Vernova", "Gas turbines wind and grid equipment"),
        ("MTZ", "MasTec", "Infrastructure and clean energy construction"),
        ("CCJ", "Cameco", "Uranium mining and nuclear fuel supply"),
        ("FLNC", "Fluence Energy", "Grid-scale battery storage systems"),
        ("ARRY", "Array Technologies", "Utility-scale solar tracking systems"),
    ],
    "cyber": [
        ("CYBR", "CyberArk Software", "Privileged access and identity security"),
        ("NET", "Cloudflare", "Edge security CDN and zero-trust networking"),
    ],
    "auto": [
        ("TER", "Teradyne", "Semiconductor test equipment and collaborative robotics"),
        ("CGNX", "Cognex", "Machine vision for factory automation"),
    ],
    "health": [
        ("DXCM", "DexCom", "Continuous glucose monitoring digital health"),
        ("AMGN", "Amgen", "Biosimilars and MariTide GLP-1 pipeline"),
        ("REGN", "Regeneron", "Dupixent franchise and obesity pipeline"),
        ("SYK", "Stryker", "Mako robotic surgery and orthopedics"),
        ("TMO", "Thermo Fisher Scientific", "Life sciences tools and instruments"),
        ("VEEV", "Veeva Systems", "Cloud software for pharma and life sciences"),
        ("EW", "Edwards Lifesciences", "Transcatheter heart valves TAVR leader"),
        ("PODD", "Insulet", "Omnipod insulin pump system"),
        ("MRNA", "Moderna", "mRNA platform vaccines and therapeutics"),
    ],
}


def safe_get(info, key, default=None):
    """Safely get a value from yfinance info dict."""
    try:
        val = info.get(key, default)
        if val is None:
            return default
        return val
    except Exception:
        return default


def get_quarterly_growth(financials):
    """Calculate YoY revenue growth from quarterly financials."""
    try:
        if financials is None or financials.empty:
            return None, None, None
        rev_row = None
        for label in ["Total Revenue", "Revenue", "Operating Revenue"]:
            if label in financials.index:
                rev_row = financials.loc[label]
                break
        if rev_row is None:
            return None, None, None
        vals = rev_row.dropna().sort_index(ascending=False)
        if len(vals) < 1:
            return None, None, None
        latest_rev = vals.iloc[0]
        yoy_rev = vals.iloc[4] if len(vals) >= 5 else None
        qoq_rev = vals.iloc[1] if len(vals) >= 2 else None
        yoy_growth = ((latest_rev / yoy_rev) - 1) * 100 if yoy_rev and yoy_rev != 0 else None
        qoq_growth = ((latest_rev / qoq_rev) - 1) * 100 if qoq_rev and qoq_rev != 0 else None
        return latest_rev, yoy_growth, qoq_growth
    except Exception:
        return None, None, None


def get_margins(financials):
    """Extract gross and operating margins from quarterly financials."""
    try:
        if financials is None or financials.empty:
            return None, None
        latest = financials.iloc[:, 0]

        gross_profit = None
        for label in ["Gross Profit"]:
            if label in latest.index:
                gross_profit = latest[label]
                break

        revenue = None
        for label in ["Total Revenue", "Revenue", "Operating Revenue"]:
            if label in latest.index:
                revenue = latest[label]
                break

        op_income = None
        for label in ["Operating Income", "EBIT"]:
            if label in latest.index:
                op_income = latest[label]
                break

        gm = (gross_profit / revenue * 100) if (gross_profit and revenue and revenue != 0) else None
        om = (op_income / revenue * 100) if (op_income and revenue and revenue != 0) else None
        return gm, om
    except Exception:
        return None, None


def get_fcf(cashflow):
    """Extract free cash flow from quarterly cash flow statement."""
    try:
        if cashflow is None or cashflow.empty:
            return None
        latest = cashflow.iloc[:, 0]
        fcf = None
        if "Free Cash Flow" in latest.index:
            fcf = latest["Free Cash Flow"]
        elif "Operating Cash Flow" in latest.index and "Capital Expenditure" in latest.index:
            ocf = latest["Operating Cash Flow"]
            capex = latest["Capital Expenditure"]
            if ocf is not None and capex is not None:
                fcf = ocf + capex  # capex is negative
        return fcf
    except Exception:
        return None


def fmt_num(val, prefix="$", suffix="", decimals=1):
    """Format large numbers readably."""
    if val is None:
        return "N/A"
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1e12:
        return f"{sign}{prefix}{abs_val/1e12:.{decimals}f}T{suffix}"
    elif abs_val >= 1e9:
        return f"{sign}{prefix}{abs_val/1e9:.{decimals}f}B{suffix}"
    elif abs_val >= 1e6:
        return f"{sign}{prefix}{abs_val/1e6:.{decimals}f}M{suffix}"
    else:
        return f"{sign}{prefix}{abs_val:.0f}{suffix}"


def fmt_pct(val):
    if val is None:
        return "N/A"
    return f"{val:+.1f}%"


def pull_ticker_data(ticker_symbol):
    """Pull all relevant data for a single ticker."""
    try:
        tk = yf.Ticker(ticker_symbol)
        info = tk.info or {}

        # Basic info
        price = safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice")
        mkt_cap = safe_get(info, "marketCap")
        fwd_pe = safe_get(info, "forwardPE")
        trail_pe = safe_get(info, "trailingPE")
        fwd_eps = safe_get(info, "forwardEps")
        trail_eps = safe_get(info, "trailingEps")
        sector = safe_get(info, "sector", "")
        industry = safe_get(info, "industry", "")
        total_debt = safe_get(info, "totalDebt", 0) or 0
        total_cash = safe_get(info, "totalCash", 0) or 0
        net_cash = total_cash - total_debt
        rev_growth = safe_get(info, "revenueGrowth")
        earnings_growth = safe_get(info, "earningsGrowth")

        # Quarterly financials
        q_fin = tk.quarterly_financials
        latest_rev, yoy_growth, qoq_growth = get_quarterly_growth(q_fin)
        gm, om = get_margins(q_fin)

        # Cash flow
        q_cf = tk.quarterly_cashflow
        fcf = get_fcf(q_cf)

        # Analyst targets
        target_mean = safe_get(info, "targetMeanPrice")
        target_low = safe_get(info, "targetLowPrice")
        target_high = safe_get(info, "targetHighPrice")
        rec = safe_get(info, "recommendationKey", "")
        num_analysts = safe_get(info, "numberOfAnalystOpinions", 0)

        return {
            "ticker": ticker_symbol,
            "price": price,
            "mkt_cap": mkt_cap,
            "fwd_pe": fwd_pe,
            "trail_pe": trail_pe,
            "fwd_eps": fwd_eps,
            "trail_eps": trail_eps,
            "latest_q_rev": latest_rev,
            "rev_yoy_pct": yoy_growth,
            "rev_qoq_pct": qoq_growth,
            "rev_growth_ttm": rev_growth,
            "earnings_growth": earnings_growth,
            "gross_margin_pct": gm,
            "op_margin_pct": om,
            "fcf": fcf,
            "net_cash": net_cash,
            "total_debt": total_debt,
            "total_cash": total_cash,
            "analyst_target_mean": target_mean,
            "analyst_target_low": target_low,
            "analyst_target_high": target_high,
            "analyst_rec": rec,
            "num_analysts": num_analysts,
            "sector": sector,
            "industry": industry,
        }
    except Exception as e:
        print(f"  ERROR pulling {ticker_symbol}: {e}")
        return {"ticker": ticker_symbol, "error": str(e)}


def main():
    # Load existing tickers from manifest
    existing_tickers = set()
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_tickers.add(row["ticker"])

    # Combine existing + new
    all_tickers = list(existing_tickers)
    new_ticker_set = set()
    for theme_tickers in NEW_TICKERS.values():
        for t, _, _ in theme_tickers:
            new_ticker_set.add(t)
            if t not in existing_tickers:
                all_tickers.append(t)

    all_tickers.sort()
    print(f"Pulling data for {len(all_tickers)} tickers...")
    print(f"  Existing: {len(existing_tickers)}, New: {len(new_ticker_set - existing_tickers)}")

    results = []
    for i, ticker in enumerate(all_tickers):
        tag = " [NEW]" if ticker in new_ticker_set and ticker not in existing_tickers else ""
        print(f"  [{i+1}/{len(all_tickers)}] {ticker}{tag}...", end=" ", flush=True)
        data = pull_ticker_data(ticker)
        results.append(data)
        if "error" in data:
            print(f"FAILED: {data['error']}")
        else:
            rev_str = fmt_num(data.get("latest_q_rev"))
            growth_str = fmt_pct(data.get("rev_yoy_pct"))
            print(f"Rev={rev_str} YoY={growth_str}")

    # Write CSV
    if not results:
        print("No data pulled.")
        return

    fieldnames = [
        "ticker", "price", "mkt_cap", "fwd_pe", "trail_pe",
        "fwd_eps", "trail_eps", "latest_q_rev", "rev_yoy_pct",
        "rev_qoq_pct", "rev_growth_ttm", "earnings_growth",
        "gross_margin_pct", "op_margin_pct", "fcf", "net_cash",
        "total_debt", "total_cash", "analyst_target_mean",
        "analyst_target_low", "analyst_target_high", "analyst_rec",
        "num_analysts", "sector", "industry",
    ]

    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print(f"\nWrote {len(results)} rows to {OUTPUT_PATH}")

    # Print summary of top growers
    growers = [r for r in results if r.get("rev_yoy_pct") is not None]
    growers.sort(key=lambda x: x["rev_yoy_pct"], reverse=True)
    print("\n=== TOP 15 BY REVENUE GROWTH (YoY) ===")
    for r in growers[:15]:
        new_tag = " *NEW*" if r["ticker"] in new_ticker_set else ""
        print(f"  {r['ticker']:6s} {fmt_pct(r['rev_yoy_pct']):>8s}  Rev={fmt_num(r.get('latest_q_rev'))}  GM={fmt_pct(r.get('gross_margin_pct'))}  P/E(fwd)={r.get('fwd_pe', 'N/A')}{new_tag}")

    print("\n=== BOTTOM 5 (DECLINING REVENUE) ===")
    for r in growers[-5:]:
        print(f"  {r['ticker']:6s} {fmt_pct(r['rev_yoy_pct']):>8s}  Rev={fmt_num(r.get('latest_q_rev'))}")


if __name__ == "__main__":
    main()
