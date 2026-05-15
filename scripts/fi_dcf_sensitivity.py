#!/usr/bin/env python3
"""
DCF sensitivity-grid generator for FutureInvestment proposed names.

Pulls current price, forward EPS (or revenue per share for pre-profit names),
and shares outstanding from yfinance, then builds a 5×5 implied-price grid
varying growth rate vs. discount rate (WACC).

Outputs a CSV and an HTML fragment for embedding.

Not investment advice. Data may be delayed or wrong; verify with primary filings.

Usage:
  python fi_dcf_sensitivity.py \
    --assumptions ../research/watchlists/scenario_assumptions.csv \
    --csv ../research/watchlists/dcf_sensitivity.csv \
    --html ../research/watchlists/dcf_sensitivity_fragment.html
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

PROJECTION_YEARS = 5
TERMINAL_GROWTH = 0.025
WACC_STEPS = [0.08, 0.09, 0.10, 0.11, 0.12]
TERMINAL_REV_MULTIPLE = 3.0  # EV/Revenue for pre-profit terminal value


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


def _growth_steps(bear: float, bull: float) -> list[float]:
    """Return 5 evenly-spaced growth rates from bear to bull."""
    if bull == bear:
        return [bear] * 5
    step = (bull - bear) / 4
    return [bear + step * i for i in range(5)]


def fetch_fundamentals(ticker: str, metric: str) -> dict:
    """Pull price and the relevant per-share metric from yfinance.

    For EPS names, prefer forward EPS (analyst consensus NTM) over trailing.
    Falls back to trailing if forward is unavailable.
    """
    t = yf.Ticker(ticker)
    info = t.info or {}

    price = _num(info.get("currentPrice") or info.get("regularMarketPrice"), 0)
    shares = _num(info.get("sharesOutstanding"), 0)

    if metric == "eps":
        fwd_eps = _num(info.get("forwardEps"), 0)
        trail_eps = _num(info.get("trailingEps"), 0)
        base_metric = fwd_eps if fwd_eps > 0 else trail_eps
        label = "Fwd EPS" if fwd_eps > 0 else "Trail EPS"
    else:
        rev = _num(info.get("totalRevenue"), 0)
        base_metric = rev / shares if shares > 0 else 0
        label = "Rev/Sh"

    return {
        "price": price,
        "shares": shares,
        "base_metric": base_metric,
        "label": label,
    }


def dcf_eps(eps: float, growth: float, wacc: float) -> float:
    """Simplified DCF for EPS-based names.

    Project EPS forward at *growth* for PROJECTION_YEARS, discount each year's
    earnings back at *wacc*, then add a Gordon-growth terminal value.
    """
    if eps <= 0:
        return 0.0

    pv_sum = 0.0
    projected_eps = eps
    for yr in range(1, PROJECTION_YEARS + 1):
        projected_eps *= (1 + growth)
        pv_sum += projected_eps / ((1 + wacc) ** yr)

    if wacc <= TERMINAL_GROWTH:
        terminal = 0.0
    else:
        terminal_eps = projected_eps * (1 + TERMINAL_GROWTH)
        terminal = (terminal_eps / (wacc - TERMINAL_GROWTH)) / ((1 + wacc) ** PROJECTION_YEARS)

    return pv_sum + terminal


def dcf_revenue(rev_per_share: float, growth: float, wacc: float, shares: float) -> float:
    """Simplified DCF for pre-profit (P/S) names.

    Projects revenue per share forward, applies a terminal EV/Revenue multiple
    at the end of the projection period, and discounts back.
    """
    if rev_per_share <= 0 or shares <= 0:
        return 0.0

    projected_rev = rev_per_share
    for _ in range(PROJECTION_YEARS):
        projected_rev *= (1 + growth)

    terminal_value_per_share = projected_rev * TERMINAL_REV_MULTIPLE
    implied = terminal_value_per_share / ((1 + wacc) ** PROJECTION_YEARS)
    return implied


def run(assumptions_path: Path, csv_path: Path | None, html_path: Path | None):
    with open(assumptions_path, newline="") as f:
        rows = list(csv.DictReader(f))

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    all_cells: list[dict] = []
    ticker_grids: list[dict] = []

    for row in rows:
        ticker = row["ticker"]
        metric = row.get("metric", "eps")
        bear_cagr = _num(row["bear_cagr"])
        bull_cagr = _num(row["bull_cagr"])

        print(f"  Fetching {ticker}…", file=sys.stderr)
        try:
            data = fetch_fundamentals(ticker, metric)
        except Exception as e:
            print(f"  ⚠ {ticker}: {e}", file=sys.stderr)
            continue

        price = data["price"]
        base_m = data["base_metric"]
        shares = data["shares"]

        if price <= 0 or base_m <= 0:
            print(f"  ⚠ {ticker}: missing price or metric", file=sys.stderr)
            continue

        growth_rates = _growth_steps(bear_cagr, bull_cagr)

        grid: list[list[dict]] = []
        for g in growth_rates:
            grid_row = []
            for w in WACC_STEPS:
                if metric == "eps":
                    implied = dcf_eps(base_m, g, w)
                else:
                    implied = dcf_revenue(base_m, g, w, shares)

                upside = ((implied / price) - 1) * 100 if price > 0 else 0

                cell = {
                    "ticker": ticker,
                    "growth_rate": g,
                    "wacc": w,
                    "implied_price": round(implied, 2),
                    "upside_pct": round(upside, 1),
                }
                all_cells.append(cell)
                grid_row.append(cell)
            grid.append(grid_row)

        ticker_grids.append({
            "ticker": ticker,
            "company": row["company"],
            "theme": row["theme"],
            "metric": metric,
            "label": data["label"],
            "price": price,
            "base_metric": base_m,
            "growth_rates": growth_rates,
            "grid": grid,
        })

    if csv_path:
        fieldnames = ["ticker", "growth_rate", "wacc", "implied_price", "upside_pct"]
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(all_cells)
        print(f"  ✓ Wrote {csv_path} ({len(all_cells)} rows)", file=sys.stderr)

    if html_path:
        html = _build_html(ticker_grids, ts)
        html_path.write_text(html, encoding="utf-8")
        print(f"  ✓ Wrote {html_path}", file=sys.stderr)

    return ticker_grids


def dcf_so_what_inner_html(grid: list[list[dict]]) -> str:
    flat = [float(cell["upside_pct"]) for row in grid for cell in row]
    mid = float(grid[2][2]["upside_pct"])
    lo, hi = min(flat), max(flat)
    lo_i, hi_i, mid_i = round(lo), round(hi), round(mid)
    return (
        f"<strong>Read:</strong> Mid grid (~median growth, ~10% WACC) ≈ <strong>{mid_i:+d}%</strong> vs spot; "
        f"full ladder <strong>{lo_i:+d}%</strong>–<strong>{hi_i:+d}%</strong>. "
        "Terminal-heavy — pick the row/column you believe from filings, not one headline cell."
    )


def _single_cell_html(cell: dict) -> str:
    upside = float(cell["upside_pct"])
    cls = ""
    if upside >= 20:
        cls = ' class="s-high"'
    elif upside <= -20:
        cls = ' class="s-low"'
    return (
        f"          <td{cls}>"
        f'<span class="dcf-price">{_fmt_price(cell["implied_price"])}</span> '
        f"<small>{_fmt_pct(upside)}</small>"
        "</td>\n"
    )


def _render_dcf_table_html(grid: list[list[dict]], growth_rates: list[float]) -> str:
    """5 growth rows × 5 WACC columns (one discount rate per column)."""
    parts: list[str] = []
    parts.append('    <table class="dcf-table-compact">\n')
    parts.append("      <thead>\n        <tr>\n")
    parts.append('          <th scope="col">Growth \\ WACC</th>\n')
    for w in WACC_STEPS:
        parts.append(f'          <th scope="col">{w:.0%}</th>\n')
    parts.append("        </tr>\n      </thead>\n      <tbody>\n")
    for i, g in enumerate(growth_rates):
        parts.append("        <tr>\n")
        parts.append(f"          <td><strong>{g:.1%}</strong></td>\n")
        for j in range(len(WACC_STEPS)):
            parts.append(_single_cell_html(grid[i][j]))
        parts.append("        </tr>\n")
    parts.append("      </tbody>\n    </table>\n")
    return "".join(parts)


def dcf_so_what_paragraph_html(grid: list[list[dict]], indent: str = "    ") -> str:
    inner = dcf_so_what_inner_html(grid)
    return f'{indent}<p class="dcf-so-what muted">{inner}</p>\n'


def _build_html(ticker_grids: list[dict], ts: str) -> str:
    parts: list[str] = []
    parts.append(
        '<section id="dcf-sensitivity">\n'
        '  <h2>DCF sensitivity analysis</h2>\n'
        '  <p class="section-purpose"><strong>What is this?</strong> '
        "How sensitive is each implied price to your growth and discount rate "
        "assumptions? Each grid shows one ticker — find your growth assumption on "
        "the left, your discount rate across the top, and read the implied price. "
        'Green cells show upside from today\'s price; red show downside.</p>\n'
        f'  <p class="muted">Generated {ts}. Not predictions — illustrative '
        "scenarios to frame your own research. Verify in filings.</p>\n"
    )

    for tg in ticker_grids:
        ticker = tg["ticker"]
        company = tg["company"]
        price = tg["price"]
        label = tg["label"]
        base_m = tg["base_metric"]
        grid = tg["grid"]
        growth_rates = tg["growth_rates"]

        parts.append(
            f'  <details class="theme-card">\n'
            f"    <summary><strong>{ticker}</strong> — {company} "
            f"(current price {_fmt_price(price)}, {label} {base_m:.2f})</summary>\n"
            f'    <div class="scroll">\n'
        )
        parts.append(_render_dcf_table_html(grid, growth_rates))
        parts.append(dcf_so_what_paragraph_html(grid))
        parts.append("    </div>\n  </details>\n")

    parts.append(
        '  <details style="margin-top:1rem;">\n'
        '    <summary class="muted">Methodology notes</summary>\n'
        '    <ul class="muted" style="font-size:0.85rem;">\n'
        "      <li><strong>EPS-based DCF:</strong> Forward EPS (analyst consensus NTM) "
        f"projected at growth rate for {PROJECTION_YEARS} years. Each year's earnings "
        "discounted at WACC. Terminal value via Gordon growth model "
        f"(g = {TERMINAL_GROWTH:.1%}).</li>\n"
        "      <li><strong>Revenue-based DCF:</strong> For pre-profit names (metric=ps), "
        f"revenue per share is projected forward then valued at a terminal "
        f"EV/Revenue multiple of {TERMINAL_REV_MULTIPLE:.0f}x, discounted back.</li>\n"
        f"      <li><strong>Projection period:</strong> {PROJECTION_YEARS} years.</li>\n"
        "      <li><strong>Growth range:</strong> Bear CAGR to Bull CAGR from "
        "scenario_assumptions.csv with 3 intermediates.</li>\n"
        "      <li><strong>Discount rates:</strong> "
        + ", ".join(f"{w:.0%}" for w in WACC_STEPS)
        + " — one column per WACC in the grid.</li>\n"
        "      <li><strong>Limitations:</strong> Single-metric model; ignores buybacks, "
        "dilution, dividends, capex, and balance-sheet changes. Terminal value dominates "
        "in most cells — treat as directional, not precise.</li>\n"
        "    </ul>\n"
        "  </details>\n"
        "</section>\n"
    )

    return "".join(parts)


def main():
    ap = argparse.ArgumentParser(description="DCF sensitivity-grid generator")
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

    for tg in results:
        ticker = tg["ticker"]
        price = tg["price"]
        mid_row = tg["grid"][2]
        mid_cell = mid_row[2]
        print(
            f"  {ticker:<7} price={_fmt_price(price):>8}  "
            f"mid-grid implied={_fmt_price(mid_cell['implied_price']):>8} "
            f"({_fmt_pct(mid_cell['upside_pct'])})"
        )


if __name__ == "__main__":
    main()
