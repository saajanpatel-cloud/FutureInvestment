#!/usr/bin/env python3
"""Normalize PDF print CSS to one canonical override layer."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from fi_embed_core import HTML

MARK_S = "/* FI_CANONICAL_PRINT_OVERRIDES_START */"
MARK_E = "/* FI_CANONICAL_PRINT_OVERRIDES_END */"

CANONICAL = f"""
{MARK_S}
@media print {{
  /* Replace blanket section breaking with explicit section flow */
  main > section {{
    page-break-before: auto !important;
    break-before: auto !important;
  }}
  #introduction,
  #executive-summary,
  #discover,
  #industry-trends,
  #screen-shortlist,
  #decide,
  #appendix,
  #appendix-company-research {{
    page-break-before: always !important;
    break-before: page !important;
  }}
  .pdf-reading-guide,
  main > section:first-of-type {{
    page-break-before: auto !important;
    break-before: auto !important;
  }}

  /* Global type system */
  body {{
    font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif !important;
    font-size: 9pt !important;
    line-height: 1.3 !important;
  }}
  main > section {{
    padding: 1.8mm 0 2.2mm 0 !important;
    margin: 0 !important;
  }}
  main > section > h2 {{
    font-size: 11pt !important;
    font-weight: 700 !important;
    margin: 0 0 1.8mm 0 !important;
    padding-bottom: 1.2mm !important;
  }}
  main > section h3 {{
    font-size: 9.6pt !important;
    font-weight: 600 !important;
    margin: 2mm 0 1mm 0 !important;
  }}
  main > section h4 {{
    font-size: 8.9pt !important;
    font-weight: 600 !important;
    margin: 1.2mm 0 0.8mm 0 !important;
  }}
  main > section p,
  main > section li {{
    font-size: 8.7pt !important;
    line-height: 1.28 !important;
    margin: 0.8mm 0 !important;
  }}
  table {{
    font-size: 7.2pt !important;
  }}

  /* Avoid blank pages from empty/hidden sections */
  main > section.fi-section-hidden,
  main > section:empty {{
    display: none !important;
    page-break-before: auto !important;
    break-before: auto !important;
    page-break-after: auto !important;
    break-after: auto !important;
  }}
  #research,
  #value {{
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    overflow: hidden !important;
    margin: 0 !important;
    padding: 0 !important;
    border: 0 !important;
    page: auto !important;
  }}

  /* Executive summary should match report document style */
  #executive-summary {{
    display: block !important;
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding: 0 !important;
  }}
  #executive-summary .exec-lead p,
  #executive-summary .exec-meta,
  #executive-summary .exec-method {{
    margin: 0.8mm 0 !important;
  }}
  #executive-summary .exec-body > * + * {{
    margin-top: 1.6mm !important;
  }}
  #executive-summary .exec-columns {{
    display: grid !important;
    grid-template-columns: 1fr 1fr !important;
    gap: 3mm !important;
  }}
  #executive-summary table.exec-table {{
    font-size: 7.1pt !important;
  }}
  #executive-summary table.exec-table th,
  #executive-summary table.exec-table td {{
    padding: 0.65mm 0.8mm !important;
  }}

  /* Appendix B formatting aligned to report */
  #appendix-company-research {{
    display: block !important;
    page-break-before: always !important;
    break-before: page !important;
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding: 0 !important;
  }}
  #appendix-company-research > h2,
  #appendix-company-research > p {{
    page-break-after: avoid !important;
    break-after: avoid-page !important;
  }}
  #appendix-company-research-pages > .appendix-ticker-page:first-child {{
    page-break-before: auto !important;
    break-before: auto !important;
  }}
  .appendix-ticker-page {{
    page-break-before: always !important;
    break-before: page !important;
    page-break-inside: avoid !important;
    break-inside: avoid !important;
    border: 0.75pt solid var(--line) !important;
    border-radius: 8px !important;
    padding: 2.2mm 2.4mm !important;
    font-size: 8.1pt !important;
    line-height: 1.22 !important;
    min-height: 240mm !important;
    max-height: 246mm !important;
    overflow: hidden !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: space-between !important;
    gap: 1.2mm !important;
  }}
  .appendix-ticker-page h3 {{
    font-size: 9.1pt !important;
    margin: 0 0 1.4mm 0 !important;
  }}
  .appendix-ticker-page p,
  .appendix-ticker-page li {{
    font-size: 7.7pt !important;
    line-height: 1.2 !important;
    margin: 0.65mm 0 !important;
  }}
  .appendix-ticker-page ul {{
    margin: 0.7mm 0 0.9mm 0 !important;
    padding-left: 2.6mm !important;
  }}
  .appendix-mini-chart {{
    width: 100% !important;
    height: 14mm !important;
  }}

  /* Compact all card-like blocks for denser pages */
  .card,
  .theme-card,
  .adv-card,
  .warn,
  .meta-strip,
  .dd-meta-banner,
  .intro-explainer,
  .print-toc {{
    padding: 1.6mm 1.9mm !important;
    margin: 0.9mm 0 !important;
    border-radius: 6px !important;
  }}
}}
{MARK_E}
"""


def strip_draft_print(doc: str) -> str:
    pat = re.compile(
        r"(/\* FI_DRAFT_LAYOUT_START \*/[\s\S]*?)@media print \{[\s\S]*?\}\s*(/\* FI_DRAFT_LAYOUT_END \*/)",
        re.MULTILINE,
    )
    m = pat.search(doc)
    if not m:
        return doc
    return doc[: m.start()] + m.group(1) + "\n" + m.group(2) + doc[m.end() :]


def inject_canonical(doc: str) -> str:
    if MARK_S in doc and MARK_E in doc:
        return re.sub(re.escape(MARK_S) + r"[\s\S]*?" + re.escape(MARK_E), CANONICAL.strip(), doc, count=1)
    return doc.replace("</style>", "\n" + CANONICAL.strip() + "\n</style>", 1)


def strip_hidden_sections(doc: str) -> str:
    doc = re.sub(
        r'\n\s*<section id="research"[\s\S]*?</section>\n',
        "\n",
        doc,
        count=1,
        flags=re.IGNORECASE,
    )
    doc = re.sub(
        r'\n\s*<section id="value"[\s\S]*?</section>\n',
        "\n",
        doc,
        count=1,
        flags=re.IGNORECASE,
    )
    doc = re.sub(
        r'\n\s*<section id="monitor"[\s\S]*?</section>\n',
        "\n",
        doc,
        count=1,
        flags=re.IGNORECASE,
    )
    doc = re.sub(
        r'\n\s*<li><a href="#monitor">Stock deep dive</a></li>\s*',
        "\n",
        doc,
        count=1,
        flags=re.IGNORECASE,
    )
    return doc


def main() -> int:
    if not HTML.is_file():
        print(f"Missing {HTML}", file=sys.stderr)
        return 2
    doc = HTML.read_text(encoding="utf-8")
    doc = strip_hidden_sections(doc)
    doc = strip_draft_print(doc)
    doc = inject_canonical(doc)
    HTML.write_text(doc, encoding="utf-8")
    print(f"Normalized print CSS → {HTML}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
