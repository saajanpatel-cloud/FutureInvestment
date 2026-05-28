#!/usr/bin/env python3
"""Embed Appendix B — one research page per decide-union ticker. Not investment advice."""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

from fi_embed_decide_data import load_csv_index, load_rubric, rubric_total
from fi_portfolio_tickers import load_decide_union, load_shortlist, portfolio_only

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
HTML = W / "SINGLE_SCREEN_REPORT.html"
CORE_JSON = ROOT / "watchlist-ui" / "core-shortlist.json"
PROFILE = W / "company_profile.csv"
SC_RES = W / "scenario_results.csv"
MC_RES = W / "monte_carlo_results.csv"
RISK = W / "risk_metrics.csv"
ADV = W / "adversarial_packs.json"
MARKER = "<!-- FI_APPENDIX_TICKER_PAGES -->"

MAX_BULLET = 280


def ensure_appendix_container(doc: str) -> str:
    if 'id="appendix-company-research-pages"' in doc:
        return doc
    section = (
        '    <section id="appendix-company-research" class="fi-appendix-research-pdf" '
        'aria-label="Company research appendix">\n'
        "      <h2>Appendix B — Company research</h2>\n"
        "      <p class=\"muted\">One page per name (composite shortlist, then personal holdings). "
        "Regenerated on refresh.</p>\n"
        f"      <div id=\"appendix-company-research-pages\">{MARKER}</div>\n"
        "    </section>\n"
    )
    if "</main>" in doc:
        return doc.replace("</main>", section + "    </main>", 1)
    return doc


def trunc(s: str, n: int = MAX_BULLET) -> str:
    s = " ".join((s or "").split())
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def dd_text(it: dict, key: str, fallback: str = "", n: int = 380) -> str:
    dd = it.get("deep_dive") or {}
    val = dd.get(key) or it.get(key) or fallback
    return trunc(str(val or ""), n)


def today_stance(it: dict) -> str:
    dd = it.get("deep_dive") or {}
    zones = str(dd.get("model_zones") or "").strip()
    low = zones.lower()
    if "avoid" in low:
        return f"Avoid today — {trunc(zones, 220)}"
    if "hold" in low:
        return f"Hold / wait today — {trunc(zones, 220)}"
    if "buy" in low:
        return f"Buy only in zone — {trunc(zones, 220)}"
    try:
        tier = int(it.get("conviction_tier") or 0)
    except (TypeError, ValueError):
        tier = 0
    if tier == 1:
        return "Potential buy only on weakness; size with risk controls."
    if tier == 4:
        return "Not a buy today unless thesis/risk improves materially."
    return "Watchlist name today; wait for entry zone and thesis confirmation."


def scenario_svg(sc: dict | None, mc: dict | None) -> str:
    if not sc and not mc:
        return '<p class="muted">Chart unavailable.</p>'
    vals: list[float] = []
    labels: list[tuple[str, float, str]] = []
    try:
        if sc:
            for k, c in (("Bear", "#f87171"), ("Base", "#94a3b8"), ("Bull", "#34d399")):
                px = float(sc.get(f"{k.lower()}_price") or 0)
                if px > 0:
                    vals.append(px)
                    labels.append((k, px, c))
        if mc:
            for k, c in (("P10", "#f59e0b"), ("Median", "#6366f1"), ("P90", "#22c55e")):
                px = float(mc.get(k.lower()) or 0)
                if px > 0:
                    vals.append(px)
                    labels.append((k, px, c))
    except (TypeError, ValueError):
        return '<p class="muted">Chart unavailable.</p>'
    if not vals:
        return '<p class="muted">Chart unavailable.</p>'
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or max(hi * 0.05, 1.0)
    lo -= span * 0.1
    hi += span * 0.1
    width, height = 620, 86
    lines = [
        f'<svg class="appendix-mini-chart" viewBox="0 0 {width} {height}" preserveAspectRatio="none" role="img" aria-label="Scenario and Monte Carlo price range">',
        f'<line x1="12" y1="46" x2="{width-12}" y2="46" stroke="#cbd5e1" stroke-width="1.2" />',
    ]
    for name, px, color in labels:
        x = 12 + (px - lo) / (hi - lo) * (width - 24)
        lines.append(f'<line x1="{x:.1f}" y1="32" x2="{x:.1f}" y2="60" stroke="{color}" stroke-width="2.2" />')
        lines.append(f'<text x="{x:.1f}" y="24" text-anchor="middle" fill="{color}" font-size="10">{html.escape(name)} ${px:.1f}</text>')
    lines.append("</svg>")
    return "".join(lines)


def load_items() -> dict[str, dict]:
    if not CORE_JSON.is_file():
        return {}
    try:
        doc = json.loads(CORE_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {
        (it.get("ticker") or "").strip().upper(): it
        for it in (doc.get("items") or [])
        if it.get("ticker")
    }


def load_profiles() -> dict[str, dict]:
    import csv

    out: dict[str, dict] = {}
    if not PROFILE.is_file():
        return out
    with PROFILE.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = (r.get("ticker") or "").strip().upper()
            if t:
                out[t] = r
    return out


def load_adversarial() -> dict[str, dict]:
    if not ADV.is_file():
        return {}
    try:
        doc = json.loads(ADV.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    packs = doc.get("packs") if isinstance(doc, dict) else doc
    if not isinstance(packs, dict):
        return {}
    return {k.upper(): v for k, v in packs.items() if isinstance(v, dict)}


def adv_bullets(pack: dict | None, n: int = 3) -> list[str]:
    if not pack:
        return []
    out: list[str] = []
    for key in ("bear_thesis", "stress_points", "kill_criteria"):
        val = pack.get(key)
        if isinstance(val, list):
            for x in val:
                s = str(x).strip()
                if s:
                    out.append(trunc(s, 200))
        elif isinstance(val, str) and val.strip():
            out.append(trunc(val, 200))
        if len(out) >= n:
            break
    return out[:n]


def model_snapshot(t: str, rub_by, sc_by, mc_by, rk_by) -> str:
    rub = rub_by.get(t, {})
    tot = rubric_total(rub)
    parts = [f"Rubric {tot}/30" if tot is not None else "Rubric —"]
    sc = sc_by.get(t)
    if sc:
        try:
            parts.append(f"Scenario wtd {float(sc['weighted_upside']):+.0f}%")
        except (KeyError, ValueError):
            pass
    mc = mc_by.get(t)
    if mc:
        try:
            cur = float(mc["current_price"])
            med = float(mc["median_price"])
            if cur > 0:
                parts.append(f"MC median {(med / cur - 1) * 100:+.0f}%")
        except (KeyError, ValueError, ZeroDivisionError):
            pass
    rk = rk_by.get(t)
    if rk:
        try:
            parts.append(f"Sharpe {float(rk['sharpe']):.2f}")
            parts.append(f"Max DD {float(rk['max_drawdown']) * 100:.0f}%")
        except (KeyError, ValueError):
            pass
    return " · ".join(parts)


def build_page(
    t: str,
    badge: str,
    it: dict,
    prof: dict,
    rub_by,
    sc_by,
    mc_by,
    rk_by,
    adv_by,
) -> str:
    name = (prof.get("long_name") or prof.get("short_name") or t).strip()
    theme = (it.get("theme_label") or "").strip()
    glance = dd_text(it, "at_a_glance", it.get("research_glance") or it.get("research_thesis") or "", 420)
    what_company = dd_text(it, "what_company", "", 360)
    products = dd_text(it, "key_products", "", 360)
    strategic = dd_text(it, "strategic_plays", "", 320)
    theme_linkage = dd_text(it, "theme_linkage", "", 320)
    demand = dd_text(it, "demand_outlook", "", 320)
    market_ctx = dd_text(it, "market_context", "", 320)
    thesis = dd_text(it, "research_thesis", "", 420)
    kill = dd_text(it, "kill", it.get("research_kill") or it.get("key_risk_kill") or "", 280)
    bull = dd_text(it, "bull_case", it.get("qual_bull") or "", 260)
    bear = dd_text(it, "bear_case", it.get("qual_bear") or "", 260)
    watch = dd_text(it, "watch", it.get("qual_watch") or "", 260)
    lens = it.get("growth_lens") or {}
    lens_line = ""
    if lens:
        lens_line = (
            f'<p class="growth-lens"><strong>Growth lens:</strong> '
            f"{html.escape(str(lens.get('linkage_tier', '')).replace('_', ' '))} — "
            f"{html.escape(trunc(str(lens.get('growth_mechanism') or ''), 220))}</p>"
        )
    adv = adv_bullets(adv_by.get(t))
    if adv:
        adv_html = "<ul>" + "".join(f"<li>{html.escape(b)}</li>" for b in adv) + "</ul>"
    else:
        adv_html = '<p class="muted">—</p>'
    snap = html.escape(model_snapshot(t, rub_by, sc_by, mc_by, rk_by))
    scen = sc_by.get(t, {})
    mc = mc_by.get(t, {})
    rk = rk_by.get(t, {})
    scen_line = "Scenario data unavailable"
    if scen:
        try:
            scen_line = (
                f"Wtd up {float(scen.get('weighted_upside') or 0):+.0f}% | "
                f"B {float(scen.get('bull_upside') or 0):+.0f}% / "
                f"Ba {float(scen.get('base_upside') or 0):+.0f}% / "
                f"Br {float(scen.get('bear_upside') or 0):+.0f}%"
            )
        except (TypeError, ValueError):
            pass
    mc_line = "MC unavailable"
    if mc:
        try:
            cp = float(mc.get("current_price") or 0)
            med = float(mc.get("median_price") or 0)
            p10 = float(mc.get("p10") or 0)
            p90 = float(mc.get("p90") or 0)
            mc_line = f"MC median ${med:.2f} vs spot ${cp:.2f} | P10 ${p10:.2f} / P90 ${p90:.2f}"
        except (TypeError, ValueError):
            pass
    risk_line = "Risk metrics unavailable"
    if rk:
        try:
            risk_line = (
                f"Beta {float(rk.get('beta') or 0):.2f} | "
                f"Vol {float(rk.get('volatility') or 0)*100:.1f}% | "
                f"Sharpe {float(rk.get('sharpe') or 0):.2f} | "
                f"MaxDD {float(rk.get('max_drawdown') or 0)*100:.0f}%"
            )
        except (TypeError, ValueError):
            pass
    stance = today_stance(it)
    chart = scenario_svg(scen, mc)
    return (
        f'      <article class="appendix-ticker-page" id="appendix-{html.escape(t)}">\n'
        f"        <h3>{html.escape(t)} — {html.escape(name)} "
        f'<span class="muted">({html.escape(badge)}</span>)</h3>\n'
        f'        <p class="muted">{html.escape(theme)}</p>\n'
        f"        <p><strong>At a glance.</strong> {html.escape(glance)}</p>\n"
        f"        <p><strong>What this company is.</strong> {html.escape(what_company)}</p>\n"
        f"        <p><strong>Key products & revenue drivers.</strong> {html.escape(products)}</p>\n"
        f"        <p><strong>Strategic plays.</strong> {html.escape(strategic)}</p>\n"
        f"        <p><strong>Theme linkage.</strong> {html.escape(theme_linkage)}</p>\n"
        f"        <p><strong>Demand outlook.</strong> {html.escape(demand)}</p>\n"
        f"        <p><strong>Market context.</strong> {html.escape(market_ctx)}</p>\n"
        f"{lens_line}\n"
        f"        <p><strong>Thesis.</strong> {html.escape(thesis)}</p>\n"
        f"        <p><strong>Should I buy today?</strong> {html.escape(stance)}</p>\n"
        f"        <p><strong>Kill / watch.</strong> {html.escape(kill)} {html.escape(watch)}</p>\n"
        f"        <p><strong>Bull.</strong> {html.escape(bull)}</p>\n"
        f"        <p><strong>Bear.</strong> {html.escape(bear)}</p>\n"
        f"        <p><strong>Models.</strong> {snap}</p>\n"
        f"        <p><strong>Scenario detail.</strong> {html.escape(scen_line)}</p>\n"
        f"        <p><strong>Monte Carlo detail.</strong> {html.escape(mc_line)}</p>\n"
        f"        <p><strong>Risk detail.</strong> {html.escape(risk_line)}</p>\n"
        f"        <div class=\"appendix-chart-wrap\"><strong>Model range chart.</strong>{chart}</div>\n"
        f"        <p><strong>Adversarial.</strong></p>\n{adv_html}\n"
        f"        <p class=\"muted\" style=\"font-size:8.5pt;\">Further reading: "
        f"research/memoes/draft_reports/{html.escape(t)}.md</p>\n"
        f"      </article>\n"
    )


def main() -> int:
    sl = set(load_shortlist())
    extra = portfolio_only()
    union = load_decide_union()
    items = load_items()
    prof_by = load_profiles()
    rub_by = load_rubric()
    sc_by = load_csv_index(SC_RES, "ticker")
    mc_by = load_csv_index(MC_RES, "ticker")
    rk_by = load_csv_index(RISK, "ticker")
    adv_by = load_adversarial()

    parts: list[str] = []
    for t in union:
        badge = "composite shortlist" if t in sl else "personal holding"
        parts.append(
            build_page(
                t,
                badge,
                items.get(t, {}),
                prof_by.get(t, {}),
                rub_by,
                sc_by,
                mc_by,
                rk_by,
                adv_by,
            )
        )
    inner = "".join(parts)

    doc = HTML.read_text(encoding="utf-8")
    doc = ensure_appendix_container(doc)
    marker_n = doc.count(MARKER)
    if marker_n >= 2:
        doc = re.sub(
            re.escape(MARKER) + r"[\s\S]*?" + re.escape(MARKER),
            MARKER + "\n" + inner + MARKER,
            doc,
            count=1,
        )
    elif marker_n == 1:
        doc = doc.replace(MARKER, MARKER + "\n" + inner + MARKER, 1)
    else:
        doc = doc.replace(
            '<div id="appendix-company-research-pages">',
            f'<div id="appendix-company-research-pages">\n{MARKER}\n{inner}{MARKER}\n',
            1,
        )
    HTML.write_text(doc, encoding="utf-8")
    print(f"Appendix B: {len(union)} pages ({len(extra)} portfolio-only) → {HTML}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
