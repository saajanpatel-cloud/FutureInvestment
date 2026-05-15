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

from fi_embed_core import HTML, W, load_core_tickers, load_csv_index
from fi_narrative import format_verdict_summary, rubric_total, ri

ROOT = Path(__file__).resolve().parents[1]
CORE_JSON = ROOT / "watchlist-ui" / "core-shortlist.json"
MAN = W / "universe_manifest.csv"
SCEN = W / "scenario_results.csv"
RISK = W / "risk_metrics.csv"
MC = W / "monte_carlo_results.csv"
DCF = W / "dcf_sensitivity.csv"
RUB = W / "rubric_scores.csv"

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


def load_items() -> dict[str, dict]:
    if not CORE_JSON.is_file():
        return {}
    doc = json.loads(CORE_JSON.read_text(encoding="utf-8"))
    return {
        (it.get("ticker") or "").strip().upper(): it
        for it in (doc.get("items") or [])
        if it.get("ticker")
    }


def js_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


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


def build_data_vars(tickers: list[str]) -> str:
    man = load_manifest()
    items = load_items()
    scen = load_csv_index(SCEN)
    risk = load_csv_index(RISK)
    mc = load_csv_index(MC)
    rub = load_csv_index(RUB)

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
        meta_lines.append(f"    {js_str(t)}: {{ name: {js_str(name)}, theme: {js_str(theme_lbl)} }},")

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

        it = items.get(t, {})
        verdict = format_verdict_summary(rb, scen.get(t), mc.get(t), risk.get(t), it)
        if len(verdict) > 320:
            verdict = verdict[:317] + "…"
        tier = "Tier 2"
        tot = rubric_total(rb)
        if tot is not None:
            if tot >= 20:
                tier = "Tier 1"
            elif tot <= 12:
                tier = "Tier 3"
        color = "var(--accent)" if tier == "Tier 1" else ("var(--warn)" if tier == "Tier 3" else "var(--fg)")
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

    meta_lines.append("  };")
    scen_lines.append("  };")
    risk_lines.append("  };")
    mc_lines.append("  };")
    dcf_lines.append("  };")
    rub_lines.append("  " + ",".join(rub_parts) + "\n  };")
    sowhat_lines.append("  };")
    adv_lines.append("  };")

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
        + "\n\n  /* ── Adversarial summaries ──────────────────────────── */\n"
        + "\n".join(adv_lines)
        + "\n"
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
        "The dropdown lists the live <strong>Decide shortlist</strong> "
        "(<code>report_core_tickers.txt</code>) — refreshed on each full watchlist refresh"
    )
    doc = doc.replace(intro_old, intro_new)

    HTML.write_text(doc, encoding="utf-8")
    print(f"Patched Value JS for {len(tickers)} tickers → {HTML}")


if __name__ == "__main__":
    main()
