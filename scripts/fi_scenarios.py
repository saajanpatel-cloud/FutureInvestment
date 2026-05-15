#!/usr/bin/env python3
"""
Forward-multiple scenario model for FutureInvestment proposed names.

Pulls current price and trailing EPS (or revenue-per-share for pre-profit names)
from yfinance, then applies bull / base / bear growth and multiple assumptions
from scenario_assumptions.csv.

Outputs scenario_results.csv and an HTML fragment for embedding.

Not investment advice. Data may be delayed or wrong; verify with primary filings.

Usage:
  python fi_scenarios.py \
    --assumptions ../research/watchlists/scenario_assumptions.csv \
    --csv ../research/watchlists/scenario_results.csv \
    --html ../research/watchlists/scenario_fragment.html
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


def _fmt_dollar(v: float) -> str:
    if abs(v) >= 1e12:
        return f"${v / 1e12:.2f}T"
    if abs(v) >= 1e9:
        return f"${v / 1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v / 1e6:.0f}M"
    return f"${v:,.0f}"


def fetch_fundamentals(ticker: str, metric: str) -> dict:
    """Pull price and the relevant per-share metric from yfinance.

    For EPS names, prefer forward EPS (analyst consensus NTM) over trailing.
    Forward EPS better represents normalised earning power for companies with
    heavy stock comp (PANW), cyclical troughs (AMAT), or rapid growth.
    Falls back to trailing if forward is unavailable.
    """
    t = yf.Ticker(ticker)
    info = t.info or {}

    price = _num(info.get("currentPrice") or info.get("regularMarketPrice"), 0)
    mkt_cap = _num(info.get("marketCap"), 0)
    shares = _num(info.get("sharesOutstanding"), 0)

    if metric == "eps":
        trail_eps = _num(info.get("trailingEps"), 0)
        fwd_eps = _num(info.get("forwardEps"), 0)
        base_metric = fwd_eps if fwd_eps > 0 else trail_eps
        fwd_metric = fwd_eps
        used_forward = fwd_eps > 0
        current_mult = price / base_metric if base_metric > 0 else 0
    else:
        rev = _num(info.get("totalRevenue"), 0)
        base_metric = rev / shares if shares > 0 else 0
        fwd_metric = base_metric
        used_forward = False
        current_mult = price / base_metric if base_metric > 0 else 0

    return {
        "price": price,
        "mkt_cap": mkt_cap,
        "base_metric": base_metric,
        "fwd_metric": fwd_metric,
        "current_mult": current_mult,
        "used_forward": used_forward,
    }


def compute_scenario(base_metric: float, cagr: float, exit_mult: float) -> float:
    """Project metric forward by HORIZON years at cagr, apply exit multiple."""
    if base_metric <= 0:
        return 0
    future_metric = base_metric * ((1 + cagr) ** HORIZON)
    return future_metric * exit_mult


def run(assumptions_path: Path, csv_path: Path | None, html_path: Path | None):
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

        bull_cagr = _num(row["bull_cagr"])
        base_cagr = _num(row["base_cagr"])
        bear_cagr = _num(row["bear_cagr"])
        bull_mult = _num(row["bull_multiple"])
        base_mult = _num(row["base_multiple"])
        bear_mult = _num(row["bear_multiple"])
        bull_prob = _num(row["bull_prob"], 0.25)
        base_prob = _num(row["base_prob"], 0.50)
        bear_prob = _num(row["bear_prob"], 0.25)

        bull_price = compute_scenario(base_m, bull_cagr, bull_mult)
        base_price = compute_scenario(base_m, base_cagr, base_mult)
        bear_price = compute_scenario(base_m, bear_cagr, bear_mult)

        weighted = (bull_price * bull_prob) + (base_price * base_prob) + (bear_price * bear_prob)

        bull_upside = ((bull_price / price) - 1) * 100 if price > 0 else 0
        base_upside = ((base_price / price) - 1) * 100 if price > 0 else 0
        bear_upside = ((bear_price / price) - 1) * 100 if price > 0 else 0
        wt_upside = ((weighted / price) - 1) * 100 if price > 0 else 0

        metric_label = ("Fwd EPS" if data["used_forward"] else "Trail EPS") if metric == "eps" else "Rev/Sh"
        current_mult_label = f"{data['current_mult']:.1f}x" if data["current_mult"] > 0 else "n/a"

        results.append({
            "ticker": ticker,
            "company": row["company"],
            "theme": row["theme"],
            "metric_type": metric_label,
            "price": price,
            "mkt_cap": data["mkt_cap"],
            "current_metric": base_m,
            "current_multiple": current_mult_label,
            "bull_cagr": bull_cagr,
            "bull_multiple": bull_mult,
            "bull_price": bull_price,
            "bull_upside": bull_upside,
            "base_cagr": base_cagr,
            "base_multiple": base_mult,
            "base_price": base_price,
            "base_upside": base_upside,
            "bear_cagr": bear_cagr,
            "bear_multiple": bear_mult,
            "bear_price": bear_price,
            "bear_upside": bear_upside,
            "weighted_price": weighted,
            "weighted_upside": wt_upside,
            "bull_prob": bull_prob,
            "base_prob": base_prob,
            "bear_prob": bear_prob,
        })

    if csv_path:
        fieldnames = list(results[0].keys()) if results else []
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(results)
        print(f"  ✓ Wrote {csv_path} ({len(results)} rows)", file=sys.stderr)

    if html_path:
        html = _build_html(results, ts)
        html_path.write_text(html, encoding="utf-8")
        print(f"  ✓ Wrote {html_path}", file=sys.stderr)

    return results


def _build_html(results: list[dict], ts: str) -> str:
    """Generate an HTML table fragment for embedding in the report."""
    header = """<section id="scenarios">
  <h2>Forward-multiple scenario model</h2>
  <p class="section-purpose"><strong>What is this?</strong> A quantitative bull / base / bear framework for each proposed name. For every ticker: take today's trailing earnings (or revenue per share for pre-profit names), grow them at three rates over 3 years, apply an exit multiple, and compare the implied price to today's price. The weighted column blends all three scenarios by probability. Edit assumptions in <code>scenario_assumptions.csv</code> and re-run the script.</p>
  <p class="muted">Generated """ + ts + """. Not predictions — illustrative scenarios to frame your own research. Verify in filings.</p>
  <p class="muted" style="margin-bottom:0.5rem;"><strong>How to read this:</strong> <em>CAGR</em> = compound annual growth rate over 3 years. <em>Exit</em> = the P/E (or P/S) multiple you think the market will assign at the end of year 3. <em>Implied</em> = the share price those inputs produce. <em>Δ</em> = percentage change from today's price. <em>Weighted</em> = probability-blended target across all three scenarios.</p>
  <div class="scroll">
  <table>
    <thead>
      <tr>
        <th rowspan="2">Ticker</th>
        <th rowspan="2">Price</th>
        <th rowspan="2">Metric</th>
        <th rowspan="2">Current<br>multiple</th>
        <th colspan="3" style="text-align:center;border-bottom:2px solid var(--accent);">Bull</th>
        <th colspan="3" style="text-align:center;border-bottom:2px solid var(--fg);">Base</th>
        <th colspan="3" style="text-align:center;border-bottom:2px solid var(--warn);">Bear</th>
        <th colspan="2" style="text-align:center;border-bottom:2px solid #a78bfa;">Weighted</th>
      </tr>
      <tr>
        <th>CAGR</th><th>Exit</th><th>Implied / Δ</th>
        <th>CAGR</th><th>Exit</th><th>Implied / Δ</th>
        <th>CAGR</th><th>Exit</th><th>Implied / Δ</th>
        <th>Target</th><th>Δ</th>
      </tr>
    </thead>
    <tbody>
"""

    rows_html = ""
    for r in results:
        wt_class = "s-high" if r["weighted_upside"] >= 20 else ("s-low" if r["weighted_upside"] <= -10 else "")
        bull_class = "s-high" if r["bull_upside"] >= 50 else ""
        bear_class = "s-low" if r["bear_upside"] <= -30 else ""

        rows_html += f"""      <tr>
        <td><strong>{r['ticker']}</strong></td>
        <td>{_fmt_price(r['price'])}</td>
        <td>{r['metric_type']} {r['current_metric']:.2f}</td>
        <td>{r['current_multiple']}</td>
        <td>{r['bull_cagr']:.0%}</td><td>{r['bull_multiple']:.0f}x</td><td class="{bull_class}">{_fmt_price(r['bull_price'])} <small>{_fmt_pct(r['bull_upside'])}</small></td>
        <td>{r['base_cagr']:.0%}</td><td>{r['base_multiple']:.0f}x</td><td>{_fmt_price(r['base_price'])} <small>{_fmt_pct(r['base_upside'])}</small></td>
        <td>{r['bear_cagr']:.0%}</td><td>{r['bear_multiple']:.0f}x</td><td class="{bear_class}">{_fmt_price(r['bear_price'])} <small>{_fmt_pct(r['bear_upside'])}</small></td>
        <td class="{wt_class}"><strong>{_fmt_price(r['weighted_price'])}</strong></td>
        <td class="{wt_class}"><strong>{_fmt_pct(r['weighted_upside'])}</strong></td>
      </tr>
"""

    footer = """    </tbody>
  </table>
  </div>
  <details style="margin-top:1rem;">
    <summary class="muted">Methodology notes</summary>
    <ul class="muted" style="font-size:0.85rem;">
      <li><strong>Metric:</strong> Forward EPS (analyst consensus NTM) from yfinance where available, trailing EPS as fallback. Revenue per share for pre-profit names (IONQ). Forward EPS avoids distortions from stock comp, one-offs, or cyclical troughs.</li>
      <li><strong>Projection:</strong> metric × (1 + CAGR)³ × exit multiple = implied price.</li>
      <li><strong>Weighted target:</strong> Σ(scenario price × probability). Default split is 25/50/25 bull/base/bear; IONQ uses 20/45/35 given higher uncertainty.</li>
      <li><strong>Limitations:</strong> Single-metric model; ignores buybacks, dilution, dividends, and balance-sheet changes. Meant for relative comparison across the watchlist, not absolute price targets.</li>
      <li><strong>Edit:</strong> Change assumptions in <code>research/watchlists/scenario_assumptions.csv</code> and re-run <code>python scripts/fi_scenarios.py</code>.</li>
    </ul>
  </details>
</section>
"""

    return header + rows_html + footer


def main():
    ap = argparse.ArgumentParser(description="Forward-multiple scenario model")
    ap.add_argument("--assumptions", required=True, help="Path to scenario_assumptions.csv")
    ap.add_argument("--csv", default=None, help="Output CSV path")
    ap.add_argument("--html", default=None, help="Output HTML fragment path")
    args = ap.parse_args()

    results = run(
        Path(args.assumptions),
        Path(args.csv) if args.csv else None,
        Path(args.html) if args.html else None,
    )

    if not results:
        print("No results generated.", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'Ticker':<7} {'Price':>8} {'Bull':>10} {'Base':>10} {'Bear':>10} {'Weighted':>10}")
    print("-" * 60)
    for r in results:
        print(
            f"{r['ticker']:<7} {_fmt_price(r['price']):>8} "
            f"{_fmt_pct(r['bull_upside']):>10} {_fmt_pct(r['base_upside']):>10} "
            f"{_fmt_pct(r['bear_upside']):>10} {_fmt_pct(r['weighted_upside']):>10}"
        )


if __name__ == "__main__":
    main()
