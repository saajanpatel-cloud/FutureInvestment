#!/usr/bin/env python3
"""
Insert <p class="dcf-so-what muted">…</p> under each DCF table in HTML exports.

Reads upside cells from research/watchlists/dcf_sensitivity.csv (same ordering as
fi_dcf_sensitivity.py). Logic mirrors dcf_so_what_inner_html in fi_dcf_sensitivity.py —
keep both in sync when changing copy or heuristics.

Usage:
  python3 scripts/inject_dcf_so_what_html.py \
    --csv research/watchlists/dcf_sensitivity.csv \
    research/watchlists/SINGLE_SCREEN_REPORT.html \
    research/watchlists/dcf_sensitivity_fragment.html
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path


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


def dcf_so_what_paragraph_html(grid: list[list[dict]], indent: str = "    ") -> str:
    return f'{indent}<p class="dcf-so-what muted">{dcf_so_what_inner_html(grid)}</p>\n'


def load_paragraphs(csv_path: Path) -> dict[str, str]:
    by: dict[str, list[float]] = defaultdict(list)
    with csv_path.open(newline="") as f:
        for row in csv.DictReader(f):
            by[row["ticker"]].append(float(row["upside_pct"]))
    out: dict[str, str] = {}
    for t, ups in by.items():
        if len(ups) != 25:
            print(f"skip {t}: expected 25 cells, got {len(ups)}", file=sys.stderr)
            continue
        grid = [[{"upside_pct": ups[i + j]} for j in range(5)] for i in range(0, 25, 5)]
        out[t] = dcf_so_what_paragraph_html(grid)
    return out


_BLOCK = re.compile(
    r"(<details class=\"theme-card\">\s*\n"
    r"\s*<summary><strong>([A-Z0-9][A-Z0-9.\-]*)</strong>[\s\S]*?"
    r"</table>\s*\n)"
    r"(\s*</div>\s*\n\s*</details>)",
    re.MULTILINE,
)


def inject_into_html(html: str, paras: dict[str, str]) -> tuple[str, int]:
    """Return (new_html, n_inserted). Skips blocks that already contain dcf-so-what."""

    def repl(m: re.Match[str]) -> str:
        ticker = m.group(2)
        if "dcf-so-what" in m.group(0):
            return m.group(0)
        p = paras.get(ticker)
        if not p:
            return m.group(0)
        return m.group(1) + p + m.group(3)

    new_html, n = _BLOCK.subn(repl, html)
    return new_html, n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--csv",
        type=Path,
        default=Path("research/watchlists/dcf_sensitivity.csv"),
        help="CSV from fi_dcf_sensitivity.py",
    )
    ap.add_argument("html_files", nargs="+", type=Path, help="HTML files to patch in place")
    args = ap.parse_args()
    paras = load_paragraphs(args.csv)
    if not paras:
        print("No paragraphs built from CSV.", file=sys.stderr)
        sys.exit(1)
    for path in args.html_files:
        text = path.read_text(encoding="utf-8")
        new_text, n = inject_into_html(text, paras)
        if n == 0:
            print(f"{path}: no blocks matched (already injected or different markup?)", file=sys.stderr)
            continue
        path.write_text(new_text, encoding="utf-8")
        print(f"{path}: inserted {n} DCF so-what line(s)")


if __name__ == "__main__":
    main()
