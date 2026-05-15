#!/usr/bin/env python3
"""
Embed core-shortlist valuation tables into SINGLE_SCREEN_REPORT.html #value section.

Patches tbody for scenario, risk, and Monte Carlo summary tables from core CSVs.
Run after fi_scenarios / fi_risk_metrics / fi_monte_carlo on core assumptions.

Not investment advice.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fi_embed_core import (
    HTML,
    W,
    fmt_pct,
    fmt_price,
    load_core_tickers,
    load_csv_index,
    patch_tbody_by_class,
    patch_tbody_scroll_data_after_marker,
    restore_print_risk_def_table,
)

SCEN = W / "scenario_results.csv"
RISK = W / "risk_metrics.csv"
MC = W / "monte_carlo_results.csv"


def _num(row: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key) or default)
    except (TypeError, ValueError):
        return default


def build_scenario_rows(tickers: list[str], by_t: dict[str, dict]) -> str:
    rows: list[str] = []
    for t in tickers:
        r = by_t.get(t)
        if not r:
            continue
        wt_up = _num(r, "weighted_upside")
        bull_up = _num(r, "bull_upside")
        bear_up = _num(r, "bear_upside")
        wt_class = "s-high" if wt_up >= 20 else ("s-low" if wt_up <= -10 else "")
        bull_class = "s-high" if bull_up >= 50 else ""
        bear_class = "s-low" if bear_up <= -30 else ""
        price = _num(r, "price")
        cm = (r.get("current_multiple") or "n/a").strip()
        metric = (r.get("metric_type") or "EPS").strip()
        base_m = _num(r, "current_metric")
        rows.append(
            f"          <tr>\n"
            f"            <td><strong>{t}</strong></td>\n"
            f"            <td>{fmt_price(price)}</td>\n"
            f"            <td>{metric} {base_m:.2f}</td>\n"
            f"            <td>{cm}</td>\n"
            f"            <td>{_num(r, 'bull_cagr'):.0%}</td><td>{_num(r, 'bull_multiple'):.0f}x</td>"
            f'<td class="{bull_class}">{fmt_price(_num(r, "bull_price"))} <small>{fmt_pct(bull_up)}</small></td>\n'
            f"            <td>{_num(r, 'base_cagr'):.0%}</td><td>{_num(r, 'base_multiple'):.0f}x</td>"
            f"            <td>{fmt_price(_num(r, 'base_price'))} <small>{fmt_pct(_num(r, 'base_upside'))}</small></td>\n"
            f"            <td>{_num(r, 'bear_cagr'):.0%}</td><td>{_num(r, 'bear_multiple'):.0f}x</td>"
            f'<td class="{bear_class}">{fmt_price(_num(r, "bear_price"))} <small>{fmt_pct(bear_up)}</small></td>\n'
            f'            <td class="{wt_class}"><strong>{fmt_price(_num(r, "weighted_price"))}</strong></td>\n'
            f'            <td class="{wt_class}"><strong>{fmt_pct(wt_up)}</strong></td>\n'
            f"          </tr>"
        )
    return "\n".join(rows) + "\n"


def build_risk_rows(tickers: list[str], by_t: dict[str, dict]) -> str:
    rows: list[str] = []
    for t in tickers:
        r = by_t.get(t)
        if not r:
            continue
        beta = _num(r, "beta")
        mdd = _num(r, "max_drawdown")
        sharpe = _num(r, "sharpe")
        beta_cls = ' class="s-low"' if beta > 1.5 else ""
        mdd_cls = ' class="s-low"' if mdd < -0.40 else ""
        sharpe_cls = ' class="s-high"' if sharpe > 1.0 else ""
        vol = _num(r, "volatility")
        ret1y = _num(r, "return_1y")
        spy = _num(r, "spy_correlation")
        rows.append(
            f"      <tr>\n"
            f"        <td><strong>{t}</strong></td>\n"
            f"        <td{beta_cls}>{beta:.2f}</td>\n"
            f"        <td>{fmt_pct(vol * 100)}</td>\n"
            f"        <td{mdd_cls}>{fmt_pct(mdd * 100)}</td>\n"
            f"        <td>{fmt_pct(ret1y * 100)}</td>\n"
            f"        <td{sharpe_cls}>{sharpe:.2f}</td>\n"
            f"        <td>{spy:.2f}</td>\n"
            f"      </tr>"
        )
    return "\n".join(rows) + "\n"


def build_mc_rows(tickers: list[str], by_t: dict[str, dict]) -> str:
    rows: list[str] = []
    for t in tickers:
        r = by_t.get(t)
        if not r:
            continue
        p50 = _num(r, "prob_50pct_up")
        p30 = _num(r, "prob_30pct_down")
        p50_cls = ' class="s-high"' if p50 > 40 else ""
        p30_cls = ' class="s-low"' if p30 > 40 else ""
        rows.append(
            f"      <tr>\n"
            f"        <td><strong>{t}</strong></td>\n"
            f"        <td>{fmt_price(_num(r, 'current_price'))}</td>\n"
            f"        <td>{fmt_price(_num(r, 'p10'))}</td>\n"
            f"        <td>{fmt_price(_num(r, 'median_price'))}</td>\n"
            f"        <td>{fmt_price(_num(r, 'p90'))}</td>\n"
            f"        <td{p50_cls}>{p50:.1f}%</td>\n"
            f"        <td{p30_cls}>{p30:.1f}%</td>\n"
            f"      </tr>"
        )
    return "\n".join(rows) + "\n"


def main() -> None:
    tickers = load_core_tickers()
    if not tickers:
        print(f"No tickers in {CORE_TXT}", file=sys.stderr)
        sys.exit(2)
    doc = HTML.read_text(encoding="utf-8")
    scen_by = load_csv_index(SCEN)
    risk_by = load_csv_index(RISK)
    mc_by = load_csv_index(MC)

    doc = patch_tbody_by_class(doc, "scenario-model-table", build_scenario_rows(tickers, scen_by))
    doc = restore_print_risk_def_table(doc)
    doc = patch_tbody_scroll_data_after_marker(
        doc,
        "risk-metrics",
        build_risk_rows(tickers, risk_by),
        header_hint="<th>Beta</th>",
        end_marker_id="dcf-sensitivity",
    )
    doc = patch_tbody_scroll_data_after_marker(
        doc,
        "monte-carlo",
        build_mc_rows(tickers, mc_by),
        header_hint="<th>Current</th>",
        end_marker_id="decide",
    )

    note = (
        '<p class="muted fi-value-refresh-note">Decide shortlist model tables refresh on each '
        "<code>refresh_watchlists.sh</code> run (core tickers only).</p>"
    )
    if "fi-value-refresh-note" not in doc:
        doc = doc.replace(
            '<section id="value">\n      <h2>Value</h2>',
            '<section id="value">\n      <h2>Value</h2>\n      ' + note,
            1,
        )

    HTML.write_text(doc, encoding="utf-8")
    print(f"Patched Value tables for {len(tickers)} tickers → {HTML}")


if __name__ == "__main__":
    main()
