#!/usr/bin/env python3
"""
Add data-report-core="1" to <tr> rows in SINGLE_SCREEN_REPORT.html rubric table
when the ticker appears in research/watchlists/report_core_tickers.txt.

Keeps the full rubric on screen; PDF print CSS hides rows without this attribute.

Usage:
  python3 scripts/fi_tag_rubric_report_core.py

Not investment advice.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "research" / "watchlists" / "SINGLE_SCREEN_REPORT.html"
TICKERS = ROOT / "research" / "watchlists" / "report_core_tickers.txt"


def load_core(path: Path) -> set[str]:
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line.upper())
    return out


def patch_rubric_tbody(html: str, core: set[str]) -> tuple[str, int]:
    pat = re.compile(
        r'(<table[^>]*\bid="rubric-table"[^>]*>[\s\S]*?<tbody>\s*\n)'
        r"([\s\S]*?)"
        r"(\s*</tbody>\s*\n\s*</table>)",
        re.MULTILINE,
    )
    m = pat.search(html)
    if not m:
        print("Could not find rubric-table tbody", file=sys.stderr)
        sys.exit(2)
    body = m.group(2)
    n = 0
    lines_out: list[str] = []
    for line in body.splitlines():
        orig = line
        if "<tr" in line and "data-theme=" in line:
            tm = re.search(r"<td>[^<]*</td>\s*<td>([A-Z0-9.\-]+)</td>", line)
            if tm:
                t = tm.group(1).upper()
                if t in core:
                    if "data-report-core" not in line:
                        line = line.replace("<tr data-theme=", '<tr data-report-core="1" data-theme=', 1)
                        n += 1
                else:
                    line = re.sub(r"\s*data-report-core=\"1\"", "", line)
        lines_out.append(line)
    new_body = "\n".join(lines_out)
    return pat.sub(r"\1" + new_body + r"\3", html, count=1), n


def main() -> None:
    if not TICKERS.is_file():
        print(f"Missing {TICKERS}", file=sys.stderr)
        sys.exit(2)
    core = load_core(TICKERS)
    if not core:
        print("No tickers in core file", file=sys.stderr)
        sys.exit(2)
    text = HTML.read_text(encoding="utf-8")
    new_text, n = patch_rubric_tbody(text, core)
    if new_text == text:
        print("No changes", file=sys.stderr)
        sys.exit(0)
    HTML.write_text(new_text, encoding="utf-8")
    print(f"Tagged {n} rubric rows with data-report-core (file: {HTML})")


if __name__ == "__main__":
    main()
