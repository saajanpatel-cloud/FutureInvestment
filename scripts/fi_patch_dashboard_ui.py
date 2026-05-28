#!/usr/bin/env python3
"""
One-time-safe patches to SINGLE_SCREEN_REPORT.html for simplified dashboard UI.

Hides Research/Value, updates nav/TOC/intro, print CSS for Decide separator and appendix.
Re-run is idempotent.

Not investment advice.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from fi_embed_core import HTML

APPENDIX_B_PLACEHOLDER = """
    <section id="appendix-company-research" class="fi-appendix-research-pdf" aria-label="Company research appendix">
      <h2>Appendix B — Company research</h2>
      <p class="muted">One page per name (composite shortlist, then personal holdings). Regenerated on refresh.</p>
      <div id="appendix-company-research-pages"><!-- FI_APPENDIX_TICKER_PAGES --></div>
    </section>
"""


def patch_nav(doc: str) -> str:
    doc = doc.replace(
        '        <a href="#research">Research</a>\n        <a href="#value">Value</a>\n        ',
        "",
    )
    doc = doc.replace(
        '        <li><a href="#research">Research — adversarial reviews</a></li>\n'
        '        <li><a href="#value">Valuation &amp; risk models</a></li>\n',
        "",
    )
    if 'href="#my-holdings"' not in doc:
        doc = doc.replace(
            '        <li><a href="#decide">Decide — model reconciliation</a></li>\n',
            '        <li><a href="#decide">Decide — model reconciliation</a></li>\n'
            '        <li><a href="#my-holdings">Personal holdings (in Decide)</a></li>\n',
            1,
        )
    doc = doc.replace(
        '        <li><a href="#appendix">Appendix</a></li>\n',
        '        <li><a href="#appendix">Appendix — methodology</a></li>\n',
        1,
    )
    if "Appendix B — Company research (PDF; one page per name)" not in doc:
        doc = doc.replace(
            '        <li><a href="#appendix">Appendix — methodology</a></li>\n',
            '        <li><a href="#appendix">Appendix — methodology</a></li>\n'
            '        <li>Appendix B — Company research (PDF; one page per name)</li>\n',
            1,
        )
    if 'href="#my-holdings"' not in doc.split("</nav>", 1)[0]:
        doc = doc.replace(
            '        <a href="#decide">Decide</a>\n',
            '        <a href="#decide">Decide</a>\n        <a href="#my-holdings">My holdings</a>\n',
            1,
        )
    # De-duplicate print TOC rows that can appear after repeated refreshes.
    doc = re.sub(
        r'(\s*<li><a href="#my-holdings">Personal holdings \(in Decide\)</a></li>\n)+',
        '        <li><a href="#my-holdings">Personal holdings (in Decide)</a></li>\n',
        doc,
    )
    return doc


def patch_hidden_sections(doc: str) -> str:
    for sid in ("research", "value"):
        pat = re.compile(rf'(<section id="{sid}")>', re.IGNORECASE)
        doc = pat.sub(rf'\1 class="fi-section-hidden">', doc, count=1)
    return doc


def patch_intro(doc: str) -> str:
    old = (
        "Sections follow one pipeline: <strong>Discover</strong> (goals and weights), "
        "<strong>Screen</strong> (universe and shortlist), <strong>Research</strong> (adversarial reviews), "
        "<strong>Value</strong> (scenarios, DCF, risk metrics, Monte Carlo), <strong>Decide</strong> (reconciliation), "
        "then <strong>Monitor</strong> in the live HTML"
    )
    new = (
        "Sections follow one pipeline: <strong>Discover</strong> (goals and weights), "
        "<strong>Screen</strong> (universe and shortlist), <strong>Decide</strong> (models + historic risk in one table), "
        "then <strong>Stock deep dive</strong> in the live HTML (charts and full narrative). "
        "The PDF adds <strong>Appendix B</strong> — one research page per name"
    )
    return doc.replace(old, new, 1)


def patch_css(doc: str) -> str:
    block = """
    .fi-section-hidden { display: none !important; }
    #decide tr.decide-portfolio-separator td {
      border-top: 3px solid var(--accent);
      padding: 0.75rem 0.5rem;
      font-size: 0.95rem;
      background: var(--panel);
    }
    #my-holdings { scroll-margin-top: 4rem; }
    .fi-appendix-research-pdf { display: none !important; margin-top: 2rem; }
"""
    if ".fi-appendix-research-pdf { display: none !important;" in doc:
        return doc
    return doc.replace("</style>", block + "\n  </style>", 1)


def patch_print_css(doc: str) -> str:
    additions = """
      /* Unified PDF typography */
      body {
        font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif !important;
        font-size: 9.25pt !important;
        line-height: 1.36 !important;
      }
      main > section,
      nav.print-toc,
      #appendix-company-research {
        font-size: 9.25pt !important;
        line-height: 1.36 !important;
      }
      main > section > h2,
      #appendix-company-research > h2 {
        font-size: 12pt !important;
        line-height: 1.2 !important;
        font-weight: 600 !important;
      }
      main > section h3,
      #appendix-company-research h3 {
        font-size: 9.6pt !important;
        line-height: 1.24 !important;
        font-weight: 600 !important;
      }
      main > section h4,
      #appendix-company-research h4 {
        font-size: 9pt !important;
        line-height: 1.24 !important;
        font-weight: 600 !important;
      }
      main > section p,
      main > section li,
      #appendix-company-research p,
      #appendix-company-research li {
        font-size: 8.6pt !important;
        line-height: 1.34 !important;
      }
      main > section table,
      #appendix-company-research table {
        font-size: 7.8pt !important;
      }
      .fi-section-hidden { display: none !important; }
      #monitor { display: none !important; }
      #appendix-company-research { display: block !important; page-break-before: always; break-before: page; }
      .appendix-ticker-page {
        page-break-before: always;
        break-before: page;
        break-inside: avoid;
        page-break-inside: avoid;
        padding: 2.5mm 0;
        font-size: 8.2pt !important;
        line-height: 1.32;
      }
      .appendix-ticker-page h3 { font-size: 9.2pt !important; margin: 0 0 1.2mm 0; }
      .appendix-ticker-page p,
      .appendix-ticker-page ul {
        margin: 0.9mm 0 !important;
      }
      .appendix-ticker-page ul {
        padding-left: 3.5mm;
      }
      .appendix-chart-wrap {
        margin: 1.2mm 0 0.8mm !important;
      }
      .appendix-mini-chart {
        width: 100%;
        height: 22mm;
        display: block;
        margin-top: 0.9mm;
      }
      .appendix-ticker-page .growth-lens { font-size: 9pt; color: var(--muted); margin: 2mm 0; }
      #appendix-company-research-pages > .appendix-ticker-page:first-child {
        page-break-before: auto !important;
        break-before: auto !important;
      }
      main > section.fi-section-hidden,
      main > section:empty {
        display: none !important;
        page-break-before: auto !important;
        break-before: auto !important;
        page-break-after: auto !important;
        break-after: auto !important;
      }
      #executive-summary {
        background: var(--panel) !important;
        border: 1px solid var(--line) !important;
        border-radius: 10px !important;
        box-shadow: none !important;
        padding: 4mm 4.5mm !important;
      }
      #executive-summary .exec-body > * + * {
        margin-top: 2.4mm !important;
      }
      #executive-summary .exec-block {
        padding: 0 !important;
        margin: 2.2mm 0 !important;
      }
      #executive-summary table.exec-table {
        width: 100% !important;
        border-collapse: collapse !important;
        background: transparent !important;
        font-size: 7.8pt !important;
      }
      #executive-summary table.exec-table th,
      #executive-summary table.exec-table td {
        border-bottom: 1px solid var(--line) !important;
        padding: 1.1mm 1.2mm !important;
      }
      #executive-summary .exec-columns {
        display: grid !important;
        grid-template-columns: 1fr 1fr !important;
        gap: 2.2mm !important;
      }
      #appendix-company-research > h2,
      #appendix-company-research > p {
        page-break-after: avoid !important;
        break-after: avoid-page !important;
      }
      #appendix-company-research {
        background: var(--panel) !important;
        border: 1px solid var(--line) !important;
        border-radius: 10px !important;
        padding: 4mm 4.5mm !important;
      }
      .appendix-ticker-page {
        border: 1px solid var(--line) !important;
        border-radius: 8px !important;
        padding: 3mm 3.2mm !important;
      }
      .appendix-ticker-page p strong:first-child {
        font-weight: 600 !important;
      }
"""
    if "#appendix-company-research > h2," in doc:
        return doc
    return doc.replace("@media print {", "@media print {\n" + additions, 1)


def patch_appendix_placeholder(doc: str) -> str:
    if "appendix-company-research" in doc:
        return doc
    if "</main>" in doc:
        return doc.replace("</main>", APPENDIX_B_PLACEHOLDER + "\n    </main>", 1)
    return doc


def patch_decide_section_copy(doc: str) -> str:
    doc = doc.replace(
        "Model reconciliation for the core shortlist",
        "Model reconciliation — composite shortlist, then your personal holdings",
        1,
    )
    anchor = '<section id="decide">'
    if 'id="my-holdings"' not in doc:
        doc = doc.replace(
            anchor,
            '<span id="my-holdings" aria-hidden="true"></span>\n    ' + anchor,
            1,
        )
    return doc


def main() -> int:
    if not HTML.is_file():
        print(f"Missing {HTML}", file=sys.stderr)
        return 2
    doc = HTML.read_text(encoding="utf-8")
    doc = patch_nav(doc)
    doc = patch_hidden_sections(doc)
    doc = patch_intro(doc)
    doc = patch_css(doc)
    doc = patch_print_css(doc)
    doc = patch_appendix_placeholder(doc)
    doc = patch_decide_section_copy(doc)
    HTML.write_text(doc, encoding="utf-8")
    print(f"Patched dashboard UI shell → {HTML}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
