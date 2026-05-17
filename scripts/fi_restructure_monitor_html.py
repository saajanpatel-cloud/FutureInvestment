#!/usr/bin/env python3
"""Unify Monitor: drop legacy aggregate section, promote per-ticker deep-dive before appendix."""
from __future__ import annotations

import re

from fi_embed_core import HTML, load_core_tickers

LEGACY_MONITOR = re.compile(
    r"\s*<section id=\"monitor\">\s*<h2>Monitor</h2>[\s\S]*?"
    r"<h3>Monitoring triggers</h3>[\s\S]*?</section>\s*",
    re.MULTILINE,
)
DEEP_DIVE_SECTION = re.compile(
    r"<section id=\"stock-deep-dive\">[\s\S]*?</section>\s*",
    re.MULTILINE,
)
STOCK_NAV = re.compile(
    r"\s*<a href=\"#stock-deep-dive\">Stock Deep-Dive</a>\s*",
    re.I,
)
PRINT_TOC_DD = re.compile(
    r"\s*<li><a href=\"#stock-deep-dive\">Stock deep-dive</a></li>\s*",
    re.I,
)


def main() -> None:
    doc = HTML.read_text(encoding="utf-8")
    n_core = len(load_core_tickers())
    changed = False

    if STOCK_NAV.search(doc):
        doc = STOCK_NAV.sub("\n", doc, count=1)
        changed = True
    if PRINT_TOC_DD.search(doc):
        doc = PRINT_TOC_DD.sub("\n", doc, count=1)
        changed = True

    dd_match = DEEP_DIVE_SECTION.search(doc)
    if dd_match:
        block = dd_match.group(0)
        block = block.replace('id="stock-deep-dive"', 'id="monitor"', 1)
        block = block.replace("<h2>Stock Deep-Dive</h2>", "<h2>Monitor</h2>", 1)
        doc = DEEP_DIVE_SECTION.sub("", doc, count=1)
        doc = doc.replace('<section id="appendix">', block + "\n\n    <section id=\"appendix\">", 1)
        changed = True

    if LEGACY_MONITOR.search(doc):
        doc = LEGACY_MONITOR.sub("\n", doc, count=1)
        changed = True

    # Tail section still at end (id may already be monitor)
    tail_pat = re.compile(
        r"(<section id=\"monitor\">\s*<h2>Monitor</h2>[\s\S]*?</section>)\s*</main>",
        re.MULTILINE,
    )
    m = tail_pat.search(doc)
    if m and doc.find(m.group(1)) > doc.find('<section id="appendix">'):
        block = m.group(1)
        doc = tail_pat.sub("</main>", doc, count=1)
        if block not in doc.split('<section id="appendix">')[0]:
            doc = doc.replace('<section id="appendix">', block + "\n\n    <section id=\"appendix\">", 1)
        changed = True

    doc = doc.replace("#stock-deep-dive", "#monitor")
    doc = doc.replace("stock-deep-dive", "monitor")

    dup = (
        '<p class="muted"><strong>Full thesis, market context, and kill criteria</strong> '
        'for each name are in <a href="#monitor">Monitor</a> '
        "(select ticker or use Deep dive links in the table).</p>"
    )
    while doc.count(dup) > 1:
        doc = doc.replace(dup, "", 1)
        changed = True

    purpose = re.search(
        r'<p class="section-purpose">Pick any shortlisted company[\s\S]*?</p>',
        doc,
    )
    if purpose:
        new_p = (
            f'<p class="section-purpose"><strong>What this is.</strong> Per-ticker brief: narrative, '
            f"models with explanations, Finnhub headlines. Core shortlist ({n_core} names) has full valuation; "
            "other universe names show a lighter stub.</p>"
        )
        if purpose.group(0) != new_p:
            doc = doc.replace(purpose.group(0), new_p, 1)
            changed = True

    HTML.write_text(doc, encoding="utf-8")
    status = "restructured" if changed else "already unified"
    print(f"{status} {HTML}")


if __name__ == "__main__":
    main()
