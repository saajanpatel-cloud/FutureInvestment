#!/usr/bin/env python3
"""Embed DRAFT Stock-Deep Dive CSS into SINGLE_SCREEN_REPORT.html."""
from __future__ import annotations

import re
import sys

from fi_embed_core import HTML

MARK_S = "/* FI_DRAFT_LAYOUT_START */"
MARK_E = "/* FI_DRAFT_LAYOUT_END */"

CSS = """
    #monitor { margin-top: 2rem; }
    .dd-pilot-banner {
      background: rgba(99,102,241,0.12);
      border: 1px solid var(--accent);
      border-radius: 8px;
      padding: 0.65rem 0.85rem;
      font-size: 0.9rem;
      margin: 0 0 1rem;
    }
    .dd-picker { margin-bottom: 1rem; }
    #monitor #dd-content { width: 100%; max-width: 100%; }
    .draft-report { max-width: none; line-height: 1.55; width: 100%; }
    .draft-report h3.draft-h3 {
      margin: 1.35rem 0 0.5rem;
      font-size: 1.05rem;
      border-bottom: 1px solid var(--line);
      padding-bottom: 0.25rem;
    }
    .draft-report p { margin: 0.45rem 0; }
    .draft-report h4.draft-h4 { margin: 0.75rem 0 0.35rem; font-size: 0.95rem; }
    .draft-source-pill { margin-left: 0.5rem; font-size: 0.78rem; }
    .draft-education { margin-top: 1rem; font-size: 0.85rem; }
    #monitor .dcf-wrap,
    #monitor .dcf-grid { width: 100%; max-width: 100%; }
    #monitor .dd-peer-table,
    #monitor .dd-news-table {
      width: 100%;
      table-layout: fixed;
    }
    #monitor .dd-news-table td.dd-news-headline {
      word-break: break-word;
    }
    .draft-self-check { display: none !important; }
    .draft-price-zones {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.75rem;
      margin: 1rem 0;
      padding: 0.85rem;
      background: rgba(99,102,241,0.06);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    @media (max-width: 640px) {
      .draft-price-zones { grid-template-columns: 1fr; }
    }
    .draft-zone-card strong { display: block; font-size: 0.88rem; margin-bottom: 0.25rem; }
    .draft-zone-card .draft-zone-range {
      font-size: 1.15rem;
      font-weight: 700;
      color: var(--accent);
    }
    .draft-zone-method { font-size: 0.82rem; color: var(--muted); margin-top: 0.75rem; grid-column: 1 / -1; }
    .draft-chart-block {
      margin: 1rem 0;
    }
    .draft-chart-block .draft-chart-print-note { display: none; }
    .draft-valuation-embed { margin: 1rem 0 1.5rem; }
    .draft-self-check {
      margin-top: 1.5rem;
      padding: 0.75rem;
      font-size: 0.88rem;
      color: var(--muted);
      border-left: 3px solid var(--warn);
      background: rgba(251,191,36,0.06);
    }
    .draft-risks-list { margin: 0.35rem 0 0.75rem 1.1rem; }
    .draft-debate { margin: 0.5rem 0; }
    .draft-debate-bull { color: #34d399; }
    .draft-debate-bear { color: #f87171; }
    .draft-verdict-rating {
      display: inline-block;
      font-weight: 700;
      padding: 0.2rem 0.55rem;
      border-radius: 4px;
      margin-bottom: 0.35rem;
    }
    .draft-verdict-buy { background: rgba(52,211,153,0.2); color: #34d399; }
    .draft-verdict-hold { background: rgba(251,191,36,0.2); color: var(--warn); }
    .draft-verdict-avoid { background: rgba(248,113,113,0.2); color: #f87171; }
    .draft-stub { padding: 1.5rem; color: var(--muted); border: 1px dashed var(--line); border-radius: 8px; }
    @media print {
      #monitor .draft-chart-block .screen-only-draft-chart { display: none !important; }
      #monitor .draft-chart-print-note { display: block !important; font-size: 9pt; color: #555; }
    }
"""


def main() -> int:
    if not HTML.is_file():
        print(f"Missing {HTML}", file=sys.stderr)
        return 2
    doc = HTML.read_text(encoding="utf-8")
    block = f"{MARK_S}\n{CSS}\n{MARK_E}\n"
    if MARK_S in doc and MARK_E in doc:
        doc = re.sub(re.escape(MARK_S) + r"[\s\S]*?" + re.escape(MARK_E), block.rstrip(), doc, count=1)
    else:
        doc = doc.replace("    /* ── Deep-dive layout ─────────────────────────────── */", block + "\n    /* ── Deep-dive layout ─────────────────────────────── */", 1)
    HTML.write_text(doc, encoding="utf-8")
    print(f"Patched DRAFT layout CSS → {HTML}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
