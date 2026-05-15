#!/usr/bin/env python3
"""
Emit HTML <tr> rows for SINGLE_SCREEN_REPORT.html universe table from a fi_snapshot CSV
plus research/watchlists/universe_manifest.csv (theme + linkage).

Usage (from Projects/FutureInvestment):
  python scripts/fi_snapshot.py --manifest research/watchlists/universe_manifest.csv \\
    --csv research/watchlists/rubric_universe.csv --md research/watchlists/rubric_universe.md
  python scripts/fi_universe_html_rows.py \\
    --manifest research/watchlists/universe_manifest.csv \\
    --csv research/watchlists/rubric_universe.csv \\
    > research/watchlists/_universe_table_rows.inc.html

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

from fi_manifest import fmt_mcap, fmt_num, load_manifest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "research" / "watchlists" / "universe_manifest.csv"


def row_html(
    slug: str,
    theme_label: str,
    link: str,
    r: dict[str, str],
) -> str:
    t = r["ticker"].strip().upper()
    sec = r.get("sec_company_search_url") or ""
    search_blob = (
        f"{t} {r.get('short_name', '')} {slug} {theme_label} {link} {r.get('sector', '')} {r.get('industry', '')}"
    ).lower()
    parts = [
        f'            <tr class="universe-row" data-theme="{html.escape(slug)}" data-search="{html.escape(search_blob)}">',
        f"              <td>{html.escape(theme_label)}</td>",
        f"              <td><strong>{html.escape(t)}</strong></td>",
        f"              <td>{html.escape(r.get('short_name', '') or '')}</td>",
        f"              <td>{html.escape(link)}</td>",
        f"              <td>{html.escape(r.get('exchange', '') or '')}</td>",
        f"              <td>{html.escape(r.get('sector', '') or '')}</td>",
        f"              <td>{fmt_mcap(r.get('market_cap', '') or '')}</td>",
        f"              <td>{fmt_num(r.get('trailing_pe'))}</td>",
        f"              <td>{fmt_num(r.get('forward_pe'))}</td>",
        f"              <td>{fmt_num(r.get('revenue_growth'))}</td>",
        f"              <td>{fmt_num(r.get('last_close_5d'))}</td>",
        f'              <td><a href="{html.escape(sec)}">SEC</a></td>',
        "            </tr>",
    ]
    return "\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="universe_manifest.csv (default: research/watchlists/universe_manifest.csv)",
    )
    ap.add_argument("--csv", required=True, type=Path, help="Path to fi_snapshot CSV")
    args = ap.parse_args()

    manifest_path = args.manifest.resolve()
    if not manifest_path.is_file():
        print(f"Manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(2)

    ordered = load_manifest(manifest_path)
    snap_rows = list(csv.DictReader(args.csv.open(encoding="utf-8", newline="")))
    by_ticker = {r["ticker"].strip().upper(): r for r in snap_rows}

    lines: list[str] = []
    for m in ordered:
        t = m["ticker"]
        r = by_ticker.get(t)
        if not r:
            print(f"warning: no snapshot row for manifest ticker {t}", file=sys.stderr)
            continue
        lines.append(
            row_html(
                m["theme_slug"],
                m["theme_label"],
                m["linkage_one_liner"],
                r,
            )
        )
    print("\n".join(lines))


if __name__ == "__main__":
    main()
