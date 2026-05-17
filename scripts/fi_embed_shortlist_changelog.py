#!/usr/bin/env python3
"""Embed shortlist changelog section into SINGLE_SCREEN_REPORT.html."""
from __future__ import annotations

import html
import json
import re
import sys

from fi_embed_core import CORE_JSON, HTML

MARK_S = "<!-- FI_SHORTLIST_CHANGELOG_START -->"
MARK_E = "<!-- FI_SHORTLIST_CHANGELOG_END -->"


def _cell(v: object) -> str:
    if v is None or v == "":
        return "—"
    return html.escape(str(v))


def _intro_paragraphs(_delta: dict) -> str:
    """Single source of truth for method copy (avoid hand-editing HTML)."""
    return (
        '<p class="muted">Shortlist = top ~60 by <strong>five-signal composite</strong> '
        "(scenario, rubric, risk, Monte Carlo, DCF percentiles; see "
        "<code>shortlist_weights.json</code> where composite mode applies), "
        "then <strong>theme caps</strong> to 20–28 names. "
        "<strong>Rubric alone does not decide adds or drops.</strong></p>"
    )


def build_html(delta: dict) -> str:
    intro = _intro_paragraphs(delta)

    if delta.get("baseline_established"):
        body = (
            intro
            + '<p class="muted">No prior snapshot — baseline established this refresh. '
            "Next run will show adds and drops.</p>"
        )
    else:
        prior = delta.get("prior_as_of") or "last refresh"
        sections: list[str] = [
            intro,
            f'<p class="muted"><strong>Changes since {html.escape(str(prior))}</strong></p>',
        ]
        added = delta.get("added") or []
        if added:
            rows = "".join(
                f"<tr><td><strong>{html.escape(r['ticker'])}</strong></td>"
                f"<td>{_cell(r.get('theme'))}</td>"
                f"<td>{_cell(r.get('composite_rank'))}</td>"
                f"<td>{_cell(r.get('pct_scenario'))}</td>"
                f"<td>{_cell(r.get('pct_rubric'))}</td>"
                f"<td>{_cell(r.get('pct_risk'))}</td>"
                f"<td>{_cell(r.get('pct_mc'))}</td>"
                f"<td>{_cell(r.get('pct_dcf'))}</td>"
                f"<td>{_cell(r.get('rubric_total'))}</td>"
                f"<td>{_cell(r.get('reason_label') or r.get('reason'))}</td></tr>"
                for r in added
            )
            sections.append(
                '<h4>Added</h4><div class="scroll"><table class="print-table-rubric">'
                "<thead><tr><th>Ticker</th><th>Theme</th><th>Composite #</th>"
                "<th>Scen %</th><th>Rub %</th><th>Risk %</th><th>MC %</th><th>DCF %</th>"
                "<th>Rubric</th><th>Why</th></tr></thead>"
                f"<tbody>{rows}</tbody></table></div>"
            )
        dropped = delta.get("dropped") or []
        if dropped:
            rows = "".join(
                f"<tr><td><strong>{html.escape(r['ticker'])}</strong></td>"
                f"<td>{_cell(r.get('reason_label') or r.get('reason'))}</td>"
                f"<td>{_cell(r.get('composite_rank'))}</td>"
                f"<td>{_cell(r.get('rubric_total'))}</td>"
                f"<td>{_cell(r.get('note'))}</td></tr>"
                for r in dropped
            )
            sections.append(
                '<h4>Dropped</h4><div class="scroll"><table class="print-table-rubric">'
                "<thead><tr><th>Ticker</th><th>Reason</th><th>Composite #</th>"
                "<th>Rubric</th><th>Note</th></tr></thead>"
                f"<tbody>{rows}</tbody></table></div>"
            )
        if len(sections) == 2:
            sections.append('<p class="muted">Shortlist unchanged vs prior snapshot.</p>')
        body = "\n".join(sections)

    return (
        f"{MARK_S}\n"
        '      <div id="shortlist-changelog" class="shortlist-changelog-wrap">\n'
        "      <h3>Shortlist changes (this refresh)</h3>\n"
        f"{body}\n"
        "      </div>\n"
        f"{MARK_E}"
    )


def main() -> None:
    if not CORE_JSON.is_file():
        sys.exit(2)
    doc = json.loads(CORE_JSON.read_text(encoding="utf-8"))
    delta = (doc.get("selection_memo") or {}).get("shortlist_delta") or {}
    block = build_html(delta)
    text = HTML.read_text(encoding="utf-8")
    if MARK_S in text and MARK_E in text:
        text = re.sub(
            re.escape(MARK_S) + r"[\s\S]*?" + re.escape(MARK_E),
            block,
            text,
            count=1,
        )
    else:
        needle = '      <div class="warn"><strong>Not advice.</strong>'
        text = text.replace(needle, block + "\n" + needle, 1)
    HTML.write_text(text, encoding="utf-8")
    print("Patched shortlist changelog section")


if __name__ == "__main__":
    main()
