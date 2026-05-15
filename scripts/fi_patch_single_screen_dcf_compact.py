#!/usr/bin/env python3
"""
Replace legacy or compact DCF <table> blocks in SINGLE_SCREEN_REPORT.html with the
5×5 layout from fi_dcf_sensitivity.py — no yfinance fetch required.

Reads research/watchlists/dcf_sensitivity.csv (25 rows per ticker).

Usage (repo root):
  python3 scripts/fi_patch_single_screen_dcf_compact.py \\
    research/watchlists/dcf_sensitivity.csv \\
    research/watchlists/SINGLE_SCREEN_REPORT.html
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import sys
from collections import defaultdict
from pathlib import Path


def load_grids(csv_path: Path) -> dict[str, tuple[list[list[dict]], list[float]]]:
    by_ticker: dict[str, list[dict]] = defaultdict(list)
    with csv_path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = (r.get("ticker") or "").strip()
            if not t:
                continue
            by_ticker[t].append(
                {
                    "growth_rate": float(r["growth_rate"]),
                    "wacc": float(r["wacc"]),
                    "implied_price": float(r["implied_price"]),
                    "upside_pct": float(r["upside_pct"]),
                }
            )
    out: dict[str, tuple[list[list[dict]], list[float]]] = {}
    for t, cells in by_ticker.items():
        if len(cells) != 25:
            print(f"skip {t}: need 25 cells, got {len(cells)}", file=sys.stderr)
            continue
        gr = sorted({c["growth_rate"] for c in cells})
        wc = sorted({c["wacc"] for c in cells})
        if len(gr) != 5 or len(wc) != 5:
            print(f"skip {t}: non-5×5 ladder", file=sys.stderr)
            continue
        m = {(round(c["growth_rate"], 8), round(c["wacc"], 8)): c for c in cells}
        try:
            grid = [[m[(round(g, 8), round(w, 8))] for w in wc] for g in gr]
        except KeyError:
            print(f"skip {t}: ladder key mismatch", file=sys.stderr)
            continue
        out[t] = (grid, gr)
    return out


def load_dcf_helpers(scripts_dir: Path):
    spec = importlib.util.spec_from_file_location(
        "fi_dcf_sensitivity", scripts_dir / "fi_dcf_sensitivity.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load fi_dcf_sensitivity.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._render_dcf_table_html, mod.dcf_so_what_paragraph_html


def patch_html(html: str, grids: dict[str, tuple[list[list[dict]], list[float]]], render, para) -> tuple[str, int]:
    n = 0
    for ticker in sorted(grids.keys()):
        grid, growth_rates = grids[ticker]
        marker = f"<summary><strong>{ticker}</strong>"
        s = html.find(marker)
        if s < 0:
            continue
        sc = html.find('<div class="scroll">', s)
        if sc < 0:
            continue
        tb = html.find("<table", sc)
        if tb < 0:
            continue
        te = html.find("</table>", tb)
        if te < 0:
            continue
        te += len("</table>")
        pe_end = te
        p0 = html.find('<p class="dcf-so-what', te)
        if p0 >= 0 and p0 - te < 400:
            p1 = html.find("</p>", p0)
            if p1 > p0:
                pe_end = p1 + len("</p>")
        block = render(grid, growth_rates) + para(grid)
        html = html[:tb] + block + html[pe_end:]
        n += 1
    return html, n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv_path", type=Path)
    ap.add_argument("html_path", type=Path)
    args = ap.parse_args()

    root = args.csv_path.resolve().parents[2]
    scripts = root / "scripts"
    grids = load_grids(args.csv_path)
    if not grids:
        print("No valid ticker grids in CSV.", file=sys.stderr)
        return 2
    render, para = load_dcf_helpers(scripts)
    text = args.html_path.read_text(encoding="utf-8")
    new_text, total = patch_html(text, grids, render, para)
    if total == 0:
        print("No DCF tables patched (tickers in CSV not found in HTML?).", file=sys.stderr)
        return 1
    args.html_path.write_text(new_text, encoding="utf-8")
    print(f"Patched {total} DCF table block(s) → {args.html_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
