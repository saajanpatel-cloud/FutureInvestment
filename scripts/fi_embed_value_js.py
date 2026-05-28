#!/usr/bin/env python3
"""
Regenerate deep-dive JS (META, SCENARIOS, RISK, MC, DCF, RUBRIC, SOWHAT, ADV) for core tickers only.

Replaces the block between FI_VALUE_JS_START and FI_VALUE_JS_END in SINGLE_SCREEN_REPORT.html.
Run via refresh_watchlists.sh after core valuation CSVs exist.

Not investment advice.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

from fi_embed_chart_ticker_core import load_exchanges, tv_symbol
from fi_embed_core import HTML, W, load_csv_index
from fi_portfolio_tickers import load_decide_union
from fi_narrative import format_verdict_summary, research_status_label, rubric_total, ri

ROOT = Path(__file__).resolve().parents[1]
CORE_JSON = ROOT / "watchlist-ui" / "core-shortlist.json"
MAN = W / "universe_manifest.csv"
SCEN = W / "scenario_results.csv"
RISK = W / "risk_metrics.csv"
MC = W / "monte_carlo_results.csv"
DCF = W / "dcf_sensitivity.csv"
RUB = W / "rubric_scores.csv"
PROFILE_CSV = W / "company_profile.csv"
FH_CSV = W / "finnhub_context.csv"
FH_NEWS_JSON = W / "finnhub_news.json"
ERN_CSV = W / "earnings_data.csv"
RU = W / "rubric_universe.csv"

NARRATIVE_KEYS = (
    "executive_summary",
    "what_company",
    "key_products",
    "strategic_plays",
    "theme_linkage",
    "demand_outlook",
    "holders",
    "market_context",
    "bull_case",
    "bear_case",
    "watch",
    "kill",
    "model_zones",
    "links",
    "signals_intro",
    "at_a_glance",
    "explain_price_chart",
    "explain_scenario",
    "explain_risk",
    "explain_dcf",
    "explain_monte_carlo",
    "explain_rubric",
    "explain_market_context",
    "website",
    "sec_edgar_url",
)

MARK_S = "/* FI_VALUE_JS_START */"
MARK_E = "/* FI_VALUE_JS_END */"


def _f(row: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key) or default)
    except (TypeError, ValueError):
        return default


def load_manifest() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if not MAN.is_file():
        return out
    with MAN.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = (r.get("ticker") or "").strip().upper()
            if t:
                out[t] = r
    return out


def load_core_doc() -> dict:
    if not CORE_JSON.is_file():
        return {}
    return json.loads(CORE_JSON.read_text(encoding="utf-8"))


def load_items() -> dict[str, dict]:
    doc = load_core_doc()
    return {
        (it.get("ticker") or "").strip().upper(): it
        for it in (doc.get("items") or [])
        if it.get("ticker")
    }


def sort_tickers(tickers: list[str], man: dict[str, dict[str, str]]) -> list[str]:
    def key(t: str) -> tuple[str, str]:
        m = man.get(t, {})
        theme = (m.get("theme_label") or m.get("theme_slug") or "").lower()
        return (theme, t)

    return sorted(tickers, key=key)


def js_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def sanitize_narrative_text(s: str) -> str:
    if not s:
        return "—"
    t = str(s).replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\u2028", " ").replace("\u2029", " ")
    if any(ord(c) < 32 for c in t):
        t = "".join(c if ord(c) >= 32 or c == "\n" else " " for c in t)
    return t.replace("\n", " ").strip() or "—"


def build_dcf(ticker: str, dcf_rows: list[dict[str, str]]) -> str | None:
    if not dcf_rows:
        return None
    growths = sorted({round(_f(r, "growth_rate"), 6) for r in dcf_rows})
    waccs = sorted({round(_f(r, "wacc"), 6) for r in dcf_rows})
    if len(growths) != 5 or len(waccs) != 5:
        return None
    grid: dict[tuple[float, float], tuple[float, float]] = {}
    for r in dcf_rows:
        g = round(_f(r, "growth_rate"), 6)
        w = round(_f(r, "wacc"), 6)
        grid[(g, w)] = (_f(r, "implied_price"), _f(r, "upside_pct"))
    row_parts: list[str] = []
    for g in growths:
        cells: list[str] = []
        for w in waccs:
            p, u = grid.get((g, w), (0.0, 0.0))
            cells.append(f"{{p:{p:.2f},u:{u:.0f}}}")
        row_parts.append("[" + ",".join(cells) + "]")
    g_js = ",".join(f"{g:.4g}" for g in growths)
    w_js = ",".join(f"{w:.2g}" for w in waccs)
    rows_js = ",".join(row_parts)
    return f"{{ growths:[{g_js}], waccs:[{w_js}], rows:[{rows_js}] }}"


def scenario_entry(t: str, r: dict[str, str]) -> str:
    price = _f(r, "price")
    cm = (r.get("current_multiple") or "n/a").replace("x", "x")
    metric = "Fwd EPS" if "EPS" in (r.get("metric_type") or "") else "Rev/Sh"
    def sc(prefix: str) -> str:
        cagr = _f(r, f"{prefix}_cagr")
        mult = _f(r, f"{prefix}_multiple")
        px = _f(r, f"{prefix}_price")
        up = _f(r, f"{prefix}_upside")
        prob = _f(r, f"{prefix}_prob", 0.25)
        return (
            f'{{cagr:"{cagr:.0%}",mult:{mult:.0f},price:{px:.2f},'
            f'upside:"{up:+.0f}%",prob:"{prob:.0%}"}}'
        )
    wt_px = _f(r, "weighted_price")
    wt_up = _f(r, "weighted_upside")
    return (
        f"    {js_str(t)}: {{ price:{price:.2f}, metric:{js_str(metric)}, cm:{js_str(cm)}, "
        f"bull:{sc('bull')}, base:{sc('base')}, bear:{sc('bear')}, "
        f"wt:{{price:{wt_px:.2f},upside:\"{wt_up:+.0f}%\"}} }},"
    )


def mc_median_upside(mc_row: dict[str, str] | None) -> str:
    if not mc_row:
        return "—"
    try:
        cur = float(mc_row.get("current_price") or 0)
        med = float(mc_row.get("median_price") or 0)
        if cur <= 0:
            return "—"
        return f"{(med / cur - 1) * 100:+.0f}%"
    except (TypeError, ValueError):
        return "—"


def load_finnhub_news() -> dict[str, list[dict]]:
    if not FH_NEWS_JSON.is_file():
        return {}
    try:
        raw = json.loads(FH_NEWS_JSON.read_text(encoding="utf-8"))
        return {str(k).upper(): v for k, v in raw.items() if isinstance(v, list)}
    except (json.JSONDecodeError, OSError):
        return {}


def build_finnhub_by_ticker(core: list[str], fh: dict[str, dict[str, str]], news: dict[str, list]) -> str:
    lines = ["  var FINNHUB_BY_TICKER = {"]
    for t in core:
        row = fh.get(t, {})
        arts = news.get(t, [])
        arts_js = json.dumps(arts, ensure_ascii=False)
        lines.append(
            f"    {js_str(t)}: {{"
            f"analyst_skew:{js_str(row.get('analyst_skew') or '—')},"
            f"insider_mspr:{js_str(row.get('insider_mspr') or '—')},"
            f"news_7d:{js_str(str(row.get('news_7d') or '—'))},"
            f"next_earnings:{js_str(row.get('next_earnings') or '—')},"
            f"context_line:{js_str(row.get('context_line') or '')},"
            f"articles:{arts_js}"
            f"}},"
        )
    lines.append("  };")
    return "\n".join(lines)


def build_meta_all(man: dict[str, dict[str, str]], order: list[str] | None = None) -> str:
    lines = ["  var META_ALL = {"]
    keys = order if order else sorted(man.keys())
    for t in keys:
        if t not in man:
            continue
        m = man[t]
        name = (
            m.get("name")
            or m.get("company")
            or (m.get("linkage_one_liner") or "").split("—")[0].strip()
            or t
        ).strip()[:48]
        theme_lbl = (m.get("theme_label") or m.get("theme_slug") or "—").strip()
        if "—" in theme_lbl:
            theme_lbl = theme_lbl.split("—")[0].strip()
        link = (m.get("linkage_one_liner") or m.get("link") or "").strip()[:200]
        lines.append(
            f"    {js_str(t)}: {{ name: {js_str(name)}, theme: {js_str(theme_lbl)}, "
            f"link: {js_str(link)} }},"
        )
    lines.append("  };")
    return "\n".join(lines)


def build_core_tickers_set(tickers: list[str]) -> str:
    inner = ",".join(js_str(t) for t in tickers)
    return f"  var CORE_TICKERS = new Set([{inner}]);\n"


def build_peers_by_theme(
    tickers: list[str],
    man: dict[str, dict[str, str]],
    rub: dict[str, dict[str, str]],
    scen: dict[str, dict[str, str]],
    mc: dict[str, dict[str, str]],
) -> str:
    from collections import defaultdict

    by_theme: dict[str, list[dict[str, str]]] = defaultdict(list)
    for t in tickers:
        slug = (man.get(t, {}).get("theme_slug") or "").strip()
        if not slug:
            continue
        rb = rub.get(t, {})
        tot = rubric_total(rb)
        wt = scen.get(t, {})
        wt_up = ""
        if wt:
            try:
                wt_up = f"{float(wt.get('weighted_upside') or 0):+.0f}%"
            except (TypeError, ValueError):
                wt_up = str(wt.get("weighted_upside") or "—")
        by_theme[slug].append(
            {
                "ticker": t,
                "rubric": f"{tot}/24" if tot is not None else "—",
                "wt": wt_up or "—",
                "mc": mc_median_upside(mc.get(t)),
            }
        )
    parts: list[str] = []
    for slug, rows in sorted(by_theme.items()):
        row_js = ",".join(
            "{ticker:"
            + js_str(r["ticker"])
            + ",rubric:"
            + js_str(r["rubric"])
            + ",wt:"
            + js_str(r["wt"])
            + ",mc:"
            + js_str(r["mc"])
            + "}"
            for r in rows
        )
        parts.append(f"    {js_str(slug)}: [{row_js}]")
    return "  var PEERS_BY_THEME = {\n" + ",\n".join(parts) + "\n  };\n"


def build_data_vars(tickers: list[str]) -> str:
    man = load_manifest()
    items = load_items()
    core_doc = load_core_doc()
    as_of = (core_doc.get("as_of") or "").strip()
    scen = load_csv_index(SCEN)
    risk = load_csv_index(RISK)
    mc = load_csv_index(MC)
    rub = load_csv_index(RUB)
    profile = load_csv_index(PROFILE_CSV)
    fh = load_csv_index(FH_CSV)
    earn = load_csv_index(ERN_CSV)
    ex_by = load_exchanges()
    tickers = sort_tickers(tickers, man)

    dcf_by: dict[str, list[dict[str, str]]] = {}
    if DCF.is_file():
        with DCF.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                t = (row.get("ticker") or "").strip().upper()
                if t:
                    dcf_by.setdefault(t, []).append(row)

    meta_lines = ["  var META = {"]
    scen_lines = ["  var SCENARIOS = {"]
    risk_lines = ["  var RISK = {"]
    mc_lines = ["  var MC = {"]
    dcf_lines = ["  var DCF = {"]
    rub_lines = ["  var RUBRIC = {"]
    sowhat_lines = ["  var SOWHAT = {"]
    adv_lines = ["  var ADV = {"]
    narrative_lines = ["  var NARRATIVE = {"]
    fresh_lines = ["  var FRESHNESS = {"]
    signals_lines = ["  var REFRESH_SIGNALS = {"]
    tv_lines = ["  var TV_MAP = {"]

    rub_parts: list[str] = []
    for t in tickers:
        m = man.get(t, {})
        name = (
            m.get("name")
            or m.get("company")
            or (m.get("linkage_one_liner") or "").split("—")[0].strip()
            or t
        ).strip()[:48]
        theme_lbl = (m.get("theme_label") or m.get("theme_slug") or "—").strip()
        if "—" in theme_lbl:
            theme_lbl = theme_lbl.split("—")[0].strip()
        slug = (m.get("theme_slug") or "").strip()
        it = items.get(t, {})
        rs = (it.get("research_status") or "stub").strip()
        rs_lbl = research_status_label(rs)
        alloc = (it.get("alloc_pct") or "").strip()
        meta_lines.append(
            f"    {js_str(t)}: {{ name: {js_str(name)}, theme: {js_str(theme_lbl)}, "
            f"theme_slug: {js_str(slug)}, alloc: {js_str(alloc)}, "
            f"research_status: {js_str(rs)}, research_label: {js_str(rs_lbl)} }},"
        )
        tv_lines.append(f"    {js_str(t)}: {js_str(tv_symbol(t, ex_by))},")

        if t in scen:
            scen_lines.append(scenario_entry(t, scen[t]))
        if t in risk:
            rk = risk[t]
            risk_lines.append(
                f"    {js_str(t)}: {{ beta:{_f(rk,'beta'):.2f}, vol:{_f(rk,'volatility')*100:.1f}, "
                f"maxDD:{_f(rk,'max_drawdown')*100:.1f}, ret1y:{_f(rk,'return_1y')*100:.1f}, "
                f"sharpe:{_f(rk,'sharpe'):.2f}, spyCorr:{_f(rk,'spy_correlation'):.2f} }},"
            )
        if t in mc:
            mcr = mc[t]
            mc_lines.append(
                f"    {js_str(t)}: {{ current:{_f(mcr,'current_price'):.2f}, "
                f"median:{_f(mcr,'median_price'):.2f}, p10:{_f(mcr,'p10'):.2f}, "
                f"p90:{_f(mcr,'p90'):.2f}, prob50up:{_f(mcr,'prob_50pct_up'):.2f}, "
                f"prob30dn:{_f(mcr,'prob_30pct_down'):.2f} }},"
            )
        dcf_obj = build_dcf(t, dcf_by.get(t, []))
        if dcf_obj:
            dcf_lines.append(f"    {js_str(t)}: {dcf_obj},")

        rb = rub.get(t, {})
        if rb:
            rub_parts.append(
                f"{js_str(t)}:[{ri(rb,'growth')},{ri(rb,'margins')},{ri(rb,'balance_sheet')},"
                f"{ri(rb,'durability')},{ri(rb,'valuation')},{ri(rb,'tail_risks')},"
                f"{rubric_total(rb) or 0}]"
            )

        verdict = format_verdict_summary(rb, scen.get(t), mc.get(t), risk.get(t), it)
        if len(verdict) > 320:
            verdict = verdict[:317] + "…"
        try:
            ct = int(it.get("conviction_tier") or 0)
            tier = f"Tier {ct}" if 1 <= ct <= 4 else "Tier 2"
        except (TypeError, ValueError):
            tier = "Tier 2"
        if tier == "Tier 1":
            color = "var(--accent)"
        elif tier == "Tier 4":
            color = "var(--warn)"
        else:
            color = "var(--fg)"
        sowhat_lines.append(
            f"    {js_str(t)}: {{tier:{js_str(tier)},color:{js_str(color)},text:{js_str(verdict)}}},"
        )

        bull = (it.get("qual_bull") or it.get("why_this_name") or "—").strip()
        bear = (it.get("qual_bear") or it.get("research_thesis") or "—").strip()
        kill = (it.get("research_kill") or it.get("key_risk_kill") or "—").strip()
        if len(bull) > 280:
            bull = bull[:277] + "…"
        if len(bear) > 280:
            bear = bear[:277] + "…"
        if len(kill) > 200:
            kill = kill[:197] + "…"
        adv_lines.append(
            f"    {js_str(t)}: {{bull:{js_str(bull)},bear:{js_str(bear)},kill:{js_str(kill)}}},"
        )

        dd = it.get("deep_dive") or {}
        nar_obj = {k: sanitize_narrative_text(dd.get(k) or "—") for k in NARRATIVE_KEYS}
        nar_json = json.dumps(nar_obj, ensure_ascii=False)
        narrative_lines.append(f"    {js_str(t)}: JSON.parse({js_str(nar_json)}),")

        fh_row = fh.get(t, {})
        prof = profile.get(t, {})
        fh_line = (fh_row.get("context_line") or "").strip()
        fh_ok = bool(fh_line and "not configured" not in fh_line.lower())
        prof_date = (prof.get("as_of") or prof.get("pulled_at") or "").strip()
        if "T" in prof_date:
            prof_date = prof_date.split("T")[0]
        earn_date = (earn.get(t, {}).get("last_earnings_date") or earn.get(t, {}).get("as_of") or "").strip()
        fresh_lines.append(
            f"    {js_str(t)}: {{ models_as_of: {js_str(as_of)}, finnhub: {js_str(fh_line or 'missing')}, "
            f"finnhub_ok: {'true' if fh_ok else 'false'}, earnings: {js_str(earn_date or '—')}, "
            f"profile: {js_str(prof_date or '—')}, profile_ok: {'true' if prof_date else 'false'} }},"
        )

        sig = it.get("refresh_signals") or {"bullish": [], "bearish": []}
        bull = json.dumps(sig.get("bullish") or [], ensure_ascii=False)
        bear = json.dumps(sig.get("bearish") or [], ensure_ascii=False)
        signals_lines.append(f"    {js_str(t)}: {{ bullish: {bull}, bearish: {bear} }},")

    meta_lines.append("  };")
    scen_lines.append("  };")
    risk_lines.append("  };")
    mc_lines.append("  };")
    dcf_lines.append("  };")
    rub_lines.append("  " + ",".join(rub_parts) + "\n  };")
    sowhat_lines.append("  };")
    adv_lines.append("  };")
    narrative_lines.append("  };")
    fresh_lines.append("  };")
    signals_lines.append("  };")
    tv_lines.append("  };")
    peers_block = build_peers_by_theme(tickers, man, rub, scen, mc)
    fh_news = load_finnhub_news()
    finnhub_block = build_finnhub_by_ticker(tickers, fh, fh_news)
    meta_all_block = build_meta_all(man, tickers)
    core_set_block = build_core_tickers_set(tickers)

    return (
        "  /* ── Ticker metadata (core shortlist — auto-generated) ── */\n"
        + "\n".join(meta_lines)
        + "\n\n  /* ── Scenario data ──────────────────────────────────── */\n"
        + "\n".join(scen_lines)
        + "\n\n  /* ── Risk metrics ───────────────────────────────────── */\n"
        + "\n".join(risk_lines)
        + "\n\n  /* ── Monte Carlo ────────────────────────────────────── */\n"
        + "\n".join(mc_lines)
        + "\n\n  /* ── DCF sensitivity grids ──────────────────────────── */\n"
        + "\n".join(dcf_lines)
        + "\n\n  /* ── Rubric scores ──────────────────────────────────── */\n"
        + "  // Total = G + M + BS + D + V − T\n"
        + "\n".join(rub_lines)
        + "\n\n  /* ── So-what synthesis ──────────────────────────────── */\n"
        + "\n".join(sowhat_lines)
        + "\n\n  /* ── Adversarial summaries (legacy / memos) ────────── */\n"
        + "\n".join(adv_lines)
        + "\n\n  /* ── Executive narrative sections ─────────────────── */\n"
        + "\n".join(narrative_lines)
        + "\n\n  /* ── Data freshness ─────────────────────────────────── */\n"
        + "\n".join(fresh_lines)
        + "\n\n  /* ── Refresh signals ──────────────────────────────── */\n"
        + "\n".join(signals_lines)
        + "\n\n  /* ── TradingView symbols ──────────────────────────── */\n"
        + "\n".join(tv_lines)
        + "\n\n  /* ── Peers by theme ───────────────────────────────── */\n"
        + peers_block
        + "\n\n  /* ── Finnhub per ticker (core) ────────────────────── */\n"
        + finnhub_block
        + "\n\n  /* ── Universe metadata (picker) ───────────────────── */\n"
        + meta_all_block
        + "\n\n  /* ── Core shortlist set ───────────────────────────── */\n"
        + core_set_block
    )


def patch_dropdown(doc: str) -> str:
    """Rebuild deep-dive select from META only (core tickers)."""
    if "ddSel.innerHTML = \"\"" in doc:
        return doc
    old = (
        "  /* ── Populate ticker dropdown ───────────────────────── */\n"
        "  var ddSel = document.getElementById(\"dd-ticker\");\n"
        "  if (!ddSel) return;\n\n"
        "  var placeholderOpt = document.createElement(\"option\");"
    )
    new = (
        "  /* ── Populate ticker dropdown (core shortlist) ──────── */\n"
        "  var ddSel = document.getElementById(\"dd-ticker\");\n"
        "  if (!ddSel) return;\n"
        "  ddSel.innerHTML = \"\";\n\n"
        "  var placeholderOpt = document.createElement(\"option\");"
    )
    return doc.replace(old, new, 1)


def main() -> None:
    tickers = load_decide_union()
    if not tickers:
        from fi_embed_core import load_core_tickers

        tickers = load_core_tickers()
    if not tickers:
        print("No core tickers", file=sys.stderr)
        sys.exit(2)
    doc = HTML.read_text(encoding="utf-8")
    inner = build_data_vars(tickers)
    block = f"{MARK_S}\n{inner}{MARK_E}\n"

    if MARK_S in doc and MARK_E in doc:
        doc = re.sub(
            re.escape(MARK_S) + r"[\s\S]*?" + re.escape(MARK_E),
            block.rstrip(),
            doc,
            count=1,
        )
    else:
        for legacy_s, legacy_e in (
            ("<!-- FI_VALUE_JS_START -->", "<!-- FI_VALUE_JS_END -->"),
        ):
            if legacy_s in doc:
                doc = re.sub(
                    re.escape(legacy_s) + r"[\s\S]*?" + re.escape(legacy_e),
                    block.rstrip(),
                    doc,
                    count=1,
                )
                break
        else:
            data_pat = re.compile(
                r"  /\* ── Ticker metadata[\s\S]*?  var ADV = \{[\s\S]*?  \};\n\n",
                re.MULTILINE,
            )
            if not data_pat.search(doc):
                print("Could not find META..ADV block in SINGLE_SCREEN_REPORT.html", file=sys.stderr)
                sys.exit(2)
            doc = data_pat.sub(block, doc, count=1)

    doc = doc.replace("<!-- FI_VALUE_JS_START -->", MARK_S)
    doc = doc.replace("<!-- FI_VALUE_JS_END -->", MARK_E)
    doc = patch_dropdown(doc)

    intro_old = (
        "The dropdown is a <strong>cached illustration set</strong> (not the full "
        "<code>report_core_tickers.txt</code> sleeve)"
    )
    intro_new = (
        "The dropdown lists the <strong>Decide shortlist</strong> "
        "(<code>report_core_tickers.txt</code>) — theme order, refreshed each watchlist refresh"
    )
    doc = doc.replace(intro_old, intro_new)

    HTML.write_text(doc, encoding="utf-8")
    print(f"Patched Value JS for {len(tickers)} tickers → {HTML}")


if __name__ == "__main__":
    main()
