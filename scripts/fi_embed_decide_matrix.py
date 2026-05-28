#!/usr/bin/env python3
"""
Replace Decide matrix thead/tbody in SINGLE_SCREEN_REPORT.html.

Rows: composite shortlist, separator, portfolio-only holdings.
Columns: rubric, scenario, MC, historic risk (no verdict prose column).

Not investment advice.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from fi_embed_core import fmt_pct
from fi_embed_decide_data import (
    build_data_row,
    build_separator_row,
    load_csv_index,
    load_manifest_short_theme,
    load_rubric,
    rubric_total,
)
from fi_portfolio_tickers import load_shortlist, portfolio_only

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
HTML = W / "SINGLE_SCREEN_REPORT.html"
SC_RES = W / "scenario_results.csv"
MC_RES = W / "monte_carlo_results.csv"
RISK = W / "risk_metrics.csv"

DECIDE_COLS = 14

THEAD = f"""          <thead>
            <tr>
              <th rowspan="2">Ticker</th>
              <th rowspan="2">Theme</th>
              <th rowspan="2">Rubric<br /><small>/30</small></th>
              <th colspan="2" style="text-align:center;border-bottom:2px solid var(--accent);">Scenario model</th>
              <th colspan="3" style="text-align:center;border-bottom:2px solid #a78bfa;">Monte Carlo</th>
              <th colspan="6" style="text-align:center;border-bottom:2px solid var(--warn);">Historic risk (2y)</th>
            </tr>
            <tr>
              <th>Wtd upside</th>
              <th>Wtd price</th>
              <th>Median up</th>
              <th>P(50%&uarr;)</th>
              <th>P(30%&darr;)</th>
              <th>Beta</th>
              <th>Ann. vol</th>
              <th>1Y return</th>
              <th>Sharpe</th>
              <th>Max DD</th>
              <th>SPY corr</th>
            </tr>
          </thead>
"""


def build_tbody(
    tickers: list[str],
    rub_by: dict,
    theme_by: dict,
    sc_by: dict,
    mc_by: dict,
    rk_by: dict,
) -> str:
    lines: list[str] = []
    for t in tickers:
        lines.append(build_data_row(t, rub_by, theme_by, sc_by, mc_by, rk_by))
    return "\n".join(lines) + "\n"


def main() -> int:
    shortlist = load_shortlist()
    extra = portfolio_only()
    if not shortlist and not extra:
        print("Empty shortlist and portfolio", file=sys.stderr)
        return 2

    rub_by = load_rubric()
    theme_by = load_manifest_short_theme()
    sc_by = load_csv_index(SC_RES, "ticker")
    mc_by = load_csv_index(MC_RES, "ticker")
    rk_by = load_csv_index(RISK, "ticker")

    parts: list[str] = []
    if shortlist:
        parts.append(build_tbody(shortlist, rub_by, theme_by, sc_by, mc_by, rk_by))
    if extra:
        parts.append(build_separator_row(DECIDE_COLS, len(extra)))
        parts.append(build_tbody(extra, rub_by, theme_by, sc_by, mc_by, rk_by))
    tbody = "".join(parts)

    text = HTML.read_text(encoding="utf-8")
    pat = re.compile(
        r'<table class="decide-matrix print-table-rubric">\s*<thead>[\s\S]*?</thead>\s*<tbody>\s*\n'
        r"[\s\S]*?"
        r"\s*</tbody>\s*\n\s*</table>",
        re.MULTILINE,
    )
    replacement = (
        f'<table class="decide-matrix print-table-rubric">\n{THEAD}\n          <tbody>\n\n'
        f"{tbody}"
        f"          </tbody>\n        </table>"
    )
    new_text, n = pat.subn(replacement, text, count=1)
    if n != 1:
        print("Could not find decide-matrix table", file=sys.stderr)
        return 2

    HTML.write_text(new_text, encoding="utf-8")
    print(
        f"Patched Decide matrix ({len(shortlist)} shortlist + {len(extra)} portfolio) → {HTML}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
