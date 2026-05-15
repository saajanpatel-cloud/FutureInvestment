#!/usr/bin/env python3
"""Rebuild #value DCF company grids from core tickers + dcf_sensitivity.csv."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Callable

from fi_embed_core import HTML, W, load_core_tickers, load_csv_index
from fi_patch_single_screen_dcf_compact import load_grids

ROOT = Path(__file__).resolve().parents[1]
DCF = W / "dcf_sensitivity.csv"
SCEN = W / "scenario_results.csv"
SCRIPTS = ROOT / "scripts"


def load_dcf_helpers():
    spec = importlib.util.spec_from_file_location(
        "fi_dcf_sensitivity", SCRIPTS / "fi_dcf_sensitivity.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load fi_dcf_sensitivity.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._render_dcf_table_html, mod.dcf_so_what_paragraph_html, mod._fmt_price


def summary_line(
    ticker: str, scen: dict[str, str], fmt_price: Callable[[float], str]
) -> str:
    company = (scen.get("company") or ticker).strip()
    price = float(scen.get("price") or 0)
    mt = (scen.get("metric_type") or "EPS").strip()
    cm = float(scen.get("current_metric") or 0)
    label = "Fwd EPS" if mt.upper() == "EPS" else mt
    return (
        f"<summary><strong>{ticker}</strong> — {company} "
        f"(current price {fmt_price(price)}, {label} {cm:.2f})</summary>"
    )


def build_details(
    ticker: str,
    grid: list[list[dict]],
    growth_rates: list[float],
    scen_by: dict[str, dict[str, str]],
    render,
    para,
    fmt_price,
) -> str:
    return (
        '  <details class="theme-card">\n'
        f"    {summary_line(ticker, scen_by.get(ticker, {}), fmt_price)}\n"
        '    <div class="scroll">\n'
        f"{render(grid, growth_rates)}"
        f"{para(grid)}"
        "    </div>\n"
        "  </details>\n"
    )


def _find_matching_div_close(s: str, open_end: int) -> int:
    """Index of the `</div>` that closes the div whose `>` ends at open_end-1 (depth 1)."""
    pos = open_end
    depth = 1
    while pos < len(s):
        i_div = s.find("<div", pos)
        i_close = s.find("</div>", pos)
        if i_close < 0:
            return -1
        if i_div >= 0 and i_div < i_close:
            depth += 1
            gt = s.find(">", i_div)
            if gt < 0:
                return -1
            pos = gt + 1
        else:
            depth -= 1
            if depth == 0:
                return i_close
            pos = i_close + len("</div>")
    return -1


def replace_grid_block(doc: str, css_class: str, inner: str) -> str:
    """Replace inner HTML between wrapper open and its matching close (ignores nested </div>)."""
    open_tag = f'<div class="dcf-company-grids {css_class}">'
    idx = doc.find(open_tag)
    if idx < 0:
        return doc
    after_gt = idx + len(open_tag)
    close_idx = _find_matching_div_close(doc, after_gt)
    if close_idx < 0:
        return doc
    return doc[:after_gt] + "\n" + inner + doc[close_idx:]


def main() -> int:
    tickers = load_core_tickers()
    if not tickers:
        print("No core tickers", file=sys.stderr)
        return 2
    grids = load_grids(DCF)
    if not grids:
        print(f"No DCF grids in {DCF}", file=sys.stderr)
        return 2

    render, para, fmt_price = load_dcf_helpers()
    scen_by = load_csv_index(SCEN)

    blocks: list[str] = []
    missing: list[str] = []
    for t in tickers:
        if t not in grids:
            missing.append(t)
            continue
        grid, gr = grids[t]
        blocks.append(build_details(t, grid, gr, scen_by, render, para, fmt_price))

    if missing:
        print(f"WARN: no DCF grid for {', '.join(missing)}", file=sys.stderr)

    first = blocks[:4]
    rest = blocks[4:]
    doc = HTML.read_text(encoding="utf-8")
    doc = replace_grid_block(doc, "dcf-grids-print-4", "".join(first))
    doc = replace_grid_block(doc, "dcf-grids-print-6", "".join(rest))
    HTML.write_text(doc, encoding="utf-8")
    print(f"Rebuilt DCF grids: {len(first)} print-4 + {len(rest)} print-6 → {HTML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
