#!/usr/bin/env python3
"""
Replace Research rebuttal master table with core-shortlist rows from enrich JSON.

Not investment advice.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

from fi_embed_core import HTML, load_core_tickers


def sort_tickers_themed(tickers: list[str], theme_by: dict[str, str]) -> list[str]:
    def key(sym: str) -> tuple[str, str]:
        th = (theme_by.get(sym) or "Other").strip().lower()
        return (th, sym.upper())

    return sorted(tickers, key=key)

ROOT = Path(__file__).resolve().parents[1]
CORE_JSON = ROOT / "watchlist-ui" / "core-shortlist.json"
MAN = ROOT / "research" / "watchlists" / "universe_manifest.csv"


def load_manifest_theme() -> dict[str, str]:
    import csv

    out: dict[str, str] = {}
    with MAN.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = (r.get("ticker") or "").strip().upper()
            if not t:
                continue
            lbl = (r.get("theme_label") or r.get("theme_slug") or "Other").strip()
            if "—" in lbl:
                lbl = lbl.split("—")[0].strip()
            out[t] = lbl[:40]
    return out


def load_items() -> dict[str, dict]:
    doc = json.loads(CORE_JSON.read_text(encoding="utf-8"))
    return {
        (it.get("ticker") or "").strip().upper(): it
        for it in (doc.get("items") or [])
        if it.get("ticker")
    }


def split_bear_bullets(bear: str) -> list[str]:
    text = (bear or "").strip()
    if not text or text == "—":
        return ["Thesis risk — define after adversarial workshop."]
    parts = [p.strip() for p in text.replace(" · ", "|").split("|") if p.strip()]
    if not parts:
        parts = [text[:120]]
    return parts[:4]


def build_table(tickers: list[str], items: dict[str, dict], theme_by: dict[str, str]) -> str:
    by_theme: dict[str, list[str]] = {}
    for t in tickers:
        th = theme_by.get(t, "Other")
        by_theme.setdefault(th, []).append(t)

    rows: list[str] = []
    for theme in sorted(by_theme.keys()):
        rows.append(
            f'            <tr class="rebuttal-master-sector"><td colspan="3">{html.escape(theme)}</td></tr>'
        )
        for t in sorted(by_theme[theme]):
            it = items.get(t, {})
            bears = split_bear_bullets(it.get("qual_bear") or it.get("research_thesis") or "")
            reb_stub = (
                (it.get("qual_bull") or it.get("why_this_name") or "—").strip()
            )
            if len(reb_stub) > 200:
                reb_stub = reb_stub[:197] + "…"
            first = True
            for i, bear_pt in enumerate(bears):
                tick_cell = (
                    f'<td class="rebuttal-master-tick" rowspan="{len(bears)}">{html.escape(t)}</td>'
                    if first
                    else ""
                )
                first = False
                reb = reb_stub if i == 0 else "See bull case above; workshop per-risk rebuttals."
                rows.append(
                    f"            <tr>{tick_cell}"
                    f"<td>{html.escape(bear_pt[:140])}</td>"
                    f"<td>{html.escape(reb[:200])}</td></tr>"
                )
    return "\n".join(rows) + "\n"


def main() -> None:
    # Rebuttal master table was removed from SINGLE_SCREEN_REPORT.html; keep script as no-op for old docs / manual runs.
    print(
        "  ℹ fi_embed_rebuttal_core: skipped (rebuttal master no longer in report)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
