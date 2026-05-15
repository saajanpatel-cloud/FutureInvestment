#!/usr/bin/env python3
"""
Historical risk metrics for FutureInvestment proposed names.

Pulls 2 years of daily price data from yfinance for each ticker plus SPY
as benchmark, then computes beta, volatility, max drawdown, trailing 1-year
return, a Sharpe-like ratio, and SPY correlation.

Outputs risk_metrics.csv and an HTML fragment for embedding.

Not investment advice. Data may be delayed or wrong; verify with primary filings.

Usage:
  python fi_risk_metrics.py \
    --tickers NVDA,AMAT,PANW \
    --csv ../research/watchlists/risk_metrics.csv \
    --html ../research/watchlists/risk_fragment.html

  python fi_risk_metrics.py \
    --assumptions ../research/watchlists/scenario_assumptions.csv \
    --csv ../research/watchlists/risk_metrics.csv \
    --html ../research/watchlists/risk_fragment.html
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yfinance as yf
except ImportError:
    print("Install deps: pip install -r scripts/requirements.txt", file=sys.stderr)
    raise

LOOKBACK_YEARS = 2
TRADING_DAYS = 252
RISK_FREE_RATE = 0.045
BENCHMARK = "SPY"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tickers_from_assumptions(path: Path) -> list[str]:
    """Extract unique tickers from scenario_assumptions.csv."""
    with open(path, newline="") as f:
        return [row["ticker"].strip().upper() for row in csv.DictReader(f) if row.get("ticker")]


def _daily_returns(prices: list[float]) -> list[float]:
    return [(prices[i] / prices[i - 1]) - 1 for i in range(1, len(prices))]


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _cov(xs: list[float], ys: list[float]) -> float:
    n = min(len(xs), len(ys))
    mx, my = _mean(xs[:n]), _mean(ys[:n])
    return sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / (n - 1) if n > 1 else 0.0


def _var(xs: list[float]) -> float:
    return _cov(xs, xs)


def _std(xs: list[float]) -> float:
    return math.sqrt(_var(xs)) if xs else 0.0


def _corr(xs: list[float], ys: list[float]) -> float:
    sx, sy = _std(xs), _std(ys)
    if sx == 0 or sy == 0:
        return 0.0
    return _cov(xs, ys) / (sx * sy)


def _max_drawdown(prices: list[float]) -> float:
    peak = prices[0]
    worst = 0.0
    for p in prices[1:]:
        if p > peak:
            peak = p
        dd = (p - peak) / peak
        if dd < worst:
            worst = dd
    return worst


def _fmt_pct(v: float, decimals: int = 1) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v * 100:.{decimals}f}%"


def _fmt_ratio(v: float) -> str:
    return f"{v:.2f}"


# ---------------------------------------------------------------------------
# Data fetching and metric computation
# ---------------------------------------------------------------------------

def fetch_history(ticker: str, period: str = "2y") -> list[float]:
    """Return daily closing prices as a list."""
    t = yf.Ticker(ticker)
    hist = t.history(period=period)
    if hist.empty:
        return []
    return hist["Close"].dropna().tolist()


def compute_metrics(prices: list[float], bench_prices: list[float]) -> dict[str, Any] | None:
    """Compute risk metrics for a single name against the benchmark."""
    if len(prices) < TRADING_DAYS + 1 or len(bench_prices) < TRADING_DAYS + 1:
        return None

    n = min(len(prices), len(bench_prices))
    prices = prices[-n:]
    bench_prices = bench_prices[-n:]

    ret = _daily_returns(prices)
    bench_ret = _daily_returns(bench_prices)
    n_ret = min(len(ret), len(bench_ret))
    ret = ret[-n_ret:]
    bench_ret = bench_ret[-n_ret:]

    beta = _cov(ret, bench_ret) / _var(bench_ret) if _var(bench_ret) != 0 else 0.0
    vol = _std(ret) * math.sqrt(TRADING_DAYS)
    mdd = _max_drawdown(prices)
    spy_corr = _corr(ret, bench_ret)

    ann_return = (prices[-1] / prices[-TRADING_DAYS]) - 1 if len(prices) >= TRADING_DAYS else 0.0
    ret_1y_prices = prices[-TRADING_DAYS:]
    return_1y = (ret_1y_prices[-1] / ret_1y_prices[0]) - 1

    sharpe = (ann_return - RISK_FREE_RATE) / vol if vol > 0 else 0.0

    return {
        "beta": round(beta, 2),
        "volatility": round(vol, 4),
        "max_drawdown": round(mdd, 4),
        "return_1y": round(return_1y, 4),
        "sharpe": round(sharpe, 2),
        "spy_correlation": round(spy_corr, 2),
    }


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

CSV_FIELDS = ["ticker", "beta", "volatility", "max_drawdown", "return_1y", "sharpe", "spy_correlation"]


def write_csv(results: list[dict], path: Path) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in results:
            w.writerow({k: r[k] for k in CSV_FIELDS})
    print(f"  ✓ Wrote {path} ({len(results)} rows)", file=sys.stderr)


def _build_html(results: list[dict], ts: str) -> str:
    header = (
        '<section id="risk-metrics">\n'
        '  <h2>Historical risk metrics</h2>\n'
        '  <p class="section-purpose"><strong>What is this?</strong> How each name has '
        "behaved historically \u2014 volatility, drawdown, and market sensitivity. Past "
        "behaviour is not a forecast, but it helps size positions and set expectations.</p>\n"
        f'  <p class="muted">Generated {ts}. Not investment advice.</p>\n'
        '  <div class="scroll">\n'
        "  <table>\n"
        "    <thead>\n"
        "      <tr>\n"
        "        <th>Ticker</th>\n"
        "        <th>Beta</th>\n"
        "        <th>Ann. vol</th>\n"
        "        <th>Max DD</th>\n"
        "        <th>1Y return</th>\n"
        "        <th>Sharpe</th>\n"
        "        <th>SPY corr</th>\n"
        "      </tr>\n"
        "    </thead>\n"
        "    <tbody>\n"
    )

    rows_html = ""
    for r in results:
        beta_cls = ' class="s-low"' if r["beta"] > 1.5 else ""
        mdd_cls = ' class="s-low"' if r["max_drawdown"] < -0.40 else ""
        sharpe_cls = ' class="s-high"' if r["sharpe"] > 1.0 else ""

        rows_html += (
            f"      <tr>\n"
            f"        <td><strong>{r['ticker']}</strong></td>\n"
            f"        <td{beta_cls}>{_fmt_ratio(r['beta'])}</td>\n"
            f"        <td>{_fmt_pct(r['volatility'])}</td>\n"
            f"        <td{mdd_cls}>{_fmt_pct(r['max_drawdown'])}</td>\n"
            f"        <td>{_fmt_pct(r['return_1y'])}</td>\n"
            f"        <td{sharpe_cls}>{_fmt_ratio(r['sharpe'])}</td>\n"
            f"        <td>{_fmt_ratio(r['spy_correlation'])}</td>\n"
            f"      </tr>\n"
        )

    footer = (
        "    </tbody>\n"
        "  </table>\n"
        "  </div>\n"
        '  <details style="margin-top:1rem;">\n'
        '    <summary class="muted">Methodology notes</summary>\n'
        '    <ul class="muted" style="font-size:0.85rem;">\n'
        "      <li><strong>Lookback:</strong> 2 years of daily closing prices from yfinance.</li>\n"
        "      <li><strong>Returns:</strong> Simple daily returns (close-to-close).</li>\n"
        "      <li><strong>Beta:</strong> Cov(stock, SPY) / Var(SPY) over the full 2-year window.</li>\n"
        f"      <li><strong>Annualised volatility:</strong> Std(daily returns) \u00d7 \u221a{TRADING_DAYS}.</li>\n"
        "      <li><strong>Max drawdown:</strong> Worst peak-to-trough decline in the 2-year window.</li>\n"
        f"      <li><strong>Sharpe-like ratio:</strong> (annualised return \u2212 {RISK_FREE_RATE:.1%} risk-free) / annualised vol. Uses a {RISK_FREE_RATE:.1%} risk-free proxy (approximate T-bill yield).</li>\n"
        "      <li><strong>Correlation:</strong> Pearson correlation of daily returns vs SPY.</li>\n"
        "      <li><strong>Limitations:</strong> Backward-looking only; survivorship bias applies. Vol and drawdown regimes change. Not a predictor of future risk.</li>\n"
        "    </ul>\n"
        "  </details>\n"
        "</section>\n"
    )

    return header + rows_html + footer


def write_html(results: list[dict], path: Path) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    html = _build_html(results, ts)
    path.write_text(html, encoding="utf-8")
    print(f"  ✓ Wrote {path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(tickers: list[str], csv_path: Path | None, html_path: Path | None) -> list[dict]:
    print(f"  Fetching {BENCHMARK} benchmark…", file=sys.stderr)
    bench_prices = fetch_history(BENCHMARK)
    if not bench_prices:
        print(f"  ⚠ Could not fetch {BENCHMARK}", file=sys.stderr)
        sys.exit(1)

    results: list[dict] = []
    for ticker in tickers:
        print(f"  Fetching {ticker}…", file=sys.stderr)
        try:
            prices = fetch_history(ticker)
        except Exception as e:
            print(f"  ⚠ {ticker}: {e}", file=sys.stderr)
            continue

        if not prices:
            print(f"  ⚠ {ticker}: no price data", file=sys.stderr)
            continue

        metrics = compute_metrics(prices, bench_prices)
        if metrics is None:
            print(f"  ⚠ {ticker}: insufficient data for metrics", file=sys.stderr)
            continue

        results.append({"ticker": ticker, **metrics})

    if csv_path:
        write_csv(results, csv_path)
    if html_path:
        write_html(results, html_path)

    return results


def main():
    ap = argparse.ArgumentParser(description="Historical risk metrics for proposed names")
    ap.add_argument("--tickers", default=None, help="Comma-separated ticker list")
    ap.add_argument("--assumptions", default=None, help="Path to scenario_assumptions.csv (extracts tickers)")
    ap.add_argument("--csv", default=None, help="Output CSV path")
    ap.add_argument("--html", default=None, help="Output HTML fragment path")
    args = ap.parse_args()

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    elif args.assumptions:
        tickers = _tickers_from_assumptions(Path(args.assumptions))
    else:
        print("Provide --tickers or --assumptions", file=sys.stderr)
        sys.exit(1)

    if not tickers:
        print("No tickers found.", file=sys.stderr)
        sys.exit(1)

    results = run(
        tickers,
        Path(args.csv) if args.csv else None,
        Path(args.html) if args.html else None,
    )

    if not results:
        print("No results generated.", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'Ticker':<7} {'Beta':>6} {'Vol':>8} {'MaxDD':>8} {'1Y Ret':>8} {'Sharpe':>7} {'Corr':>6}")
    print("-" * 52)
    for r in results:
        print(
            f"{r['ticker']:<7} {_fmt_ratio(r['beta']):>6} "
            f"{_fmt_pct(r['volatility']):>8} {_fmt_pct(r['max_drawdown']):>8} "
            f"{_fmt_pct(r['return_1y']):>8} {_fmt_ratio(r['sharpe']):>7} "
            f"{_fmt_ratio(r['spy_correlation']):>6}"
        )


if __name__ == "__main__":
    main()
