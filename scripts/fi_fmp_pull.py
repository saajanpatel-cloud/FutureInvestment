#!/usr/bin/env python3
"""
Financial Modeling Prep (FMP) data pull — secondary data source for international tickers.

FMP covers 70,000+ securities globally including LSE, Euronext, Xetra, OMX, and Swiss Exchange.
It handles IFRS-reported financials which yfinance sometimes misparses.

Usage:
    export FMP_API_KEY="your_key_here"
    python scripts/fi_fmp_pull.py [--tickers TICK1,TICK2] [--all-intl]

Free tier: 250 requests/day. Enough for ~60 tickers (4 endpoints each).
Get a key at https://site.financialmodelingprep.com/developer/docs

Endpoints used:
    /stable/profile              → price, market cap, PE, sector
    /stable/income-statement     → revenue, margins (quarterly)
    /stable/balance-sheet-statement → debt, cash
    /stable/cash-flow-statement  → FCF
"""
import os, sys, csv, json, time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError

API_KEY = os.environ.get("FMP_API_KEY", "")
BASE_URL = "https://financialmodelingprep.com/stable"
WATCHLIST_DIR = Path(__file__).resolve().parent.parent / "research" / "watchlists"
OUTPUT_PATH = WATCHLIST_DIR / "fmp_earnings_data.csv"

INTL_TICKERS = [
    "IFX.DE", "ASM.AS", "BESI.AS", "SOITEC.PA", "AIXA.DE",
    "VAT.SW", "NOD.OL", "MEL.BR", "XFAB.PA",
    "ORSTED.CO", "IBE.MC", "VWS.CO", "RWE.DE", "ENEL.MI",
    "ENGI.PA", "CNA.L", "EDP.LS", "EDPR.LS", "NDX1.DE",
    "PRY.MI", "LR.PA", "NEX.PA", "DRX.L", "NEOEN.PA",
    "NCC.L", "WS1V.HE", "YSN.DE",
    "ATCO-A.ST", "HEXA-B.ST", "DSY.PA", "RSW.L", "IMI.L",
    "SPX.L", "HLMA.L", "SXS.L", "KNEBV.HE", "ALFA.ST",
    "SAND.ST", "EPIR.ST", "KION.DE", "GEA.DE", "SMIN.L",
    "ROG.SW", "NOVN.SW", "SAN.PA", "SN.L", "LONN.SW",
    "AFX.DE", "STMN.SW", "COLO-B.CO", "DEMANT.CO", "SRT3.DE",
    "HIK.L", "UCB.BR", "GMAB.CO", "BANB.SW", "ARGX.BR",
    "OXIG.L", "IQE.L",
    "BA.L", "RHM.DE", "AIR.PA", "HO.PA", "SAF.PA", "LDO.MI",
    "RR.L", "NGG", "SSE.L", "ENR.DE", "SU.PA", "SIE.DE",
    "ABB", "NVO", "AZN", "GSK",
]

def fmp_get(endpoint, params=None):
    if not API_KEY:
        print("ERROR: Set FMP_API_KEY environment variable")
        sys.exit(1)
    url = f"{BASE_URL}/{endpoint}?apikey={API_KEY}"
    if params:
        for k, v in params.items():
            url += f"&{k}={v}"
    try:
        req = Request(url, headers={"User-Agent": "FutureInvestment/1.0"})
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None

def fmt(val, prefix=""):
    if val is None: return "N/A"
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1e12: return f"{sign}{prefix}{abs_val/1e12:.1f}T"
    elif abs_val >= 1e9: return f"{sign}{prefix}{abs_val/1e9:.1f}B"
    elif abs_val >= 1e6: return f"{sign}{prefix}{abs_val/1e6:.1f}M"
    else: return f"{sign}{prefix}{abs_val:.0f}"

def pull_ticker(ticker):
    result = {"ticker": ticker}

    profile = fmp_get("profile", {"symbol": ticker})
    if profile and len(profile) > 0:
        p = profile[0]
        result.update({
            "price": p.get("price"),
            "mkt_cap": p.get("mktCap"),
            "sector": p.get("sector", ""),
            "industry": p.get("industry", ""),
            "exchange": p.get("exchangeShortName", ""),
            "currency": p.get("currency", ""),
        })
    else:
        result["error"] = "Profile not found"
        return result

    inc = fmp_get("income-statement", {"symbol": ticker, "period": "quarter", "limit": 5})
    if inc and len(inc) > 0:
        latest = inc[0]
        result["latest_q_rev"] = latest.get("revenue")
        result["gross_profit"] = latest.get("grossProfit")
        result["op_income"] = latest.get("operatingIncome")
        result["net_income"] = latest.get("netIncome")
        result["eps"] = latest.get("eps")
        rev = latest.get("revenue")
        gp = latest.get("grossProfit")
        oi = latest.get("operatingIncome")
        result["gross_margin_pct"] = (gp / rev * 100) if gp and rev and rev != 0 else None
        result["op_margin_pct"] = (oi / rev * 100) if oi and rev and rev != 0 else None
        if len(inc) >= 5:
            yoy_rev = inc[4].get("revenue")
            if yoy_rev and yoy_rev != 0 and rev:
                result["rev_yoy_pct"] = ((rev / yoy_rev) - 1) * 100

    bs = fmp_get("balance-sheet-statement", {"symbol": ticker, "period": "quarter", "limit": 1})
    if bs and len(bs) > 0:
        b = bs[0]
        total_debt = b.get("totalDebt", 0) or 0
        total_cash = b.get("cashAndCashEquivalents", 0) or 0
        result["total_debt"] = total_debt
        result["total_cash"] = total_cash
        result["net_cash"] = total_cash - total_debt

    cf = fmp_get("cash-flow-statement", {"symbol": ticker, "period": "quarter", "limit": 1})
    if cf and len(cf) > 0:
        c = cf[0]
        ocf = c.get("operatingCashFlow", 0) or 0
        capex = c.get("capitalExpenditure", 0) or 0
        result["fcf"] = ocf - abs(capex)

    time.sleep(0.5)
    return result

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", help="Comma-separated ticker list")
    parser.add_argument("--all-intl", action="store_true", help="Pull all international tickers")
    args = parser.parse_args()

    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(",")]
    elif args.all_intl:
        tickers = INTL_TICKERS
    else:
        print("Usage: --tickers TICK1,TICK2 or --all-intl")
        print(f"\nFMP_API_KEY is {'set' if API_KEY else 'NOT SET'}")
        if not API_KEY:
            print("\nTo get started:")
            print("  1. Sign up at https://site.financialmodelingprep.com/developer/docs")
            print("  2. Get your free API key")
            print("  3. export FMP_API_KEY='your_key_here'")
            print("  4. python scripts/fi_fmp_pull.py --all-intl")
        return

    if not API_KEY:
        print("ERROR: Set FMP_API_KEY environment variable")
        print("  Sign up at https://site.financialmodelingprep.com/developer/docs")
        sys.exit(1)

    fieldnames = [
        "ticker", "price", "mkt_cap", "exchange", "currency", "sector", "industry",
        "latest_q_rev", "gross_profit", "op_income", "net_income", "eps",
        "gross_margin_pct", "op_margin_pct", "rev_yoy_pct",
        "total_debt", "total_cash", "net_cash", "fcf",
    ]

    print(f"Pulling {len(tickers)} tickers from FMP...")
    results = []
    errors = []
    for i, t in enumerate(tickers):
        print(f"  [{i+1}/{len(tickers)}] {t}...", end=" ", flush=True)
        data = pull_ticker(t)
        results.append(data)
        if "error" in data:
            print(f"NOT FOUND")
            errors.append(t)
        else:
            rev = fmt(data.get("latest_q_rev"), "$")
            gm = data.get("gross_margin_pct")
            gm_s = f"{gm:.0f}%" if gm else "N/A"
            mc = fmt(data.get("mkt_cap"), "$")
            print(f"Rev={rev} GM={gm_s} MktCap={mc}")

    good = [r for r in results if "error" not in r]
    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in good:
            writer.writerow(r)

    print(f"\nWrote {len(good)} rows to {OUTPUT_PATH}")
    if errors:
        print(f"Not found ({len(errors)}): {', '.join(errors)}")

if __name__ == "__main__":
    main()
