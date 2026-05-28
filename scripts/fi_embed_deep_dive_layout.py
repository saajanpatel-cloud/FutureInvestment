#!/usr/bin/env python3
"""Patch Monitor section copy/CSS and remove Quality Movers styles."""
from __future__ import annotations

import re

from fi_embed_core import HTML

DD_CSS = """
    .dd-meta-banner {
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem 0.6rem;
      margin: 0.5rem 0 1rem;
      padding: 0.5rem 0.75rem;
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 8px;
      font-size: 0.85rem;
    }
    .dd-pill {
      padding: 0.15rem 0.5rem;
      border-radius: 999px;
      background: var(--bg);
      border: 1px solid var(--line);
    }
    .dd-pill-warn { border-color: var(--warn); color: var(--warn); }
    .dd-research-status {
      font-size: 0.78rem;
      padding: 0.2rem 0.5rem;
      border-radius: 6px;
      margin-left: 0.5rem;
    }
    .dd-rs-ok { background: rgba(52,211,153,0.15); color: #34d399; }
    .dd-rs-warn { background: rgba(251,191,36,0.15); color: var(--warn); }
    .dd-narrative { margin-top: 1.5rem; border-top: 1px solid var(--line); padding-top: 1rem; }
    .dd-narrative-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 0.5rem;
    }
    .dd-narrative-section { margin: 1rem 0; }
    .dd-narrative-section h4 { margin: 0 0 0.35rem; font-size: 0.95rem; }
    .dd-narrative-section p { margin: 0.25rem 0; line-height: 1.45; }
    .dd-signals-sub { font-size: 0.88rem; margin: 0.6rem 0 0.25rem; }
    ul.dd-signals-bull li { color: #34d399; }
    ul.dd-signals-bear li { color: #f87171; }
    .dd-peer-table { width: 100%; margin: 0.75rem 0 1.5rem; font-size: 0.88rem; }
    .dd-peer-current { background: rgba(99,102,241,0.08); }
    .dd-print-btn {
      font-size: 0.85rem;
      padding: 0.35rem 0.75rem;
      border-radius: 6px;
      border: 1px solid var(--line);
      background: var(--card);
      cursor: pointer;
    }
    a.dd-jump { font-weight: 600; text-decoration: none; }
    a.dd-jump:hover { text-decoration: underline; }
    .dd-chart-explain {
      font-size: 0.9rem;
      line-height: 1.45;
      color: var(--muted);
      margin: 0.5rem 0 1rem;
      max-width: 52rem;
    }
    .dd-file-protocol-note {
      font-size: 0.88rem;
      color: var(--muted);
      margin: 0.35rem 0 0.5rem;
      padding: 0.45rem 0.65rem;
      border-left: 3px solid var(--accent);
      background: rgba(99,102,241,0.08);
    }
    .dd-news-scroll-hint { font-size: 0.82rem; margin: 0.25rem 0 0.35rem; }
    .dd-news-table-wrap {
      max-height: 6.5rem;
      overflow-y: auto;
      margin: 0.35rem 0 0.75rem;
      border: 1px solid var(--line);
      border-radius: 6px;
    }
    .dd-news-table { width: 100%; table-layout: fixed; font-size: 0.82rem; border-collapse: collapse; }
    .dd-peer-table { table-layout: fixed; }
    .dd-news-table td.dd-news-headline { word-break: break-word; }
    .dd-news-table th, .dd-news-table td {
      padding: 0.3rem 0.45rem;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }
    .dd-news-h4 { font-size: 0.9rem; margin: 0.75rem 0 0.25rem; }
    .dd-stale-warn {
      padding: 0.4rem 0.6rem;
      margin: 0.5rem 0;
      border-radius: 6px;
      background: rgba(251,191,36,0.12);
      border: 1px solid var(--warn);
      font-size: 0.85rem;
    }
    .dd-rubric-bars { margin: 0.5rem 0; }
    .dd-rubric-row {
      display: grid;
      grid-template-columns: 6rem 1fr 2.5rem;
      gap: 0.5rem;
      align-items: center;
      margin: 0.25rem 0;
      font-size: 0.85rem;
    }
    .dd-rubric-bar {
      height: 0.45rem;
      background: var(--line);
      border-radius: 4px;
      overflow: hidden;
    }
    .dd-rubric-fill { height: 100%; background: var(--accent); }
    .dd-nav-btn {
      font-size: 0.85rem;
      padding: 0.35rem 0.65rem;
      margin-left: 0.35rem;
      border-radius: 6px;
      border: 1px solid var(--line);
      background: var(--card);
      cursor: pointer;
    }
    .dd-links { margin: 0.35rem 0 0.75rem; font-size: 0.88rem; }
    .dd-earnings-chip { font-size: 0.88rem; margin: 0.25rem 0 0.75rem; }
    .dd-reconcile { font-size: 0.95rem; margin: 0.5rem 0 1rem; }
    .dd-block { margin: 1rem 0 1.25rem; }
    .dd-block h3 { margin: 0 0 0.5rem; font-size: 1rem; }
    @media (max-width: 720px) {
      .dd-block.dd-collapsible > h3 { cursor: pointer; }
      .dd-block.dd-collapsible .dd-collapse-body { display: none; }
      .dd-block.dd-collapsible.is-open .dd-collapse-body { display: block; }
    }
"""

PRINT_CSS = """
      body.dd-print-one-ticker main > section:not(#monitor),
      body.dd-print-one-ticker nav,
      body.dd-print-one-ticker .screen-only-dd-chart,
      body.dd-print-one-ticker .screen-only-dd-print,
      body.dd-print-one-ticker .dd-print-btn,
      body.dd-print-one-ticker .dd-nav-btn {
        display: none !important;
      }
      body.dd-print-one-ticker #monitor {
        display: block !important;
        page-break-before: auto;
      }
      body.dd-print-one-ticker .dd-chart-explain { display: block !important; }
"""


def remove_movers_css(doc: str) -> str:
    pat = re.compile(
        r"\n    \.shortlist-movers-scroll \{[\s\S]*?\n    \}\n",
        re.MULTILINE,
    )
    return pat.sub("\n", doc, count=1)


def remove_quality_movers_html(doc: str) -> str:
    return re.sub(
        r"<h4>Quality movers</h4>[\s\S]*?</table></div>\n?",
        "",
        doc,
        count=1,
    )


CHART_SCREEN_CSS = """
    #monitor .dd-chart-block {
      margin: 0.75rem 0 1.25rem;
    }
    #monitor #dd-tv-chart-container {
      display: block !important;
      width: 100%;
      min-height: 400px;
      height: 400px;
      visibility: visible !important;
      overflow: hidden;
    }
    #monitor #dd-tv-chart-container iframe {
      display: block !important;
      width: 100% !important;
      min-height: 400px !important;
      height: 400px !important;
      visibility: visible !important;
      border: 0;
    }
    .dd-chart-loading,
    .dd-chart-fallback {
      margin: 0;
      padding: 1.5rem;
      text-align: center;
      font-size: 0.9rem;
    }
    .dd-offline-chart {
      padding: 0.75rem 1rem 1rem;
      height: 100%;
      box-sizing: border-box;
    }
    .dd-offline-note {
      margin: 0 0 0.75rem;
      font-size: 0.82rem;
    }
    .dd-offline-track {
      position: relative;
      height: 120px;
      margin-top: 2.5rem;
      border-radius: 6px;
      background: linear-gradient(90deg, rgba(248,113,113,0.15), rgba(148,163,184,0.12), rgba(52,211,153,0.15));
    }
    .dd-offline-bar {
      position: absolute;
      left: 2%;
      right: 2%;
      top: 50%;
      height: 4px;
      margin-top: -2px;
      border-radius: 2px;
      background: var(--line);
    }
    .dd-offline-lbl {
      position: absolute;
      top: 0;
      transform: translateX(-50%);
      font-size: 0.72rem;
      white-space: nowrap;
      color: var(--muted);
    }
    .dd-offline-bear { color: #f87171; }
    .dd-offline-base { top: auto; bottom: 0; color: var(--text); font-weight: 600; }
    .dd-offline-bull { color: #34d399; }
    .dd-offline-spot {
      position: absolute;
      top: 50%;
      transform: translate(-50%, -50%);
      padding: 0.2rem 0.45rem;
      border-radius: 4px;
      background: var(--accent, #3b82f6);
      color: #fff;
      font-size: 0.78rem;
      font-weight: 600;
      z-index: 2;
    }
"""


def inject_dd_css(doc: str) -> str:
    if ".dd-news-table-wrap" not in doc:
        anchor = "    #monitor #dd-content .dcf-wrap .dcf-so-what {"
        if anchor not in doc:
            anchor = "    #monitor {"
        doc = doc.replace(anchor, DD_CSS + "\n" + anchor, 1)
    if "#monitor .dd-chart-block {" not in doc:
        anchor = "    #monitor #dd-content .dcf-wrap .dcf-so-what {"
        if anchor not in doc:
            anchor = "    #monitor {"
        doc = doc.replace(anchor, CHART_SCREEN_CSS + "\n" + anchor, 1)
    return doc


def inject_print_css(doc: str) -> str:
    if "body.dd-print-one-ticker .dd-chart-explain" in doc:
        return doc
    anchor = "      #monitor {"
    idx = doc.rfind(anchor)
    if idx < 0:
        return doc
    return doc[:idx] + PRINT_CSS + doc[idx:]


def patch_section_copy(doc: str) -> str:
    doc = doc.replace(
        "Select a stock to see all analysis in one view",
        "Select a stock for chart, models, Finnhub context, and executive brief",
    )
    old_purpose = (
        "Pick any shortlisted company to see its rubric scores, scenario model output, "
        "risk metrics, Monte Carlo distribution, and adversarial review combined into a single page."
    )
    new_purpose = (
        "Pick any core shortlist name for a full executive report with model charts and "
        "company-specific narrative. Re-run the pipeline to refresh prose and numbers."
    )
    doc = doc.replace(old_purpose, new_purpose)
    doc = doc.replace("#stock-deep-dive", "#monitor")
    doc = doc.replace("Stock Deep-Dive", "Monitor")
    doc = doc.replace("Stock deep-dive", "Monitor")
    return doc


def patch_proposed_table_css(doc: str) -> str:
    """No-op: column layout owned by fi_embed_shortlist_proposed.py (Tier column)."""
    return doc


def main() -> None:
    doc = HTML.read_text(encoding="utf-8")
    doc = remove_movers_css(doc)
    doc = remove_quality_movers_html(doc)
    doc = patch_proposed_table_css(doc)
    doc = inject_dd_css(doc)
    doc = inject_print_css(doc)
    doc = patch_section_copy(doc)
    HTML.write_text(doc, encoding="utf-8")
    print("Patched Monitor layout CSS")


if __name__ == "__main__":
    main()
