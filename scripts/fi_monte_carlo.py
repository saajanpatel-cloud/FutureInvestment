#!/usr/bin/env python3
"""
Monte Carlo simulation for FutureInvestment proposed names.

Draws growth rates and exit multiples from triangular distributions based on
bear/base/bull assumptions, runs N simulations per ticker, and reports the
probability distribution of implied prices.

Outputs a CSV and an HTML fragment for embedding.

Not investment advice. Data may be delayed or wrong; verify with primary filings.

Usage:
  python fi_monte_carlo.py \
    --assumptions ../research/watchlists/scenario_assumptions.csv \
    --csv ../research/watchlists/monte_carlo_results.csv \
    --html ../research/watchlists/monte_carlo_fragment.html \
    --sims 10000
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import numpy as np
    _USE_NUMPY = True
except ImportError:
    import random
    _USE_NUMPY = False

try:
    import yfinance as yf
except ImportError:
    print("Install deps: pip install -r scripts/requirements.txt", file=sys.stderr)
    raise

HORIZON = 3  # years


def _num(v: Any, fallback: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return fallback


def _fmt_price(v: float) -> str:
    if v >= 1000:
        return f"${v:,.0f}"
    return f"${v:,.2f}"


def _fmt_pct(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.0f}%"


def fetch_fundamentals(ticker: str, metric: str) -> dict:
    """Pull price and the relevant per-share metric from yfinance.

    Forward EPS preferred over trailing for companies with heavy stock comp,
    cyclical troughs, or rapid growth.  Falls back to trailing if unavailable.
    """
    t = yf.Ticker(ticker)
    info = t.info or {}

    price = _num(info.get("currentPrice") or info.get("regularMarketPrice"), 0)
    shares = _num(info.get("sharesOutstanding"), 0)

    if metric == "eps":
        trail_eps = _num(info.get("trailingEps"), 0)
        fwd_eps = _num(info.get("forwardEps"), 0)
        base_metric = fwd_eps if fwd_eps > 0 else trail_eps
    else:
        rev = _num(info.get("totalRevenue"), 0)
        base_metric = rev / shares if shares > 0 else 0

    return {"price": price, "base_metric": base_metric}


# ── simulation ───────────────────────────────────────────────────────────────


def _triangular_draws(low: float, mode: float, high: float, n: int) -> Any:
    """Draw n samples from a triangular distribution."""
    if low > mode:
        low = mode
    if high < mode:
        high = mode
    if low == high:
        return np.full(n, mode) if _USE_NUMPY else [mode] * n

    if _USE_NUMPY:
        return np.random.triangular(low, mode, high, size=n)
    return [random.triangular(low, mode, high) for _ in range(n)]


def simulate_ticker(
    base_metric: float,
    bear_cagr: float,
    base_cagr: float,
    bull_cagr: float,
    bear_mult: float,
    base_mult: float,
    bull_mult: float,
    n: int,
) -> Any:
    """Run n simulations and return array of implied prices."""
    growth_draws = _triangular_draws(bear_cagr, base_cagr, bull_cagr, n)
    mult_draws = _triangular_draws(bear_mult, base_mult, bull_mult, n)

    if _USE_NUMPY:
        future_metric = base_metric * (1 + growth_draws) ** HORIZON
        return future_metric * mult_draws
    else:
        return [
            base_metric * ((1 + g) ** HORIZON) * m
            for g, m in zip(growth_draws, mult_draws)
        ]


def compute_stats(prices: Any, current_price: float) -> dict:
    """Compute summary statistics from simulation results."""
    if _USE_NUMPY:
        median = float(np.median(prices))
        p10 = float(np.percentile(prices, 10))
        p90 = float(np.percentile(prices, 90))
        mean = float(np.mean(prices))
        std = float(np.std(prices))
        prob_50up = float(np.mean(prices > current_price * 1.5)) * 100
        prob_30dn = float(np.mean(prices < current_price * 0.7)) * 100
    else:
        s = sorted(prices)
        n = len(s)
        median = s[n // 2]
        p10 = s[int(n * 0.10)]
        p90 = s[int(n * 0.90)]
        mean = sum(s) / n
        std = (sum((x - mean) ** 2 for x in s) / n) ** 0.5
        prob_50up = sum(1 for x in s if x > current_price * 1.5) / n * 100
        prob_30dn = sum(1 for x in s if x < current_price * 0.7) / n * 100

    return {
        "median": median,
        "p10": p10,
        "p90": p90,
        "mean": mean,
        "std": std,
        "prob_50up": prob_50up,
        "prob_30dn": prob_30dn,
    }


# ── histogram helper ─────────────────────────────────────────────────────────

_BLOCKS = " ▏▎▍▌▋▊▉█"


def _ascii_histogram(prices: Any, current_price: float, bins: int = 30, width: int = 40) -> str:
    """Build a text histogram using Unicode block chars."""
    if _USE_NUMPY:
        counts, edges = np.histogram(prices, bins=bins)
    else:
        mn, mx = min(prices), max(prices)
        step = (mx - mn) / bins if mx > mn else 1
        counts = [0] * bins
        edges = [mn + i * step for i in range(bins + 1)]
        for p in prices:
            idx = int((p - mn) / step)
            idx = min(idx, bins - 1)
            counts[idx] += 1

    max_count = max(counts) if max(counts) > 0 else 1
    lines = []

    for i, c in enumerate(counts):
        bar_len = c / max_count * width
        full = int(bar_len)
        frac = bar_len - full
        bar = "█" * full
        if frac > 0.05:
            bar += _BLOCKS[int(frac * 8)]

        lo = edges[i]
        hi = edges[i + 1]
        marker = " ◄ now" if lo <= current_price < hi else ""
        lines.append(f"  {_fmt_price(lo):>10} │{bar:<{width}}{marker}")

    return "\n".join(lines)


# ── orchestration ────────────────────────────────────────────────────────────


def run(assumptions_path: Path, csv_path: Path | None, html_path: Path | None, n_sims: int):
    with open(assumptions_path, newline="") as f:
        rows = list(csv.DictReader(f))

    results = []
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for row in rows:
        ticker = row["ticker"]
        metric = row.get("metric", "eps")
        print(f"  Fetching {ticker}…", file=sys.stderr)

        try:
            data = fetch_fundamentals(ticker, metric)
        except Exception as e:
            print(f"  ⚠ {ticker}: {e}", file=sys.stderr)
            continue

        price = data["price"]
        base_m = data["base_metric"]

        if price <= 0 or base_m <= 0:
            print(f"  ⚠ {ticker}: missing price or metric", file=sys.stderr)
            continue

        bear_cagr = _num(row["bear_cagr"])
        base_cagr = _num(row["base_cagr"])
        bull_cagr = _num(row["bull_cagr"])
        bear_mult = _num(row["bear_multiple"])
        base_mult = _num(row["base_multiple"])
        bull_mult = _num(row["bull_multiple"])

        sim_prices = simulate_ticker(
            base_m, bear_cagr, base_cagr, bull_cagr,
            bear_mult, base_mult, bull_mult, n_sims,
        )

        stats = compute_stats(sim_prices, price)
        histogram = _ascii_histogram(sim_prices, price)

        results.append({
            "ticker": ticker,
            "company": row["company"],
            "current_price": price,
            "median_price": stats["median"],
            "p10": stats["p10"],
            "p90": stats["p90"],
            "prob_50pct_up": stats["prob_50up"],
            "prob_30pct_down": stats["prob_30dn"],
            "mean_price": stats["mean"],
            "std_price": stats["std"],
            "histogram": histogram,
        })

    if csv_path:
        fieldnames = [
            "ticker", "current_price", "median_price", "p10", "p90",
            "prob_50pct_up", "prob_30pct_down", "mean_price", "std_price",
        ]
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in results:
                w.writerow({k: r[k] for k in fieldnames})
        print(f"  ✓ Wrote {csv_path} ({len(results)} rows)", file=sys.stderr)

    if html_path:
        html = _build_html(results, ts, n_sims)
        html_path.write_text(html, encoding="utf-8")
        print(f"  ✓ Wrote {html_path}", file=sys.stderr)

    return results


# ── HTML output ──────────────────────────────────────────────────────────────


def _build_html(results: list[dict], ts: str, n_sims: int) -> str:
    """Generate an HTML fragment for embedding in the report."""
    sims_str = f"{n_sims:,}"
    header = f"""<section id="monte-carlo">
  <h2>Monte Carlo distribution</h2>
  <p class="section-purpose"><strong>What is this?</strong> Instead of three point estimates, this runs {sims_str} simulations drawing growth and multiple assumptions from a range. The result is a probability distribution — what share of outcomes land above or below today's price.</p>
  <p class="muted">Generated {ts}. Not investment advice — illustrative simulations only. Verify with primary filings.</p>
  <div class="scroll">
  <table>
    <thead>
      <tr>
        <th>Ticker</th>
        <th>Current</th>
        <th>P10 (pessimistic)</th>
        <th>Median</th>
        <th>P90 (optimistic)</th>
        <th>Prob(&gt;50% up)</th>
        <th>Prob(&gt;30% down)</th>
      </tr>
    </thead>
    <tbody>
"""

    rows_html = ""
    for r in results:
        p50_cls = ' class="s-high"' if r["prob_50pct_up"] > 40 else ""
        p30_cls = ' class="s-low"' if r["prob_30pct_down"] > 40 else ""

        rows_html += f"""      <tr>
        <td><strong>{r['ticker']}</strong></td>
        <td>{_fmt_price(r['current_price'])}</td>
        <td>{_fmt_price(r['p10'])}</td>
        <td>{_fmt_price(r['median_price'])}</td>
        <td>{_fmt_price(r['p90'])}</td>
        <td{p50_cls}>{r['prob_50pct_up']:.1f}%</td>
        <td{p30_cls}>{r['prob_30pct_down']:.1f}%</td>
      </tr>
"""

    table_close = """    </tbody>
  </table>
  </div>
"""

    histograms_html = ""
    for r in results:
        histograms_html += f"""  <h3>{r['ticker']} — {r['company']}</h3>
  <pre class="mc-hist">{r['histogram']}</pre>
"""

    methodology = f"""  <details style="margin-top:1rem;">
    <summary class="muted">Methodology notes</summary>
    <ul class="muted" style="font-size:0.85rem;">
      <li><strong>Draws:</strong> Growth rates drawn from a triangular distribution (bear CAGR as min, base as mode, bull as max). Exit multiples drawn independently from a triangular distribution (bear multiple as min, base as mode, bull as max).</li>
      <li><strong>Projection:</strong> implied price = current metric × (1 + growth)³ × exit multiple.</li>
      <li><strong>Simulations:</strong> {sims_str} independent draws per ticker. Metric is forward EPS where available, trailing EPS as fallback, revenue per share for pre-profit names.</li>
      <li><strong>Statistics:</strong> P10/P90 are the 10th and 90th percentiles of the simulated distribution. Prob(&gt;50% up) is the share of simulations exceeding 1.5× current price. Prob(&gt;30% down) is the share falling below 0.7× current price.</li>
      <li><strong>Limitations:</strong> Assumes growth and multiple are independent. Single-metric model; ignores buybacks, dilution, dividends, and balance-sheet changes. Triangular distribution is a rough proxy for true uncertainty.</li>
      <li><strong>Edit:</strong> Change assumptions in <code>scenario_assumptions.csv</code> and re-run <code>python scripts/fi_monte_carlo.py</code>.</li>
    </ul>
  </details>
</section>
"""

    return header + rows_html + table_close + histograms_html + methodology


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser(description="Monte Carlo simulation for proposed tickers")
    ap.add_argument("--assumptions", required=True, help="Path to scenario_assumptions.csv")
    ap.add_argument("--csv", default=None, help="Output CSV path")
    ap.add_argument("--html", default=None, help="Output HTML fragment path")
    ap.add_argument("--sims", type=int, default=10_000, help="Number of simulations (default 10000)")
    args = ap.parse_args()

    results = run(
        Path(args.assumptions),
        Path(args.csv) if args.csv else None,
        Path(args.html) if args.html else None,
        args.sims,
    )

    if not results:
        print("No results generated.", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'Ticker':<7} {'Price':>8} {'P10':>10} {'Median':>10} {'P90':>10} {'P(>50%↑)':>10} {'P(>30%↓)':>10}")
    print("-" * 72)
    for r in results:
        print(
            f"{r['ticker']:<7} {_fmt_price(r['current_price']):>8} "
            f"{_fmt_price(r['p10']):>10} {_fmt_price(r['median_price']):>10} "
            f"{_fmt_price(r['p90']):>10} {r['prob_50pct_up']:>9.1f}% {r['prob_30pct_down']:>9.1f}%"
        )


if __name__ == "__main__":
    main()
