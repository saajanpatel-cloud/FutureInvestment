#!/usr/bin/env python3
"""
Emit HTML <tr> rows for SINGLE_SCREEN_REPORT.html rubric table from rubric_scores.csv
joined to universe_manifest.csv for theme_slug and theme_label.

Usage:
  python scripts/fi_rubric_html_rows.py \\
    --manifest research/watchlists/universe_manifest.csv \\
    --scores research/watchlists/rubric_scores.csv \\
    > research/watchlists/_rubric_table_rows.inc.html

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

from fi_manifest import load_manifest, sort_manifest_rows
from fi_sort_manifest_order import load_company_names

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "research" / "watchlists" / "universe_manifest.csv"
DEFAULT_SCORES = ROOT / "research" / "watchlists" / "rubric_scores.csv"
DEFAULT_CORE_TICKERS = ROOT / "research" / "watchlists" / "report_core_tickers.txt"
DEFAULT_NAMES_CSV = ROOT / "research" / "watchlists" / "rubric_universe.csv"


def load_core_tickers(path: Path) -> set[str]:
    """Tickers aligned with Decide / Research downselection (PDF rubric subset)."""
    if not path.is_file():
        return set()
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line.upper())
    return out


def val_cell(v: str) -> str:
    s = (v or "").strip()
    if not s:
        return "—"
    return html.escape(s)


def parse_dim(s: str) -> int | None:
    t = (s or "").strip()
    if not t or t == "—":
        return None
    try:
        v = int(t)
        if 1 <= v <= 5:
            return v
    except ValueError:
        pass
    return None


def compute_total_int(sc: dict[str, str]) -> int | None:
    g = parse_dim(sc.get("growth", ""))
    m = parse_dim(sc.get("margins", ""))
    bs = parse_dim(sc.get("balance_sheet", ""))
    d = parse_dim(sc.get("durability", ""))
    tail = parse_dim(sc.get("tail_risks", ""))
    v = parse_dim(sc.get("valuation", ""))
    if any(x is None for x in (g, m, bs, d, tail, v)):
        return None
    return int(g + m + bs + d + v - tail)  # type: ignore


def compute_total(sc: dict[str, str]) -> str:
    """G + M + BS + D + V − Tail — same as enrich / shortlist selection."""
    tot = compute_total_int(sc)
    return str(tot) if tot is not None else "—"


def clean_note_display(note: str) -> str:
    n = (note or "").strip()
    for suf in ("; yfin — verify filings", "yfin — verify filings"):
        if n.endswith(suf):
            n = n[: -len(suf)].rstrip().rstrip(";").strip()
    return n


def dim_td(raw: str, *, inverted: bool = False) -> str:
    """Score cell with tint class. Tail risks: higher score = worse → invert tint (5→dim-1)."""
    v = parse_dim(raw)
    inner = val_cell(raw)
    if v is None:
        return f"<td>{inner}</td>"
    disp = (6 - v) if inverted else v
    disp = max(1, min(5, disp))
    return f'<td class="rubric-dim-{disp}">{inner}</td>'


def total_td(sc: dict[str, str]) -> str:
    tot_s = compute_total(sc)
    tot_i = compute_total_int(sc)
    inner = html.escape(tot_s)
    if tot_i is None:
        return f"<td>{inner}</td>"
    if tot_i >= 18:
        cls = "rubric-total-high"
    elif tot_i >= 14:
        cls = "rubric-total-mid"
    elif tot_i >= 11:
        cls = "rubric-total-low"
    else:
        cls = "rubric-total-vlow"
    return f'<td class="{cls}">{inner}</td>'


def note_tone_class(sc: dict[str, str], note: str, tot_i: int | None) -> str:
    tail_v = parse_dim(sc.get("tail_risks", ""))
    nl = (note or "").lower()
    if tot_i is not None and tot_i <= 10:
        return "rubric-note-bear"
    if tail_v is not None and tail_v >= 5:
        return "rubric-note-bear"
    if any(
        k in nl
        for k in (
            "revenue down",
            "operating margin -",
            "gross margin -",
            " net loss",
            "declining revenue",
            "margin -",
        )
    ):
        return "rubric-note-bear"
    if tot_i is not None and tot_i >= 18:
        return "rubric-note-bull"
    if tot_i is not None and tot_i >= 14 and "revenue up" in nl:
        return "rubric-note-bull"
    return "rubric-note-ok"


def note_td(sc: dict[str, str], note: str) -> str:
    tot_i = compute_total_int(sc)
    cls = note_tone_class(sc, note, tot_i)
    return f'<td class="{cls}">{html.escape(note)}</td>'


def row_html(slug: str, theme_label: str, sc: dict[str, str], core: set[str], sort_index: int) -> str:
    t = sc["ticker"].strip().upper()
    note = clean_note_display(sc.get("note", "") or "")
    core_attr = ' data-report-core="1"' if t in core else ""
    return (
        f'            <tr{core_attr} data-theme="{html.escape(slug)}" data-sort-index="{sort_index}">'
        f"<td>{html.escape(theme_label)}</td>"
        f"<td>{html.escape(t)}</td>"
        f"{dim_td(sc.get('growth', ''))}"
        f"{dim_td(sc.get('margins', ''))}"
        f"{dim_td(sc.get('balance_sheet', ''))}"
        f"{dim_td(sc.get('durability', ''))}"
        f"{dim_td(sc.get('tail_risks', ''), inverted=True)}"
        f"{dim_td(sc.get('valuation', ''))}"
        f"{total_td(sc)}"
        f"{note_td(sc, note)}"
        "</tr>"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--scores", type=Path, default=DEFAULT_SCORES)
    ap.add_argument(
        "--core-tickers",
        type=Path,
        default=DEFAULT_CORE_TICKERS,
        help="Optional file: tickers get data-report-core for PDF rubric subset (default path if file exists).",
    )
    args = ap.parse_args()

    manifest_path = args.manifest.resolve()
    scores_path = args.scores.resolve()
    for p in (manifest_path, scores_path):
        if not p.is_file():
            print(f"Missing file: {p}", file=sys.stderr)
            sys.exit(2)

    names = load_company_names(DEFAULT_NAMES_CSV)
    ordered = sort_manifest_rows(load_manifest(manifest_path), name_by_ticker=names)
    score_rows = list(csv.DictReader(scores_path.open(encoding="utf-8", newline="")))
    by_ticker = {r["ticker"].strip().upper(): r for r in score_rows}
    core = load_core_tickers(args.core_tickers.resolve())
    if not core and args.core_tickers.resolve().is_file():
        print("warning: report_core_tickers.txt is empty", file=sys.stderr)
    if not core and not args.core_tickers.resolve().is_file():
        print(
            f"warning: no {args.core_tickers} — rubric rows will lack data-report-core (PDF would hide entire rubric)",
            file=sys.stderr,
        )

    lines: list[str] = []
    for idx, m in enumerate(ordered):
        t = m["ticker"]
        sc = by_ticker.get(t)
        if not sc:
            print(f"warning: no rubric_scores row for {t}", file=sys.stderr)
            continue
        lines.append(row_html(m["theme_slug"], m["theme_label"], sc, core, idx))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
