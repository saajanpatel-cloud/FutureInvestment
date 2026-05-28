#!/usr/bin/env python3
"""Keep Monitor as the single stock deep-dive section; remove legacy DRAFT duplicate."""
from __future__ import annotations

import re
import sys

from fi_embed_core import HTML

SECTION_ID = "draft-stock-deep-dive"


def remove_draft_section(doc: str) -> str:
    pat = re.compile(
        r'\n\s*<section id="draft-stock-deep-dive">[\s\S]*?</section>\s*',
        re.IGNORECASE,
    )
    return pat.sub("\n", doc, count=1)


def remove_draft_nav(doc: str) -> str:
    doc = doc.replace(
        f'        <a href="#monitor">Monitor</a>\n        <a href="#{SECTION_ID}">DRAFT Stock-Deep Dive</a>\n        <a href="#appendix">Appendix</a>',
        '        <a href="#monitor">Stock deep dive</a>\n        <a href="#appendix">Appendix</a>',
        1,
    )
    doc = doc.replace(
        f'        <li><a href="#monitor">Monitor</a></li>\n        <li><a href="#{SECTION_ID}">DRAFT Stock-Deep Dive</a></li>\n        <li><a href="#appendix">Appendix</a></li>',
        '        <li><a href="#monitor">Stock deep dive</a></li>\n        <li><a href="#appendix">Appendix</a></li>',
        1,
    )
    doc = re.sub(
        r'\s*<a href="#draft-stock-deep-dive">DRAFT Stock-Deep Dive</a>',
        "",
        doc,
    )
    doc = re.sub(
        r'\s*<li><a href="#draft-stock-deep-dive">DRAFT Stock-Deep Dive</a></li>',
        "",
        doc,
    )
    return doc


def patch_monitor_section_copy(doc: str) -> str:
    doc = doc.replace("<h2>Monitor</h2>", "<h2>Stock deep dive</h2>", 1)
    doc = doc.replace(
        "Select a stock for chart, models, Finnhub context, and executive brief",
        "Executive memo per name: thesis, valuation zones, scenario/risk/DCF, Finnhub, verdict",
        1,
    )
    old = (
        "Pick any universe name for a narrative-first brief: rubric, scenario/risk/DCF/Monte Carlo "
        "with explainers under each chart, Finnhub headlines, and thesis discipline. "
        "Core shortlist names get full models; others show a stub until selected onto the sleeve."
    )
    new = (
        "Pick any core shortlist name for a full executive report with model charts and "
        "company-specific narrative. Re-run the pipeline to refresh prose and numbers."
    )
    return doc.replace(old, new, 1)


def remove_draft_report_links(doc: str) -> str:
    return re.sub(r"\s*·\s*<a href=\"#draft-[^\"]+\">Draft report</a>", "", doc)


def main() -> int:
    if not HTML.is_file():
        print(f"Missing {HTML}", file=sys.stderr)
        return 2
    doc = HTML.read_text(encoding="utf-8")
    doc = remove_draft_section(doc)
    doc = remove_draft_nav(doc)
    doc = patch_monitor_section_copy(doc)
    doc = remove_draft_report_links(doc)
    HTML.write_text(doc, encoding="utf-8")
    print(f"Patched Monitor-only deep dive → {HTML}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
