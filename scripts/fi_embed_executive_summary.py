#!/usr/bin/env python3
"""
Regenerate the Executive Summary section from core-shortlist.json and model CSVs.

Includes shortlist adds/drops vs the prior refresh (selection_memo.shortlist_delta).
Run after fi_enrich_core_shortlist.py and fi_save_shortlist_prior.py cycle.

Usage:
  python3 scripts/fi_embed_executive_summary.py
"""
from __future__ import annotations

import csv
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

from fi_embed_core import CORE_JSON, HTML, W, load_csv_index
from fi_embed_single_screen import THEME_FILTER_SHORT, load_manifest_stats
from fi_narrative import BULLET, format_verdict_summary, rubric_total, safe_float

MAN = W / "universe_manifest.csv"
RISK = W / "risk_metrics.csv"

MARK_S = "<!-- FI_EXECUTIVE_SUMMARY_START -->"
MARK_E = "<!-- FI_EXECUTIVE_SUMMARY_END -->"
CSS_S = "<!-- FI_EXEC_SUMMARY_CSS_START -->"
CSS_E = "<!-- FI_EXEC_SUMMARY_CSS_END -->"

ERN = W / "earnings_data.csv"
SCEN = W / "scenario_results.csv"
RUB = W / "rubric_scores.csv"

EXEC_CSS = """
    /* ── Executive Summary (document-style, minimal chrome) ── */
    #executive-summary .exec-body {
      max-width: 46rem;
      line-height: 1.55;
    }
    #executive-summary .exec-body > * + * {
      margin-top: 1.35rem;
    }
    #executive-summary .exec-lead p {
      margin: 0 0 0.85rem;
      font-size: 1rem;
    }
    #executive-summary .exec-lead p:last-child {
      margin-bottom: 0;
    }
    #executive-summary .exec-meta {
      font-size: 0.88rem;
      color: var(--muted);
      margin: 0;
      padding: 0;
      border: none;
    }
    #executive-summary .exec-method {
      font-size: 0.88rem;
      line-height: 1.5;
      margin: 0.5rem 0 0;
      padding-left: 0.85rem;
      border-left: 2px solid var(--line);
      color: var(--muted);
    }
    #executive-summary .exec-block > h3 {
      margin: 0 0 0.5rem;
      font-size: 1rem;
      font-weight: 700;
      letter-spacing: -0.01em;
    }
    #executive-summary .exec-block > h4 {
      margin: 0.85rem 0 0.35rem;
      font-size: 0.9rem;
      font-weight: 600;
    }
    #executive-summary .exec-changes-lead {
      margin: 0 0 0.65rem;
    }
    #executive-summary .exec-delta-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.25rem 1.5rem;
      margin-top: 0.5rem;
    }
    @media (max-width: 720px) {
      #executive-summary .exec-delta-grid {
        grid-template-columns: 1fr;
      }
    }
    #executive-summary table.exec-table {
      width: 100%;
      min-width: 0 !important;
      font-size: 0.84rem;
      border-collapse: collapse;
      margin: 0.25rem 0 0;
    }
    #executive-summary table.exec-table th,
    #executive-summary table.exec-table td {
      padding: 0.35rem 0.45rem;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }
    #executive-summary table.exec-table th {
      font-weight: 600;
      font-size: 0.8rem;
      color: var(--muted);
    }
    #executive-summary table.exec-tier-table td:first-child {
      white-space: nowrap;
      width: 8.5rem;
    }
    #executive-summary .exec-tier-spotlight {
      margin: 0.65rem 0 0;
      padding-left: 1.1rem;
      font-size: 0.88rem;
    }
    #executive-summary .exec-tier-spotlight li {
      margin: 0.3rem 0;
    }
    #executive-summary .exec-movers ul,
    #executive-summary .exec-columns ul {
      margin: 0.25rem 0 0;
      padding-left: 1.15rem;
      font-size: 0.9rem;
    }
    #executive-summary .exec-columns {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.25rem 2rem;
    }
    @media (max-width: 720px) {
      #executive-summary .exec-columns {
        grid-template-columns: 1fr;
      }
    }
    #executive-summary .exec-columns h4 {
      margin: 0 0 0.35rem;
      font-size: 0.9rem;
      font-weight: 600;
    }
    #executive-summary .exec-columns li {
      margin: 0.35rem 0;
    }
"""

PRINT_EXEC_PATCH = """      #executive-summary {
        display: block !important;
        page-break-after: avoid;
      }
      #executive-summary .exec-body {
        max-width: none !important;
      }
      #executive-summary .exec-delta-grid,
      #executive-summary .exec-columns {
        grid-template-columns: 1fr 1fr !important;
        gap: 3mm !important;
      }
      #executive-summary table.exec-table {
        font-size: 8pt !important;
      }"""

PRINT_EXEC_OLD = """      #executive-summary {
        display: none !important;
      }"""


def _esc(v: object) -> str:
    if v is None or v == "":
        return "—"
    return html.escape(str(v))


def _strip(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()


def theme_label(slug: str) -> str:
    s = (slug or "").strip().lower()
    if not s:
        return "—"
    return THEME_FILTER_SHORT.get(s, s.replace("_", " ").title())


def tier_from_total(tot: int | None) -> int:
    if tot is None:
        return 2
    if tot >= 18:
        return 1
    if tot <= 12:
        return 3
    return 2


def load_manifest_themes() -> dict[str, str]:
    if not MAN.is_file():
        return {}
    out: dict[str, str] = {}
    with MAN.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            t = (row.get("ticker") or "").strip().upper()
            if not t:
                continue
            slug = (row.get("theme_slug") or "").strip()
            lbl = (row.get("theme_label") or "").strip()
            if "—" in lbl:
                lbl = lbl.split("—")[0].strip()
            out[t] = lbl or THEME_FILTER_SHORT.get(slug, slug) or slug
    return out


def load_core_doc() -> dict[str, Any]:
    if not CORE_JSON.is_file():
        return {}
    return json.loads(CORE_JSON.read_text(encoding="utf-8"))


def load_earnings() -> dict[str, dict[str, str]]:
    if not ERN.is_file():
        return {}
    with ERN.open(encoding="utf-8", newline="") as f:
        return {(r.get("ticker") or "").strip().upper(): r for r in csv.DictReader(f)}


def short_method(memo: dict[str, Any]) -> str:
    m = (memo.get("method") or "").strip()
    if not m:
        return "Five-signal composite pool with theme caps."
    if len(m) > 200:
        return m[:197] + "…"
    return m


def exec_meta_line(as_of: str, core_n: int, stats: dict, model_n: int) -> str:
    return (
        '<p class="exec-meta">'
        f"As of <strong>{as_of}</strong> · "
        f"<strong>{core_n}</strong>-name core shortlist · "
        f"<strong>{stats['uni_n']}</strong> universe · "
        f"<strong>{stats['n_themes']}</strong> themes · "
        f"~<strong>{model_n}</strong> modelled"
        "</p>"
    )


def _short_why(item: dict[str, Any], max_len: int = 100) -> str:
    why = _strip(item.get("why_this_name") or item.get("linkage_one_liner") or "")
    if len(why) > max_len:
        return why[: max_len - 1].rstrip() + "…"
    return why


def exec_lead(
    tickers: list[str],
    items: dict[str, dict],
    rub_by: dict,
    scen_by: dict,
    delta: dict[str, Any],
    memo: dict[str, Any],
    stats: dict,
    core_n: int,
    as_of: str,
) -> str:
    by_tier: dict[int, list[str]] = {1: [], 2: [], 3: []}
    for t in tickers:
        by_tier[tier_from_total(rubric_total(rub_by.get(t) or {}))].append(t)

    def sort_upside(sym_list: list[str]) -> list[str]:
        return sorted(
            sym_list,
            key=lambda t: safe_float((scen_by.get(t) or {}).get("weighted_upside")) or -999.0,
            reverse=True,
        )

    t1 = sort_upside(by_tier[1])
    t1_show = ", ".join(t1[:6]) + (f" (+{len(t1) - 6} more)" if len(t1) > 6 else "")
    theme_by = load_manifest_themes()
    theme_counts: dict[str, int] = {}
    for sym in tickers:
        th = theme_by.get(sym) or theme_label(str((items.get(sym) or {}).get("theme") or ""))
        theme_counts[th] = theme_counts.get(th, 0) + 1
    top_sleeves = ", ".join(f"{k} ({v})" for k, v in sorted(theme_counts.items(), key=lambda x: -x[1])[:3])

    p1 = (
        f"This report’s <strong>{core_n}-name</strong> core shortlist (as of <strong>{_esc(as_of)}</strong>) "
        f"is drawn from a <strong>{stats['uni_n']}-company</strong> thematic universe. "
        f"<strong>{len(t1)}</strong> names sit in the highest-conviction tier "
        f"({_esc(t1_show or '—')}). "
        "Selection follows the five-signal composite—scenario, rubric, risk, Monte Carlo, and DCF—"
        "with theme caps; rubric rank alone does not add or drop names."
    )

    added = delta.get("added") or []
    dropped = delta.get("dropped") or []
    if delta.get("baseline_established"):
        p2 = (
            "This is the first saved baseline for shortlist deltas; the next refresh will show "
            "adds, drops, and quality movers against today’s list."
        )
    elif added or dropped:
        add_s = ", ".join(str(r.get("ticker") or "?") for r in added[:5])
        drop_s = ", ".join(str(r.get("ticker") or "?") for r in dropped[:5])
        unchanged = delta.get("unchanged_count")
        p2 = (
            f"Versus the prior snapshot: <strong>{len(added)} added</strong> ({_esc(add_s)}), "
            f"<strong>{len(dropped)} dropped</strong> ({_esc(drop_s)})"
            + (f", <strong>{unchanged}</strong> unchanged." if unchanged is not None else ".")
        )
        p2 += f" Sleeve emphasis: {_esc(top_sleeves)}."
    else:
        p2 = f"Shortlist membership is unchanged from the prior snapshot. Sleeve emphasis: {_esc(top_sleeves)}."

    watch = _strip(str(memo.get("what_to_watch_for") or ""))
    if "cap_casualties" in watch.lower() or "high_yoy_outside_pool" in watch.lower():
        watch = (
            "Before overriding the composite screen, check theme-cap casualties and "
            "high-growth names still outside the pool — then confirm each hold in filings "
            "and adversarial packs (a gate, not a buy signal)."
        )
    elif not watch:
        watch = (
            "Reconcile scenario upside with scorecard quality before sizing; "
            "adversarial packs are a gate, not a buy signal."
        )
    if len(watch) > 240:
        watch = watch[:237] + "…"
    p3 = f'<span class="muted">Bottom line:</span> {_esc(watch)}'

    return f'<div class="exec-lead"><p>{p1}</p><p>{p2}</p><p>{p3}</p></div>'.replace("<div", "<div")


def tier_overview_table(
    by_tier: dict[int, list[str]],
    items: dict[str, dict],
    rub_by: dict,
    scen_by: dict,
) -> str:
    labels = {
        1: ("Tier 1 — Highest conviction", "var(--accent)"),
        2: ("Tier 2 — Core watchlist", ""),
        3: ("Tier 3 / Speculative", "var(--warn)"),
    }
    rows: list[str] = []
    spotlight: list[str] = []
    for tier in (1, 2, 3):
        tickers = sorted(
            by_tier[tier],
            key=lambda t: safe_float((scen_by.get(t) or {}).get("weighted_upside")) or -999.0,
            reverse=True,
        )
        label, color = labels[tier]
        color_attr = f' style="color:{color}"' if color else ""
        if not tickers:
            rows.append(
                f"<tr><td><strong{color_attr}>{_esc(label)}</strong></td>"
                f'<td>0</td><td class="muted">—</td></tr>'
            )
            continue
        names = ", ".join(tickers)
        if len(names) > 120:
            names = ", ".join(tickers[:10]) + f" (+{len(tickers) - 10} more)"
        rows.append(
            f"<tr><td><strong{color_attr}>{_esc(label)}</strong></td>"
            f"<td>{len(tickers)}</td><td>{_esc(names)}</td></tr>"
        )
        if tier == 1:
            for t in tickers[:3]:
                it = items.get(t) or {}
                rub = rub_by.get(t) or {}
                scen = scen_by.get(t)
                why = _esc(_short_why(it, 72))
                tot = rubric_total(rub)
                w_up = safe_float((scen or {}).get("weighted_upside"))
                bits = []
                if tot is not None:
                    bits.append(f"scorecard {tot}/24")
                if w_up is not None:
                    bits.append(f"wt upside {w_up:+.0f}%")
                headline = " · ".join(bits) if bits else "on shortlist"
                spotlight.append(
                    f"<li><strong>{_esc(t)}</strong> — {_esc(headline)}"
                    + (f'. <span class="muted">{why}</span>' if why else "")
                    + "</li>"
                )

    table = (
        '<table class="exec-table exec-tier-table"><thead><tr>'
        "<th>Tier</th><th>#</th><th>Names</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
    if not spotlight:
        return table
    return table + '<ul class="exec-tier-spotlight">' + "".join(spotlight) + "</ul>"


def top_reasons(
    tickers: list[str],
    items: dict[str, dict],
    earn: dict[str, dict[str, str]],
    stats: dict,
    core_n: int,
) -> str:
    u, t = stats["uni_n"], stats["n_themes"]
    growth: list[tuple[float, str]] = []
    for sym in tickers:
        yoy = safe_float((earn.get(sym) or {}).get("rev_yoy_pct"))
        if yoy is not None:
            growth.append((yoy, sym))
    growth.sort(reverse=True)

    bullets: list[str] = []
    if growth:
        top = growth[:3]
        bullets.append(
            "Revenue momentum on the shortlist: "
            + BULLET.join(f"<strong>{_esc(sym)}</strong> ({yoy:+.0f}% YoY)" for yoy, sym in top)
            + "."
        )

    theme_by = load_manifest_themes()
    theme_counts: dict[str, int] = {}
    for sym in tickers:
        th = theme_by.get(sym) or theme_label(str((items.get(sym) or {}).get("theme") or ""))
        theme_counts[th] = theme_counts.get(th, 0) + 1
    if theme_counts:
        mix = ", ".join(f"{k} ({v})" for k, v in sorted(theme_counts.items(), key=lambda x: -x[1])[:5])
        bullets.append(f"Sleeve mix on the {core_n}-name shortlist: {_esc(mix)}.")

    bullets.append(
        f"Universe screen: <strong>{u}</strong> companies across <strong>{t}</strong> themes "
        f"on US, UK, and European listings — rubric scored on latest quarterly earnings."
    )
    bullets.append(
        "Selection uses the five-signal composite with theme caps — rubric rank alone does not add or drop names."
    )
    return "<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"


def top_risks(
    tickers: list[str],
    items: dict[str, dict],
    rub_by: dict,
    scen_by: dict,
) -> str:
    bullets: list[str] = []
    tier3 = [t for t in tickers if tier_from_total(rubric_total(rub_by.get(t) or {})) == 3]
    if tier3:
        bullets.append(
            f"Tier 3 / speculative slots: <strong>{_esc(', '.join(tier3))}</strong> "
            "— confirm catalysts in the next filing."
        )

    disagree = 0
    for t in tickers:
        rub = rub_by.get(t) or {}
        tot = rubric_total(rub)
        w_up = safe_float((scen_by.get(t) or {}).get("weighted_upside"))
        if tot is not None and tot >= 16 and w_up is not None and w_up < 0:
            disagree += 1
    if disagree:
        bullets.append(
            f"<strong>{disagree}</strong> name(s) show strong scorecards but negative scenario-weighted upside "
            "— treat cross-model tension as a filings checklist."
        )

    risk_by = load_csv_index(RISK)
    high_vol: list[str] = []
    for t in tickers:
        rk = risk_by.get(t) or {}
        try:
            dd = float(rk.get("max_drawdown") or 0)
            if dd <= -0.45:
                high_vol.append(t)
        except (TypeError, ValueError):
            pass
    if high_vol:
        bullets.append(
            f"Elevated drawdown in the lookback window: <strong>{_esc(', '.join(high_vol[:5]))}</strong> "
            "— volatility is not thesis validation."
        )

    if "QUBT" in tickers or "IONQ" in tickers:
        bullets.append(
            "Quantum sleeve names remain narrative-heavy with extreme valuation risk — "
            "treat as long-dated optionality, not core compounders."
        )

    kills = []
    for t in tickers[:8]:
        k = _strip((items.get(t) or {}).get("key_risk_kill") or "")
        if k:
            kills.append(f"<strong>{_esc(t)}</strong>: {_esc(k[:100])}")
    if kills:
        bullets.append("Key kill triggers in focus: " + "; ".join(kills[:3]) + ".")

    if not bullets:
        bullets.append(
            "No automatic red flags from tiering — still verify each name in Research before sizing."
        )
    return "<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"


def build_inner(doc: dict[str, Any], stats: dict, *, as_of: str = "") -> str:
    items_list = doc.get("items") or []
    items = {(it.get("ticker") or "").strip().upper(): it for it in items_list if (it.get("ticker") or "").strip()}
    tickers = sorted(items.keys())
    core_n = len(tickers) or int(doc.get("shortlist_n") or 0)
    as_of_disp = _esc(doc.get("as_of") or as_of or "this refresh")
    memo = doc.get("selection_memo") or {}
    delta = dict(memo.get("shortlist_delta") or {})

    rub_by = load_csv_index(RUB)
    scen_by = load_csv_index(SCEN)
    earn = load_earnings()
    model_n = stats.get("model_n") or 0

    by_tier: dict[int, list[str]] = {1: [], 2: [], 3: []}
    for t in tickers:
        by_tier[tier_from_total(rubric_total(rub_by.get(t) or {}))].append(t)

    overview = (
        '<section class="exec-block" aria-labelledby="exec-overview-h">'
        '<h3 id="exec-overview-h">Shortlist by conviction tier</h3>'
        + tier_overview_table(by_tier, items, rub_by, scen_by)
        + "</section>"
    )

    reasons_risks = (
        '<section class="exec-block" aria-labelledby="exec-reasons-h">'
        '<h3 id="exec-reasons-h">Supporting view and watchouts</h3>'
        '<div class="exec-columns">'
        "<div><h4>Why this shortlist</h4>"
        + top_reasons(tickers, items, earn, stats, core_n)
        + "</div><div><h4>Biggest risks</h4>"
        + top_risks(tickers, items, rub_by, scen_by)
        + "</div></div></section>"
    )

    parts = [
        '<div class="exec-body">',
        exec_lead(tickers, items, rub_by, scen_by, delta, memo, stats, core_n, as_of_disp),
        exec_meta_line(as_of_disp, core_n, stats, model_n),
        f'<p class="exec-method">{_esc(short_method(memo))}</p>',
        overview,
        reasons_risks,
        "</div>",
    ]
    return "\n".join(parts)
def inject_css(doc: str) -> str:
    block = f"{CSS_S}\n{EXEC_CSS}\n{CSS_E}"
    if CSS_S in doc and CSS_E in doc:
        return re.sub(re.escape(CSS_S) + r"[\s\S]*?" + re.escape(CSS_E), block, doc, count=1)
    anchor = "    .dim-cards.dim-cards-eq3 {"
    if anchor in doc:
        return doc.replace(anchor, block + "\n" + anchor, 1)
    return doc


def patch_print_css(doc: str) -> str:
    if PRINT_EXEC_OLD in doc:
        doc = doc.replace(PRINT_EXEC_OLD, PRINT_EXEC_PATCH, 1)
    if '<li><a href="#executive-summary">' not in doc and "print-toc-list" in doc:
        doc = doc.replace(
            '<li><a href="#introduction">Equity Research</a></li>',
            '<li><a href="#introduction">Equity Research</a></li>\n'
            '        <li><a href="#executive-summary">Executive summary</a></li>',
            1,
        )
    return doc


def patch_html(doc: str, inner: str) -> str:
    block = f"{MARK_S}\n{inner}\n{MARK_E}"
    if MARK_S in doc and MARK_E in doc:
        return re.sub(re.escape(MARK_S) + r"[\s\S]*?" + re.escape(MARK_E), block, doc, count=1)
    pat = re.compile(
        r'(<section id="executive-summary">\s*<h2>Executive Summary</h2>\s*)'
        r"[\s\S]*?"
        r"(\s*</section>)",
        re.IGNORECASE,
    )
    m = pat.search(doc)
    if not m:
        return doc
    return doc[: m.start()] + m.group(1) + "\n" + block + "\n" + m.group(2) + doc[m.end() :]


def main() -> int:
    if not CORE_JSON.is_file():
        print("Missing core-shortlist.json", file=sys.stderr)
        return 2
    core = load_core_doc()
    stats = load_manifest_stats(MAN)
    inner = build_inner(core, stats, as_of=str(core.get("as_of") or ""))
    text = HTML.read_text(encoding="utf-8")
    text = inject_css(text)
    text = patch_print_css(text)
    text = patch_html(text, inner)
    HTML.write_text(text, encoding="utf-8")
    n = len(core.get("items") or [])
    delta = (core.get("selection_memo") or {}).get("shortlist_delta") or {}
    print(
        f"Patched Executive Summary — {n} core names, "
f"as of {core.get('as_of') or '—'}",
        file=sys.stderr,
    )
    print(HTML.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
