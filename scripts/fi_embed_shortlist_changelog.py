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


def _mover_change_two_sentences(m: dict) -> str:
    """Exactly two sentences: (1) what moved vs prior snapshot, (2) how to read it for this refresh."""
    dr = m.get("delta_rubric")
    db = m.get("delta_borda")
    dy = m.get("delta_yoy_pct")
    ins = bool(m.get("in_shortlist"))
    db_n = float(db) if db is not None else None
    dr_n = int(dr) if dr is not None else None

    frag: list[str] = []
    if dr is not None and dr != 0:
        frag.append(f"scorecard total shifted by {dr:+d} point(s)")
    if db_n is not None and abs(db_n) >= 1.0:
        frag.append(f"combined rank score moved by {db_n:+.1f}")
    if dy is not None and abs(float(dy)) >= 1.0:
        frag.append(f"revenue YoY pace moved by {float(dy):+.1f} percentage points")

    if frag:
        s1 = (
            "Since the prior snapshot, the main signal changes for this ticker are "
            + ", ".join(frag)
            + "."
        )
    else:
        s1 = (
            "Since the prior snapshot, rank and scorecard inputs moved only modestly for this name."
        )

    if ins:
        if (db_n is not None and db_n < 0) or (dr_n is not None and dr_n < 0):
            s2 = (
                "It still sits on the Decide shortlist, but the drift argues for re-reading thesis, "
                "kill triggers, and scenario tables before changing conviction or size."
            )
        elif (db_n is not None and db_n > 0) or (dr_n is not None and dr_n > 0):
            s2 = (
                "It remains on the shortlist with stronger composite or scorecard signals than last run—"
                "treat that as a diligence nudge, not a timing signal by itself."
            )
        else:
            s2 = (
                "It remains on the shortlist; cross-check the rubric and models because net drift is mixed."
            )
    else:
        if db_n is not None and db_n < 0:
            s2 = (
                "It is off the current shortlist largely because combined ranking slipped versus peers under the same theme caps—"
                "decide whether that is a temporary cap squeeze or a thesis change before you write it off."
            )
        else:
            s2 = (
                "It is off the current shortlist this refresh because peer ordering, pool membership, or theme caps shifted—"
                "compare to cap_casualties in the selection memo if the name still matters strategically."
            )

    return f"{s1} {s2}"


def _quality_movers_table(movers: list[dict]) -> str:
    rows = "".join(
        f"<tr><td><strong>{html.escape(str(m['ticker']))}</strong></td>"
        f'<td class="mover-change-cell">{_cell(_mover_change_two_sentences(m))}</td>'
        f"<td>{'Yes' if m.get('in_shortlist') else 'No'}</td></tr>"
        for m in movers
    )
    return (
        "<h4>Quality movers</h4>"
        '<div class="shortlist-movers-scroll"><table class="print-table-rubric shortlist-movers-table">'
        '<thead><tr><th>Ticker</th><th>Change (this refresh)</th><th>On shortlist?</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
    )


def build_html(delta: dict) -> str:
    intro = _intro_paragraphs(delta)

    if delta.get("baseline_established"):
        body = (
            intro
            + '<p class="muted">No prior snapshot — baseline established this refresh. '
            "Next run will show adds, drops, and quality movers.</p>"
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
        movers = delta.get("quality_movers") or []
        if movers:
            sections.append(_quality_movers_table(movers))
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
