#!/usr/bin/env python3
"""
Patch SINGLE_SCREEN_REPORT.html so the **Shortlist** table (table.proposed-shares)
and the **print-only** Decide research matrix track `report_core_tickers.txt`.

Run after `fi_select_shortlist_growth.py` + `fi_tag_rubric_report_core.py`, typically
via `scripts/refresh_watchlists.sh`.

Not investment advice.
"""
from __future__ import annotations

import csv
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

from fi_conviction_tier import tier_label
from fi_theme_targets import load_theme_weights

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "research" / "watchlists" / "SINGLE_SCREEN_REPORT.html"
CORE_TXT = ROOT / "research" / "watchlists" / "report_core_tickers.txt"
MAN = ROOT / "research" / "watchlists" / "universe_manifest.csv"
RU = ROOT / "research" / "watchlists" / "rubric_universe.csv"
RUB = ROOT / "research" / "watchlists" / "rubric_scores.csv"
CORE_JSON = ROOT / "watchlist-ui" / "core-shortlist.json"

CHANGELOG_MARK_S = "<!-- FI_SHORTLIST_CHANGELOG_START -->"
CHANGELOG_MARK_E = "<!-- FI_SHORTLIST_CHANGELOG_END -->"
CHANGELOG_PLACEHOLDER = "<!-- FI_CHANGELOG_SLOT_PLACEHOLDER -->"

FOOTNOTE_MARK = "<!-- FI_SHORTLIST_ALLOC_FOOTNOTE -->"

PROPOSED_HEAD = (
    "            <tr>\n"
    "              <th>Ticker</th>\n"
    "              <th>Company</th>\n"
    "              <th>Theme</th>\n"
    "              <th>Tier</th>\n"
    "              <th>~Alloc %</th>\n"
    "              <th>Deep dive</th>\n"
    "            </tr>"
)


def dd_link(ticker: str) -> str:
    return (
        f'<a href="#monitor" class="dd-jump" data-ticker="{html.escape(ticker)}">'
        "Deep dive</a>"
    )


def _detach_changelog(doc: str) -> tuple[str, str | None]:
    """Preserve changelog markup — regex patching tables must not consume this region."""
    i = doc.find(CHANGELOG_MARK_S)
    j = doc.find(CHANGELOG_MARK_E)
    if i < 0 or j < 0 or j < i:
        return doc, None
    j2 = j + len(CHANGELOG_MARK_E)
    block = doc[i:j2]
    return doc[:i] + CHANGELOG_PLACEHOLDER + doc[j2:], block


def _reattach_changelog(doc: str, block: str | None) -> str:
    if block is None:
        return doc.replace(CHANGELOG_PLACEHOLDER, "")
    return doc.replace(CHANGELOG_PLACEHOLDER, block, 1)


def load_core_tickers() -> list[str]:
    out: list[str] = []
    for line in CORE_TXT.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s.upper())
    return out


def sort_tickers_by_theme_then_symbol(
    tickers: list[str], man: dict[str, dict[str, str]]
) -> list[str]:
    """Theme label A–Z, then ticker A–Z (stable grouping on screen and in embed tables)."""

    def key(sym: str) -> tuple[str, str]:
        row = man.get(sym, {})
        theme = (row.get("theme_label") or row.get("theme_slug") or "").strip().lower()
        return (theme, sym.upper())

    return sorted(tickers, key=key)


def load_short_names() -> dict[str, str]:
    if not RU.is_file():
        return {}
    with RU.open(encoding="utf-8", newline="") as f:
        return {
            (r.get("ticker") or "").strip().upper(): (r.get("short_name") or "").strip()
            for r in csv.DictReader(f)
            if (r.get("ticker") or "").strip()
        }


def load_manifest() -> dict[str, dict[str, str]]:
    by_t: dict[str, dict[str, str]] = {}
    with MAN.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = (r.get("ticker") or "").strip().upper()
            if t:
                by_t[t] = r
    return by_t


def slug_labels_from_manifest(man: dict[str, dict[str, str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for r in man.values():
        slug = (r.get("theme_slug") or "").strip()
        lbl = (r.get("theme_label") or slug).strip()
        if slug and slug not in out:
            out[slug] = lbl
    return out


def load_rubric() -> dict[str, dict[str, str]]:
    if not RUB.is_file():
        return {}
    with RUB.open(encoding="utf-8", newline="") as f:
        return {(r.get("ticker") or "").strip().upper(): r for r in csv.DictReader(f)}


def tier_cell(ticker: str, shortlist_items: dict[str, dict]) -> str:
    it = shortlist_items.get(ticker) or {}
    try:
        n = int(it.get("conviction_tier") or 2)
    except (TypeError, ValueError):
        n = 2
    if n < 1 or n > 4:
        n = 2
    label = tier_label(n)
    return f'<td class="shortlist-tier shortlist-tier-{n}">{html.escape(label)}</td>'


def load_shortlist_items() -> dict[str, dict[str, str]]:
    if not CORE_JSON.is_file():
        return {}
    try:
        doc = json.loads(CORE_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    items = doc.get("items") or []
    return {(it.get("ticker") or "").strip().upper(): it for it in items if it.get("ticker")}


def clamp_two_sentences(text: str, max_chars: int = 400) -> str:
    """Trim to at most two sentences (period/exclamation/question boundaries) or max_chars."""
    t = (text or "").strip()
    if not t:
        return "—"
    if len(t) > max_chars:
        t = t[: max_chars - 1].rsplit(" ", 1)[0] + "…"
    boundaries: list[int] = []
    for i, ch in enumerate(t):
        if ch in ".!?" and i < len(t) - 1 and t[i + 1] in " \n\t":
            boundaries.append(i + 1)
            if len(boundaries) >= 2:
                break
    if len(boundaries) >= 2:
        end = boundaries[1]
        while end < len(t) and t[end] in " \n\t":
            end += 1
        t = t[:end].strip()
    return t if t else "—"


def theme_weighted_alloc_strings(
    tickers: list[str], man: dict[str, dict[str, str]], weights: dict[str, float]
) -> tuple[list[str], list[str]]:
    """Renormalised ~Alloc % across present sleeves; return (pct strings, empty policy slugs)."""
    if not tickers:
        return [], list(weights.keys())
    cnt = Counter((man.get(t, {}).get("theme_slug") or "").strip() for t in tickers)
    cnt = {k: v for k, v in cnt.items() if k}
    present = set(cnt.keys())
    wp = sum(weights.get(s, 0.0) for s in present)
    if wp <= 1e-9:
        n = len(tickers)
        base = 100.0 / n
        rounded = [round(base, 2)] * n
        drift = round(100.0 - sum(rounded), 2)
        if abs(drift) >= 0.01:
            rounded[-1] = round(rounded[-1] + drift, 2)
        return [f"{x:.2f}%" for x in rounded], [s for s in weights if weights[s] > 0]
    empty = [s for s in weights if weights[s] > 0 and s not in present]
    raw: list[float] = []
    for t in tickers:
        s = (man.get(t, {}).get("theme_slug") or "").strip()
        theme_pts = 100.0 * weights.get(s, 0.0) / wp
        raw.append(theme_pts / cnt[s])
    rounded = [round(x, 2) for x in raw]
    drift = round(100.0 - sum(rounded), 2)
    if tickers and abs(drift) >= 0.001:
        rounded[-1] = round(rounded[-1] + drift, 2)
    return [f"{r:.2f}%" for r in rounded], empty


def build_alloc_footnote_html(empty_slugs: list[str], slug_lbl: dict[str, str], weights: dict[str, float]) -> str:
    if not empty_slugs:
        return ""
    bits: list[str] = []
    for s in sorted(empty_slugs):
        pct = int(round(weights.get(s, 0) * 100))
        lbl = html.escape(slug_lbl.get(s, s))
        bits.append(f"{lbl} (policy target {pct}%)")
    body = "; ".join(bits)
    return (
        f'<p class="muted fi-shortlist-sleeve-gap"><strong>No Decide names this run</strong> for: {body}. '
        "See the full universe rubric in Screen &amp; Shortlist for candidates.</p>"
    )


def build_proposed_tbody(
    tickers: list[str],
    man: dict[str, dict[str, str]],
    items: dict[str, dict[str, str]],
    weights: dict[str, float],
    rub_by: dict[str, dict[str, str]],
) -> str:
    allocs, _empties = theme_weighted_alloc_strings(tickers, man, weights)
    rows: list[str] = []
    names = load_short_names()
    for i, t in enumerate(tickers):
        row = man.get(t, {})
        theme = (row.get("theme_label") or row.get("theme_slug") or "—").strip()
        company = (names.get(t) or t).strip()
        if len(company) > 48:
            company = company[:45] + "…"
        rows.append(
            "<tr>\n"
            f"              <td><strong>{html.escape(t)}</strong></td>\n"
            f"              <td>{html.escape(company)}</td>\n"
            f"              <td>{html.escape(theme)}</td>\n"
            f"              {tier_cell(t, items)}\n"
            f"              <td>{html.escape(allocs[i])}</td>\n"
            f"              <td>{dd_link(t)}</td>\n"
            "            </tr>"
        )
    return "\n".join(rows)


def build_research_combined_rows(tickers: list[str], man: dict[str, dict[str, str]], items: dict[str, dict]) -> str:
    rows: list[str] = []
    for t in tickers:
        row = man.get(t, {})
        it = items.get(t, {})
        theme = (row.get("theme_label") or row.get("theme_slug") or "—").strip()
        primary = (
            it.get("research_glance")
            or row.get("linkage_one_liner")
            or "—"
        ).strip()
        if len(primary) > 260:
            primary = primary[:257] + "…"
        snapshot = (it.get("research_thesis") or it.get("why_this_name") or "—").strip()
        snapshot = clamp_two_sentences(snapshot, max_chars=480)
        kill = (it.get("research_kill") or it.get("key_risk_kill") or "Define kill after adversarial pack.").strip()
        if len(kill) > 280:
            kill = kill[:277] + "…"
        rows.append(
            f"            <tr><td>{html.escape(t)}</td><td>{html.escape(theme)}</td>"
            f"<td>{html.escape(primary)}</td>"
            f"<td>{html.escape(snapshot)}</td>"
            f"<td>{html.escape(kill)}</td></tr>"
        )
    return "\n".join(rows)


def patch_proposed_shares(doc: str, tbody: str) -> str:
    pat = re.compile(
        r'(<table class="proposed-shares print-table-rubric">\s*<thead>\s*)'
        r"<tr>[\s\S]*?</tr>"
        r"(\s*</thead>\s*<tbody>\s*\n)"
        r"[\s\S]*?"
        r"(\s*</tbody>\s*\n\s*</table>)",
        re.MULTILINE,
    )
    m = pat.search(doc)
    if not m:
        print("Could not find proposed-shares table", file=sys.stderr)
        sys.exit(2)
    return pat.sub(r"\1" + PROPOSED_HEAD + r"\2" + tbody + r"\3", doc, count=1)


def patch_proposed_table_css(doc: str) -> str:
    """Keep column widths aligned after Tier column (col 4)."""
    old_screen = (
        "    table.proposed-shares td:nth-child(4),\n"
        "    table.proposed-shares th:nth-child(4) { min-width: 7.5rem; max-width: none; white-space: nowrap; }\n"
        "    table.proposed-shares td:nth-child(5),\n"
        "    table.proposed-shares th:nth-child(5) { min-width: 20rem; max-width: 48rem; white-space: normal; line-height: 1.45; }"
    )
    new_screen = (
        "    table.proposed-shares td:nth-child(4),\n"
        "    table.proposed-shares th:nth-child(4) { min-width: 4.5rem; max-width: none; white-space: nowrap; }\n"
        "    table.proposed-shares td:nth-child(5),\n"
        "    table.proposed-shares th:nth-child(5) { min-width: 7.5rem; max-width: none; white-space: nowrap; }\n"
        "    table.proposed-shares td:nth-child(6),\n"
        "    table.proposed-shares th:nth-child(6) { min-width: 5.5rem; white-space: nowrap; }\n"
        "    .shortlist-tier-1 { font-weight: 600; color: var(--accent); }\n"
        "    .shortlist-tier-2 { color: var(--fg); }\n"
        "    .shortlist-tier-3 { color: var(--fg); }\n"
        "    .shortlist-tier-4 { color: var(--warn); font-weight: 600; }"
    )
    if old_screen in doc:
        doc = doc.replace(old_screen, new_screen, 1)
    elif ".shortlist-tier-1" not in doc:
        doc = doc.replace(
            "    table.proposed-shares th,\n    table.proposed-shares td { vertical-align: top; }",
            "    table.proposed-shares th,\n    table.proposed-shares td { vertical-align: top; }\n"
            + new_screen,
            1,
        )
    old_print = (
        "      table.proposed-shares td:nth-child(4),\n"
        "      table.proposed-shares th:nth-child(4) {\n"
        "        min-width: 11mm !important;\n"
        "        width: 7% !important;\n"
        "        white-space: nowrap !important;\n"
        "      }\n"
        "      table.proposed-shares td:nth-child(5),\n"
        "      table.proposed-shares th:nth-child(5) {\n"
        "        min-width: 42mm !important;\n"
        "        width: 26% !important;\n"
        "        max-width: none !important;\n"
        "      }\n"
        "      table.proposed-shares td:nth-child(6),\n"
        "      table.proposed-shares th:nth-child(6) {\n"
        "        min-width: 28mm !important;\n"
        "        width: 18% !important;\n"
        "      }\n"
        "      table.proposed-shares td:nth-child(7),\n"
        "      table.proposed-shares th:nth-child(7) {\n"
        "        min-width: 28mm !important;\n"
        "        width: 22% !important;\n"
        "      }"
    )
    new_print = (
        "      table.proposed-shares td:nth-child(4),\n"
        "      table.proposed-shares th:nth-child(4) {\n"
        "        min-width: 14mm !important;\n"
        "        width: 8% !important;\n"
        "        white-space: nowrap !important;\n"
        "      }\n"
        "      table.proposed-shares td:nth-child(5),\n"
        "      table.proposed-shares th:nth-child(5) {\n"
        "        min-width: 11mm !important;\n"
        "        width: 7% !important;\n"
        "        white-space: nowrap !important;\n"
        "      }\n"
        "      table.proposed-shares td:nth-child(6),\n"
        "      table.proposed-shares th:nth-child(6) {\n"
        "        min-width: 16mm !important;\n"
        "        width: 10% !important;\n"
        "        white-space: nowrap !important;\n"
        "      }"
    )
    if old_print in doc:
        doc = doc.replace(old_print, new_print, 1)
    return doc


def patch_alloc_footnote(doc: str, inner_html: str) -> str:
    if FOOTNOTE_MARK not in doc:
        return doc
    rep = inner_html.strip() if inner_html.strip() else ""
    return doc.replace(FOOTNOTE_MARK, rep, 1)


def patch_print_research_combined(doc: str, tbody: str, n: int) -> str:
    """Replace glance + adversarial narrative blocks with one title, note, 5-col table."""
    pat_legacy = re.compile(
        r'<h3 class="print-research-matrix-title">Decide shortlist — research at a glance</h3>\s*'
        r'<p class="muted print-research-matrix-note">[\s\S]*?</p>\s*'
        r'<table class="print-research-matrix print-table-rubric">\s*<thead>[\s\S]*?</thead>\s*<tbody>\s*\n'
        r"[\s\S]*?"
        r"\s*</tbody>\s*\n\s*</table>\s*"
        r'<h3 class="print-research-matrix-title" style="margin-top:4mm;">Decide shortlist — adversarial narrative</h3>\s*'
        r'<p class="muted print-research-matrix-note">[\s\S]*?</p>\s*'
        r'<table class="print-research-matrix print-research-narrative[\s\S]*?<thead>[\s\S]*?</thead>\s*<tbody>\s*\n'
        r"[\s\S]*?"
        r"\s*</tbody>\s*\n\s*</table>",
        re.MULTILINE,
    )
    note = html.escape(
        f"Same {n} names as the Shortlist table and report_core_tickers.txt. "
        "Primary stress, screening snapshot, and kill refresh on each full pipeline run (rule-based bullets)."
    )
    block = (
        '<h3 class="print-research-matrix-title">Decide shortlist — research &amp; adversarial snapshot</h3>\n'
        f'        <p class="muted print-research-matrix-note">{note}</p>\n'
        '        <table class="print-research-matrix print-research-combined print-table-rubric">\n'
        "          <thead>\n"
        "            <tr>\n"
        '              <th scope="col">Ticker</th>\n'
        '              <th scope="col">Theme</th>\n'
        '              <th scope="col">Primary stress</th>\n'
        '              <th scope="col">Thesis &amp; screening snapshot</th>\n'
        '              <th scope="col">Kill / exit trigger (summary)</th>\n'
        "            </tr>\n"
        "          </thead>\n"
        "          <tbody>\n"
        f"{tbody}"
        "          </tbody>\n"
        "        </table>"
    )
    if pat_legacy.search(doc):
        return pat_legacy.sub(block, doc, count=1)

    pat_combined = re.compile(
        r'<h3 class="print-research-matrix-title">Decide shortlist — research &amp; adversarial snapshot</h3>\s*'
        r'<p class="muted print-research-matrix-note">[\s\S]*?</p>\s*'
        r'<table class="print-research-matrix print-research-combined print-table-rubric">\s*'
        r"<thead>[\s\S]*?</thead>\s*<tbody>\s*\n"
        r"[\s\S]*?"
        r"\s*</tbody>\s*\n\s*</table>",
        re.MULTILINE,
    )
    if pat_combined.search(doc):
        return pat_combined.sub(block, doc, count=1)

    print("Could not find combined research matrix region", file=sys.stderr)
    sys.exit(2)


def patch_copy_counts(doc: str, n: int) -> str:
    """Update frozen counts in copy that refer to the Decide core shortlist size."""
    repls = [
        (
            "The <strong>15</strong> core names in the Decide view were taken forward",
            f"The <strong>{n}</strong> core names in the Decide view were taken forward",
        ),
        (
            "The <strong>15</strong> Decide names are the core set taken forward",
            f"The <strong>{n}</strong> Decide names are the core set taken forward",
        ),
        (
            "The <strong>20</strong> core names in the Decide view were taken forward",
            f"The <strong>{n}</strong> core names in the Decide view were taken forward",
        ),
        (
            "The <strong>20</strong> Decide names are the core set taken forward",
            f"The <strong>{n}</strong> Decide names are the core set taken forward",
        ),
        (
            "not the first fifteen you stopped on.",
            f"not the first {n} you stopped on.",
        ),
        ("not the first 20 you stopped on.", f"not the first {n} you stopped on."),
        ("Same 15 names as the rubric subset below.", f"Same {n} names as the rubric subset below."),
        ("Only the Decide shortlist (15 names)", f"Only the Decide shortlist ({n} names)"),
        ("Only the Decide shortlist (20 names)", f"Only the Decide shortlist ({n} names)"),
        (
            "do not treat fifteen names as finished just because they fit on one page",
            "do not treat the shortlist as finished just because it fits on one page",
        ),
    ]
    for a, b in repls:
        doc = doc.replace(a, b)
    return doc


MONITOR_THESIS_NOTE = (
    '<p class="muted"><strong>Full thesis, market context, and kill criteria</strong> '
    'for each name are in <a href="#monitor">Monitor</a> '
    "(select ticker or use Deep dive links in the table).</p>"
)

_MONITOR_NOTE_RE = re.compile(
    r'\s*<p class="muted"><strong>Full thesis, market context, and kill criteria</strong>.*?</p>',
    re.DOTALL,
)


def patch_shortlist_header(doc: str) -> str:
    method_anchor = (
        '<p class="muted"><strong>Method:</strong> Names with stronger balance-sheet'
    )
    doc = _MONITOR_NOTE_RE.sub("", doc)
    if method_anchor in doc:
        doc = doc.replace(
            method_anchor,
            MONITOR_THESIS_NOTE + "\n      " + method_anchor,
            1,
        )
    while doc.count(MONITOR_THESIS_NOTE) > 1:
        doc = doc.replace(MONITOR_THESIS_NOTE, "", 1)
    return doc


def main() -> None:
    man_pre = load_manifest()
    tickers = sort_tickers_by_theme_then_symbol(load_core_tickers(), man_pre)
    if not tickers:
        print(f"No tickers in {CORE_TXT}", file=sys.stderr)
        sys.exit(2)
    n = len(tickers)
    man = man_pre
    items = load_shortlist_items()
    weights = load_theme_weights()
    slug_lbl = slug_labels_from_manifest(man)
    _, empty_slugs = theme_weighted_alloc_strings(tickers, man, weights)
    foot_html = build_alloc_footnote_html(empty_slugs, slug_lbl, weights)

    text = HTML.read_text(encoding="utf-8")
    text, changelog_block = _detach_changelog(text)
    rub_by = load_rubric()
    text = patch_proposed_shares(
        text, build_proposed_tbody(tickers, man, items, weights, rub_by) + "\n"
    )
    text = patch_proposed_table_css(text)
    text = patch_alloc_footnote(text, foot_html)
    text = patch_print_research_combined(
        text, build_research_combined_rows(tickers, man, items) + "\n", n
    )
    text = patch_copy_counts(text, n)
    text = patch_shortlist_header(text)
    text = _reattach_changelog(text, changelog_block)

    HTML.write_text(text, encoding="utf-8")
    print(f"Patched shortlist tables + copy for {n} tickers → {HTML}")


if __name__ == "__main__":
    main()
