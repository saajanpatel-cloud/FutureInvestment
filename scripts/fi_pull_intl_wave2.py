#!/usr/bin/env python3
"""
Pull earnings data for Wave 2 international tickers using yfinance.
Falls back gracefully when quarterly data is unavailable (common for European names).
Appends results to earnings_data.csv.

For tickers where yfinance returns no data, the script outputs what it can
(price, market cap, PE ratios) so rubric scoring can proceed with manual research.
"""
import sys, csv, time
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    print("pip install yfinance"); sys.exit(1)

WATCHLIST_DIR = Path(__file__).resolve().parent.parent / "research" / "watchlists"
OUTPUT_PATH = WATCHLIST_DIR / "earnings_data.csv"

WAVE2_TICKERS = [
    # AI infrastructure (11 names)
    "IFX.DE", "ASM.AS", "BESI.AS", "SOITEC.PA", "AIXA.DE",
    "VAT.SW", "NOD.OL", "MEL.BR", "XFAB.PA", "STM",
    # Energy (15 names)
    "ORSTED.CO", "IBE.MC", "VWS.CO", "RWE.DE", "ENEL.MI",
    "ENGI.PA", "CNA.L", "EDP.LS", "EDPR.LS", "NDX1.DE",
    "PRY.MI", "LR.PA", "NEX.PA", "DRX.L", "NEOEN.PA",
    # Cyber (3 names)
    "NCC.L", "WS1V.HE", "YSN.DE",
    # Automation (15 names)
    "ATCO-A.ST", "HEXA-B.ST", "DSY.PA", "RSW.L", "IMI.L",
    "SPX.L", "HLMA.L", "SXS.L", "KNEBV.HE", "ALFA.ST",
    "SAND.ST", "EPIR.ST", "KION.DE", "GEA.DE", "SMIN.L",
    # Health Tech (15 names)
    "ROG.SW", "NOVN.SW", "SAN.PA", "SN.L", "LONN.SW",
    "AFX.DE", "STMN.SW", "COLO-B.CO", "DEMANT.CO", "SRT3.DE",
    "HIK.L", "UCB.BR", "GMAB.CO", "BANB.SW", "ARGX.BR",
    # Quantum (2 names)
    "OXIG.L", "IQE.L",
    # Space & Defence cross-cutting (6 names)
    "BA.L", "RHM.DE", "AIR.PA", "HO.PA", "SAF.PA", "LDO.MI",
]

def safe_get(info, key, default=None):
    try:
        val = info.get(key, default)
        return default if val is None else val
    except Exception:
        return default

def get_quarterly_growth(financials):
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
    try:
        if financials is None or financials.empty:
            return None, None
        latest = financials.iloc[:, 0]
        gross_profit = latest.get("Gross Profit")
        revenue = None
        for label in ["Total Revenue", "Revenue", "Operating Revenue"]:
            if label in latest.index:
                revenue = latest[label]; break
        op_income = None
        for label in ["Operating Income", "EBIT"]:
            if label in latest.index:
                op_income = latest[label]; break
        gm = (gross_profit / revenue * 100) if (gross_profit and revenue and revenue != 0) else None
        om = (op_income / revenue * 100) if (op_income and revenue and revenue != 0) else None
        return gm, om
    except Exception:
        return None, None

def get_fcf(cashflow):
    try:
        if cashflow is None or cashflow.empty:
            return None
        latest = cashflow.iloc[:, 0]
        if "Free Cash Flow" in latest.index:
            return latest["Free Cash Flow"]
        elif "Operating Cash Flow" in latest.index and "Capital Expenditure" in latest.index:
            ocf = latest["Operating Cash Flow"]
            capex = latest["Capital Expenditure"]
            if ocf is not None and capex is not None:
                return ocf + capex
        return None
    except Exception:
        return None

def fmt(val, prefix=""):
    if val is None: return "N/A"
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1e12: return f"{sign}{prefix}{abs_val/1e12:.1f}T"
    elif abs_val >= 1e9: return f"{sign}{prefix}{abs_val/1e9:.1f}B"
    elif abs_val >= 1e6: return f"{sign}{prefix}{abs_val/1e6:.1f}M"
    else: return f"{sign}{prefix}{abs_val:.0f}"

def pull(ticker_symbol):
    try:
        tk = yf.Ticker(ticker_symbol)
        info = tk.info or {}
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
        q_fin = tk.quarterly_financials
        latest_rev, yoy_growth, qoq_growth = get_quarterly_growth(q_fin)
        gm, om = get_margins(q_fin)
        q_cf = tk.quarterly_cashflow
        fcf = get_fcf(q_cf)
        target_mean = safe_get(info, "targetMeanPrice")
        target_low = safe_get(info, "targetLowPrice")
        target_high = safe_get(info, "targetHighPrice")
        rec = safe_get(info, "recommendationKey", "")
        num_analysts = safe_get(info, "numberOfAnalystOpinions", 0)
        return {
            "ticker": ticker_symbol, "price": price, "mkt_cap": mkt_cap,
            "fwd_pe": fwd_pe, "trail_pe": trail_pe, "fwd_eps": fwd_eps,
            "trail_eps": trail_eps, "latest_q_rev": latest_rev,
            "rev_yoy_pct": yoy_growth, "rev_qoq_pct": qoq_growth,
            "rev_growth_ttm": rev_growth, "earnings_growth": earnings_growth,
            "gross_margin_pct": gm, "op_margin_pct": om, "fcf": fcf,
            "net_cash": net_cash, "total_debt": total_debt, "total_cash": total_cash,
            "analyst_target_mean": target_mean, "analyst_target_low": target_low,
            "analyst_target_high": target_high, "analyst_rec": rec,
            "num_analysts": num_analysts, "sector": sector, "industry": industry,
        }
    except Exception as e:
        print(f"  ERROR: {e}")
        return {"ticker": ticker_symbol, "error": str(e)}

def main():
    fieldnames = [
        "ticker", "price", "mkt_cap", "fwd_pe", "trail_pe",
        "fwd_eps", "trail_eps", "latest_q_rev", "rev_yoy_pct",
        "rev_qoq_pct", "rev_growth_ttm", "earnings_growth",
        "gross_margin_pct", "op_margin_pct", "fcf", "net_cash",
        "total_debt", "total_cash", "analyst_target_mean",
        "analyst_target_low", "analyst_target_high", "analyst_rec",
        "num_analysts", "sector", "industry",
    ]

    print(f"Pulling data for {len(WAVE2_TICKERS)} Wave 2 international tickers...")
    results = []
    errors = []
    for i, t in enumerate(WAVE2_TICKERS):
        print(f"  [{i+1}/{len(WAVE2_TICKERS)}] {t}...", end=" ", flush=True)
        data = pull(t)
        results.append(data)
        if "error" in data:
            print(f"FAILED: {data['error']}")
            errors.append(t)
        else:
            rev = fmt(data.get("latest_q_rev"), "$")
            yoy = data.get("rev_yoy_pct")
            yoy_s = f"{yoy:+.1f}%" if yoy else "N/A"
            gm = data.get("gross_margin_pct")
            gm_s = f"{gm:.0f}%" if gm else "N/A"
            mc = fmt(data.get("mkt_cap"), "$")
            pe = data.get("fwd_pe")
            pe_s = f"{pe:.1f}x" if pe else "N/A"
            print(f"Rev={rev} YoY={yoy_s} GM={gm_s} MktCap={mc} FwdPE={pe_s}")
        time.sleep(0.2)

    good = [r for r in results if "error" not in r]
    with open(OUTPUT_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        for r in good:
            writer.writerow(r)

    print(f"\nAppended {len(good)} rows to {OUTPUT_PATH}")
    if errors:
        print(f"Failed tickers ({len(errors)}): {', '.join(errors)}")

    has_rev = [r for r in good if r.get("latest_q_rev")]
    no_rev = [r for r in good if not r.get("latest_q_rev")]
    print(f"\nWith quarterly revenue: {len(has_rev)}")
    print(f"Without quarterly revenue (price/mktcap only): {len(no_rev)}")
    if no_rev:
        print("  " + ", ".join(r["ticker"] for r in no_rev))

if __name__ == "__main__":
    main()
