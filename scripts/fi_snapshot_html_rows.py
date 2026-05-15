#!/usr/bin/env python3
"""
Emit HTML <tr> rows for SINGLE_SCREEN_REPORT.html #snapshot table from fi_snapshot CSV.
Rows follow universe_manifest.csv order when --manifest is passed.

Usage:
  python scripts/fi_snapshot_html_rows.py \\
    --manifest research/watchlists/universe_manifest.csv \\
    --csv research/watchlists/rubric_universe.csv \\
    > research/watchlists/_snapshot_table_rows.inc.html

Not investment advice.
"""
from __future__ import annotations

import argparse
import csv
import html
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from fi_manifest import fmt_mcap, fmt_num, manifest_ticker_order

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "research" / "watchlists" / "universe_manifest.csv"


def snapshot_row_html(r: dict[str, str]) -> str:
    t = r["ticker"].strip().upper()
    sec = r.get("sec_company_search_url") or ""
    mcap = r.get("market_cap", "") or ""
    mcap_disp = fmt_mcap(mcap)
    parts = [
        "            <tr>",
        f"              <td>{html.escape(t)}</td>",
        f"              <td>{html.escape(r.get('short_name', '') or '')}</td>",
        f"              <td>{html.escape(r.get('exchange', '') or '')}</td>",
        f"              <td>{html.escape(r.get('sector', '') or '')}</td>",
        f"              <td>{html.escape(r.get('industry', '') or '')}</td>",
        f"              <td>{html.escape(mcap_disp)}</td>",
        f"              <td>{fmt_num(r.get('trailing_pe'))}</td>",
        f"              <td>{fmt_num(r.get('forward_pe'))}</td>",
        f"              <td>{fmt_num(r.get('price_to_book'))}</td>",
        f"              <td>{fmt_num(r.get('revenue_growth'))}</td>",
        f"              <td>{fmt_num(r.get('last_close_5d'))}</td>",
        f'              <td><a href="{html.escape(sec)}">SEC</a></td>',
        "            </tr>",
    ]
    return "\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, type=Path, help="fi_snapshot CSV")
    ap.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Order tickers like manifest (default sleeve manifest)",
    )
    args = ap.parse_args()

    manifest_path = args.manifest.resolve()
    if not manifest_path.is_file():
        print(f"Manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(2)

    order = manifest_ticker_order(manifest_path)
    snap_rows = list(csv.DictReader(args.csv.open(encoding="utf-8", newline="")))
    by_ticker = {r["ticker"].strip().upper(): r for r in snap_rows}

    lines: list[str] = []
    for t in order:
        r = by_ticker.get(t)
        if not r:
            print(f"warning: no snapshot row for {t}", file=sys.stderr)
            continue
        lines.append(snapshot_row_html(r))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
