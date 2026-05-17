#!/usr/bin/env python3
"""Sync Industry Trends: theme-card badges, Fintech card, and print narrative row."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from fi_theme_targets import load_theme_weights

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "research" / "watchlists" / "SINGLE_SCREEN_REPORT.html"

SUMMARY_TO_SLUG: list[tuple[str, str]] = [
    ("AI infrastructure &amp; compute", "ai"),
    ("Energy transition &amp; grids", "energy"),
    ("Cybersecurity &amp; digital trust", "cyber"),
    ("Industrial automation &amp; robotics", "auto"),
    ("Health Tech", "health"),
    ("Fintech &amp; digital money", "fintech"),
    ("Quantum / frontier compute", "quantum"),
]

FINTECH_PRINT_ROW = """            <tr>
              <td>Fintech &amp; digital money ({pct}%)</td>
              <td>Payments rails, neobanks, exchanges, and financial market infrastructure — revenue tied to moving money, underwriting, or selling software to banks and merchants.</td>
              <td>Scaled payment networks and processors; neobanks with improving unit economics; exchanges, clearing, and market-data vendors with subscription or volume mix.</td>
              <td>Labelling any consumer app with a wallet as fintech without checking whether payments are material to revenue and margin.</td>
            </tr>
"""

QUANTUM_INSERT_ANCHOR = """      <details class="theme-card">
        <summary>Quantum / frontier compute <span class="tc-badge">"""


def fintech_card_html(pct: int) -> str:
    return f"""      <details class="theme-card">
        <summary>Fintech &amp; digital money <span class="tc-badge">{pct}%</span></summary>
        <div class="tc-body">
          <p class="tc-one-liner">Payments rails, digital banking, trading platforms, and financial market infrastructure.</p>
          <p>This sleeve covers companies whose revenue is tied to moving money, underwriting risk, or selling software to banks and merchants — not broad “tech” stories with a payments sidecar. Neobanks and BNPL names compete on unit economics and funding costs; exchanges and market-data vendors earn through volume and subscription mix; legacy processors and card networks scale on transaction counts. Banks and conglomerates appear here when the manifest tags them for payments, wealth, or market-structure exposure — always read the linkage line before treating them as pure fintech.</p>
          <ul>
            <li><strong>What drives demand:</strong> Digital wallet adoption; cross-border remittance; merchant acquiring growth; rate cycles affecting NIM and cash balances; regulatory clarity on crypto and BNPL.</li>
            <li><strong>Where value accrues:</strong> Scaled payment networks and processors (PYPL, FI); high-growth neobanks with improving credit (NU, SOFI); exchanges and clearing (ICE, CME); market data and ratings (SPGI, MCO, MSCI).</li>
            <li><strong>How to learn:</strong> Separate transaction growth from take-rate and credit losses. For banks, track NII vs fee income. For processors, read gross vs net revenue disclosure.</li>
            <li><strong>Common mistake:</strong> Labelling any consumer app with a wallet as fintech without checking whether payments are material to revenue and margin.</li>
          </ul>
          <div class="tc-tickers"><span class="pill">PYPL</span><span class="pill">NU</span><span class="pill">HOOD</span><span class="pill">SOFI</span><span class="pill">INTU</span><span class="pill">ICE</span><span class="pill">ADYEN</span><span class="pill">WISE</span></div>
        </div>
      </details>

"""


def industry_section(doc: str) -> tuple[int, int]:
    start = doc.find('<section id="industry-trends">')
    if start < 0:
        return -1, -1
    end = doc.find('<section id="screen-shortlist">', start)
    if end < 0:
        end = doc.find("</section>", start + 50)
    return start, end


def patch_badges(doc: str, weights: dict[str, float]) -> str:
    for title, slug in SUMMARY_TO_SLUG:
        if slug not in weights:
            continue
        pct = int(round(weights[slug] * 100))
        pat = re.compile(
            rf"(<summary>{re.escape(title)} <span class=\"tc-badge\">)[^<]*(</span></summary>)"
        )
        doc = pat.sub(rf"\g<1>{pct}%\2", doc, count=1)
    return doc


def fix_broken_fintech_nesting(doc: str) -> str:
    """Remove duplicate nested <details> around Fintech and ensure Quantum opens a card."""
    doc = re.sub(
        r"(<details class=\"theme-card\">\s*)<details class=\"theme-card\">\s*"
        r"(<summary>Fintech &amp; digital money)",
        r"\1\2",
        doc,
        count=1,
    )
    doc = re.sub(
        r"(</details>\s*)\n<summary>Quantum / frontier compute",
        r"\1\n\n      <details class=\"theme-card\">\n        <summary>Quantum / frontier compute",
        doc,
        count=1,
    )
    return doc


def ensure_fintech_card(doc: str, weights: dict[str, float]) -> str:
    start, end = industry_section(doc)
    if start < 0:
        print("industry-trends section not found", file=sys.stderr)
        return doc
    chunk = doc[start:end]
    if "summary>Fintech &amp; digital money" in chunk:
        return fix_broken_fintech_nesting(doc)
    pct = int(round(weights.get("fintech", 0.08) * 100))
    card = fintech_card_html(pct)
    anchor = QUANTUM_INSERT_ANCHOR
    pos = doc.find(anchor, start)
    if pos < 0 or pos > end:
        print("Quantum theme card anchor not found in industry-trends", file=sys.stderr)
        return doc
    return fix_broken_fintech_nesting(doc[:pos] + card + doc[pos:])


def ensure_fintech_print_row(doc: str, weights: dict[str, float]) -> str:
    pct = int(round(weights.get("fintech", 0.08) * 100))
    if f"Fintech &amp; digital money ({pct}%)" in doc:
        return doc
    row = FINTECH_PRINT_ROW.format(pct=pct)
    pat = re.compile(
        r"(<tr>\s*<td>Health Tech \(\d+%\)</td>[\s\S]*?</tr>\s*)"
        r"(<tr>\s*<td>Quantum \(\d+%\)</td>)",
        re.MULTILINE,
    )
    m = pat.search(doc)
    if not m:
        print("print-industry-narrative Health→Quantum anchor not found", file=sys.stderr)
        return doc
    return doc[: m.end(1)] + row + doc[m.start(2) :]


def main() -> int:
    weights = load_theme_weights()
    doc = HTML.read_text(encoding="utf-8")
    doc = patch_badges(doc, weights)
    doc = ensure_fintech_card(doc, weights)
    doc = ensure_fintech_print_row(doc, weights)
    HTML.write_text(doc, encoding="utf-8")
    print("Patched Industry Trends (Fintech card, badges, print row)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
