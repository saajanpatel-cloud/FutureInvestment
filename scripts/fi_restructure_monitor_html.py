#!/usr/bin/env python3
"""Restructure SINGLE_SCREEN_REPORT: drop legacy #monitor, move per-ticker section before appendix."""
from __future__ import annotations

import re

from fi_embed_core import HTML, load_core_tickers


def main() -> None:
    doc = HTML.read_text(encoding="utf-8")
    n_core = len(load_core_tickers())

    doc = doc.replace("#stock-deep-dive", "#monitor")
    doc = doc.replace("stock-deep-dive", "monitor")
    doc = doc.replace('<a href="#monitor">Stock Deep-Dive</a>', '<a href="#monitor">Monitor</a>')
    doc = doc.replace("<li>Stock deep-dive</li>", "<li>Monitor</li>", 1) if "<li>Stock deep-dive</li>" in doc else None
    doc = re.sub(
        r"<li><a href=\"#monitor\">Stock deep-dive</a></li>",
        '<li><a href="#monitor">Monitor</a></li>',
        doc,
        count=1,
        flags=re.I,
    )

    # Remove legacy aggregate monitor (Finnhub tables + chart viewer)
    doc = re.sub(
        r"\s*<section id=\"monitor\">\s*<h2>Monitor</h2>[\s\S]*?"
        r"<h3>Monitoring triggers</h3>[\s\S]*?</section>\s*",
        "\n",
        doc,
        count=1,
    )

    # Extract per-ticker monitor section at end (may still be id=monitor after rename)
    tail_pat = re.compile(
        r"(<section id=\"monitor\">\s*<h2>Monitor</h2>[\s\S]*?</section>)\s*</main>",
        re.MULTILINE,
    )
    m = tail_pat.search(doc)
    if m and doc.find(m.group(1)) > doc.find('<section id="appendix">'):
        block = m.group(1)
        doc = tail_pat.sub("</main>", doc, count=1)
        doc = doc.replace('<section id="appendix">', block + "\n\n    <section id=\"appendix\">", 1)

    # Picker upgrade
    if "dd-prev" not in doc:
        doc = doc.replace(
            '<motion class="dd-picker">'.replace("motion", "div"),
            "",
        )
        old_picker = """      <div class="dd-picker">
        <label for="dd-ticker" style="font-weight:600;font-size:0.92rem;">Select stock:</label>
        <select id="dd-ticker">
          <option value="">Select a stock...</option>
        </select>
      </motion>
      <div id="dd-content"></div>""".replace("motion", "motion")
        new_picker = """      <div class="dd-picker-wrap">
        <motion class="dd-nav-btns">
          <button type="button" id="dd-prev" class="dd-nav-btn" aria-label="Previous ticker">← Prev</button>
          <button type="button" id="dd-next" class="dd-nav-btn" aria-label="Next ticker">Next →</button>
        </motion>
        <div class="dd-picker">
          <label for="dd-ticker" style="font-weight:600;font-size:0.92rem;">Select stock:</label>
          <select id="dd-ticker">
            <option value="">Select a stock...</option>
          </select>
        </div>
      </div>
      <motion id="dd-content"></motion>""".replace("motion", "div")
        if old_picker.replace("motion", "div") in doc:
            doc = doc.replace(old_picker.replace("motion", "motion"), new_picker.replace("motion", "div"))
        elif "dd-picker-wrap" not in doc:
            pass

    dup = (
        '<p class="muted"><strong>Full thesis, market context, and kill criteria</strong> '
        'for each name are in <a href="#monitor">Monitor</a> '
        "(select ticker or use Deep dive links in the table).</p>"
    )
    while doc.count(dup) > 1:
        doc = doc.replace(dup, "", 1)

    doc = doc.replace(
        "<strong>Reddit and X (directional only)</strong>",
        "<strong>Finnhub (market context)</strong>",
    )

    purpose_old = "Pick any shortlisted company to see its rubric scores"
    if purpose_old in doc:
        doc = doc.replace(
            re.search(
                r'<p class="section-purpose">Pick any shortlisted company[\s\S]*?</p>',
                doc,
            ).group(0)
            if re.search(r'<p class="section-purpose">Pick any shortlisted company[\s\S]*?</p>', doc)
            else "",
            f'<p class="section-purpose"><strong>What this is.</strong> Per-ticker brief: narrative, '
            f"models with explanations, Finnhub headlines. Core shortlist ({n_core} names) has full valuation; "
            "other universe names show a lighter stub.</p>",
            1,
        )

    HTML.write_text(doc, encoding="utf-8")
    print(f"Restructured {HTML}")


if __name__ == "__main__":
    main()
