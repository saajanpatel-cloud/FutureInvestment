#!/usr/bin/env python3
"""
Plain-language, progressive bullet narratives for FutureInvestment dashboards.

All formatters use middle-dot separators ( · ) for single-cell HTML/PDF tables.
Not investment advice.
"""
from __future__ import annotations

import math
import re
from datetime import date
from typing import Any

BULLET = " · "


def safe_float(x: Any) -> float | None:
    if x is None or x == "":
        return None
    try:
        v = float(x)
        if math.isnan(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def ri(row: dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(row[key])
    except (KeyError, ValueError):
        return default


def rubric_total(row: dict[str, str]) -> int | None:
    try:
        g = int(row["growth"])
        m = int(row["margins"])
        bs = int(row["balance_sheet"])
        d = int(row["durability"])
        tail = int(row["tail_risks"])
        v = int(row["valuation"])
        return g + m + bs + d + v - tail
    except (KeyError, ValueError):
        return None


def join_bullets(parts: list[str], max_len: int = 520) -> str:
    parts = [p.strip() for p in parts if p and p.strip()]
    if not parts:
        return "—"
    out = BULLET.join(parts)
    if len(out) <= max_len:
        return out
    return out[: max_len - 1] + "…"


def truncate_text(s: str, n: int) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def human_yoy(earn: dict[str, str]) -> str | None:
    yoy = safe_float(earn.get("rev_yoy_pct") or earn.get("revenue_yoy_pct"))
    if yoy is None:
        return None
    if yoy > 0:
        return f"Revenue up {yoy:.0f}% year-on-year"
    if yoy < 0:
        return f"Revenue down {abs(yoy):.0f}% year-on-year"
    return "Revenue flat year-on-year"


def human_margins(earn: dict[str, str]) -> str | None:
    gm = safe_float(earn.get("gross_margin_pct"))
    om = safe_float(earn.get("op_margin_pct"))
    if gm is None and om is None:
        return None
    bits: list[str] = []
    if gm is not None:
        bits.append(f"gross margin {gm:.0f}%")
    if om is not None:
        bits.append(f"operating margin {om:.0f}%")
    if len(bits) == 1:
        return bits[0].capitalize()
    return "Gross margin " + (f"{gm:.0f}%" if gm is not None else "n/a") + ", operating margin " + (
        f"{om:.0f}%" if om is not None else "n/a"
    )


def human_date(iso: str) -> str:
    s = (iso or "").strip()
    if s.startswith("last "):
        s = s[5:].strip()
    try:
        d = date.fromisoformat(s[:10])
        return f"{d.day} {d.strftime('%b')} {d.year}"
    except ValueError:
        return s


def scorecard_phrase(rub: dict[str, str]) -> str | None:
    tot = rubric_total(rub)
    if tot is None:
        return None
    return f"Our scorecard: {tot}/24"


def pool_rank_phrase(it: dict[str, Any]) -> str | None:
    vr = (it.get("valuation_rank") or "").strip()
    if vr:
        return f"Valuation pool rank #{vr}"
    pr = (it.get("pool_rank") or it.get("borda_rank") or "").strip()
    if pr:
        return f"Pool rank #{pr}"
    ranks = it.get("model_ranks_in_pool") or {}
    if isinstance(ranks, dict) and ranks:
        g = ranks.get("growth")
        q = ranks.get("quality")
        if g is not None and q is not None:
            return f"Pool ranks: growth #{g}, quality #{q}"
    return None


def linkage_lead(link: str, max_len: int = 140) -> str:
    return truncate_text(link, max_len)


def format_rubric_note(earn: dict[str, str], linkage: str, max_len: int = 220) -> str:
    """Business first, then growth, then margins."""
    parts: list[str] = []
    link = linkage_lead(linkage, 100)
    if link:
        parts.append(link)
    yoy = human_yoy(earn)
    if yoy:
        parts.append(yoy)
    margins = human_margins(earn)
    if margins:
        parts.append(margins)
    return join_bullets(parts, max_len)


def format_why(
    linkage: str,
    earn: dict[str, str],
    rub: dict[str, str],
    it: dict[str, Any],
) -> str:
    parts: list[str] = []
    link = linkage_lead(linkage)
    if link:
        parts.append(link)
    yoy = human_yoy(earn)
    if yoy:
        parts.append(yoy)
    margins = human_margins(earn)
    if margins:
        parts.append(margins)
    sc = scorecard_phrase(rub)
    if sc:
        parts.append(sc)
    pool = pool_rank_phrase(it)
    if pool:
        parts.append(pool)
    return join_bullets(parts, 480)


def analyst_phrase(skew: str) -> str | None:
    s = (skew or "").strip().lower()
    if s in ("buy-heavy", "buy heavy"):
        return "Most analysts lean buy"
    if s in ("sell-heavy", "sell heavy"):
        return "Most analysts lean sell"
    if s == "mixed":
        return "Analyst views are mixed"
    return None


def insider_phrase(insider_label: str) -> str | None:
    s = (insider_label or "").strip().lower()
    if "bullish" in s:
        return "Insiders bought more than they sold recently"
    if "bearish" in s:
        return "Insiders sold more than they bought recently"
    if "neutral" in s:
        return "Insider trading looked balanced recently"
    return None


def format_market_context(
    analyst_skew: str,
    insider_label: str,
    news: int | None,
    earnings: str,
    *,
    missing_symbol: bool = False,
) -> str:
    if missing_symbol:
        return "No Finnhub data for this listing"
    parts: list[str] = []
    a = analyst_phrase(analyst_skew)
    if a:
        parts.append(a)
    ins = insider_phrase(insider_label)
    if ins:
        parts.append(ins)
    if isinstance(news, int):
        if news >= 20:
            parts.append(f"Heavy news week: {news} stories")
        elif news > 0:
            parts.append(f"{news} news stories in the past week")
        else:
            parts.append("Quiet news week")
    if earnings and earnings != "no data":
        if earnings.startswith("last "):
            parts.append(f"Last earnings: {human_date(earnings)}")
        else:
            parts.append(f"Next earnings around {human_date(earnings)}")
    if not parts:
        return "No Finnhub data for this listing"
    return join_bullets(parts, 420)


def format_kill(rub: dict[str, str], theme_slug: str) -> str:
    tail = ri(rub, "tail_risks", 0)
    growth = ri(rub, "growth", 0)
    valuation = ri(rub, "valuation", 0)
    parts: list[str] = []

    if theme_slug in ("quantum", "space"):
        parts.append("Long-dated theme — reassess if customer spending stays muted into 2027")

    if tail >= 4:
        parts.append("Tail risk is high on our scorecard — watch governance, concentration, and regulation")
    elif tail >= 3:
        parts.append("Elevated tail risk — write down observable kill triggers before sizing")

    if growth <= 2:
        parts.append("Growth score is weak — need a clear inflection, not story alone")

    if valuation <= 2:
        parts.append("Valuation score is low — a de-rating hurts if growth disappoints")

    parts.append("Step away if revenue growth slows two quarters in a row")
    return join_bullets(parts[:4], 420)


def format_research_glance(linkage: str, theme_label: str, kill: str) -> str:
    parts: list[str] = []
    if linkage:
        parts.append(linkage_lead(linkage, 120))
    if theme_label:
        parts.append(f"On {theme_label.lower()} sleeve")
    return join_bullets(parts, 200)


def _strongest_rubric_dim(rub: dict[str, str]) -> tuple[str, int]:
    dims = [
        ("growth", "growth momentum"),
        ("margins", "margins"),
        ("balance_sheet", "balance sheet"),
        ("durability", "competitive durability"),
        ("valuation", "valuation"),
    ]
    best_name, best_v = "fundamentals", 3
    for key, label in dims:
        v = ri(rub, key, 0)
        if v > best_v:
            best_v = v
            best_name = label
    return best_name, best_v


def format_research_thesis(linkage: str, earn: dict[str, str], rub: dict[str, str]) -> str:
    parts: list[str] = []
    if linkage:
        parts.append(linkage_lead(linkage, 130))
    dim, v = _strongest_rubric_dim(rub)
    if v >= 4:
        parts.append(f"Strongest on scorecard: {dim} ({v}/5)")
    yoy = human_yoy(earn)
    if yoy:
        parts.append(yoy)
    sc = scorecard_phrase(rub)
    if sc:
        parts.append(sc)
    return join_bullets(parts, 520)


def format_premortem_stub(rub: dict[str, str], theme_slug: str) -> str:
    tail = ri(rub, "tail_risks", 0)
    growth = ri(rub, "growth", 0)
    if theme_slug in ("quantum", "space"):
        reason = "the theme pays off too late or never gets funded at scale"
    elif tail >= 4:
        reason = "a tail-risk event (regulation, concentration, or governance) overwhelms the thesis"
    elif growth <= 2:
        reason = "growth stalls and the story never converts to sustained earnings"
    else:
        reason = "the market re-rates the stock down when growth decelerates"
    return (
        f"[Auto stub] If this is a poor outcome in five years, the likely reason is {reason}. "
        "Replace after adversarial workshop."
    )


def _qual_templates(theme_slug: str) -> dict[str, list[str]]:
    lib: dict[str, dict[str, list[str]]] = {
        "ai": {
            "bull": ["AI build-out still adding capacity", "Strong product position in the stack"],
            "bear": ["Hyperscaler capex pause", "Customer concentration in a few buyers"],
            "watch": ["Data-centre revenue each quarter", "Capex and custom-silicon commentary"],
        },
        "health": {
            "bull": ["Large addressable market with approved or late-stage assets", "Pipeline optionality beyond lead drug"],
            "bear": ["Payer pushback or competition on price", "Clinical or regulatory setback"],
            "watch": ["Script trends and label expansions", "Trial readouts and guidance"],
        },
        "energy": {
            "bull": ["Power or renewables demand tied to load growth", "Backlog or regulated rate-base expansion"],
            "bear": ["Commodity or power-price collapse", "Policy or execution slip"],
            "watch": ["Rate cases and contracted vs merchant mix", "Backlog conversion"],
        },
        "quantum": {
            "bull": ["Early revenue or strategic contracts", "Balance-sheet runway"],
            "bear": ["Revenue tiny vs valuation", "Technology or funding risk"],
            "watch": ["Guidance vs prints", "Cash burn and dilution"],
        },
        "space": {
            "bull": ["Launch cadence or defence backlog", "Platform adoption"],
            "bear": ["Program delays or budget cuts", "Capital intensity"],
            "watch": ["Order book and manifest timing", "Government budget signals"],
        },
        "cyber": {
            "bull": ["Platform consolidation and recurring revenue", "Security spend resilience"],
            "bear": ["Refresh cycles elongate", "Megacap bundle competition"],
            "watch": ["Billings vs revenue", "Platform customer adds"],
        },
        "auto": {
            "bull": ["Automation and reshoring capex", "Installed-base services growth"],
            "bear": ["Industrial down-cycle", "Integration or competition"],
            "watch": ["Orders and book-to-bill", "Segment margins"],
        },
    }
    return lib.get(theme_slug, {
        "bull": ["Theme tailwind still intact", "Business model fits the sleeve thesis"],
        "bear": ["Macro or cycle turns against the name", "Execution miss vs guidance"],
        "watch": ["Next two earnings vs expectations", "Guidance and margin trend"],
    })


def format_qual_bull_bear_watch(
    rub: dict[str, str],
    linkage: str,
    theme_slug: str,
) -> tuple[str, str, str]:
    tpl = _qual_templates(theme_slug)
    growth = ri(rub, "growth", 0)
    tail = ri(rub, "tail_risks", 0)
    val = ri(rub, "valuation", 0)

    bull_parts = list(tpl["bull"])
    if growth >= 4 and linkage:
        bull_parts.insert(0, truncate_text(linkage, 80))

    bear_parts = list(tpl["bear"])
    if tail >= 4:
        bear_parts.insert(0, "High tail-risk score on our rubric")

    watch_parts = list(tpl["watch"])
    if val <= 2:
        watch_parts.insert(0, "Multiple compression if growth slows")

    return (
        join_bullets(bull_parts[:3], 200),
        join_bullets(bear_parts[:3], 200),
        join_bullets(watch_parts[:3], 200),
    )


def _pct_phrase(x: float | None, label: str) -> str | None:
    if x is None:
        return None
    if x >= 0:
        return f"{label} +{x:.0f}%"
    return f"{label} {x:.0f}%"


def format_verdict_summary(
    rub: dict[str, str],
    sc: dict[str, str] | None,
    mc: dict[str, str] | None,
    rk: dict[str, str] | None,
    it: dict[str, Any],
) -> str:
    tot = rubric_total(rub)
    w_up = safe_float(sc.get("weighted_upside")) if sc else None

    med_up = None
    if mc:
        try:
            cur = float(mc["current_price"])
            med = float(mc["median_price"])
            if cur > 0:
                med_up = (med / cur - 1.0) * 100.0
        except (KeyError, ValueError, ZeroDivisionError):
            pass

    disagree = False
    if tot is not None and tot >= 16 and w_up is not None and w_up < 0:
        disagree = True
    if (
        tot is not None
        and tot >= 16
        and med_up is not None
        and med_up < 0
        and w_up is not None
        and w_up > 20
    ):
        disagree = True

    bits: list[str] = []
    if disagree:
        bits.append("Models disagree — reconcile scorecard vs valuation.")
    elif tot is not None:
        tier = "Strong" if tot >= 18 else "Weak" if tot <= 10 else "Mid"
        bits.append(f"{tier} scorecard ({tot}/24)")
    else:
        bits.append("Scorecard incomplete")

    if w_up is not None:
        if w_up >= 50:
            bits.append(f"Scenario-weighted upside ~{w_up:+.0f}%")
        elif w_up >= 0:
            bits.append(f"Scenario-weighted upside ~{w_up:+.0f}%")
        else:
            bits.append(f"Scenario-weighted downside ~{abs(w_up):.0f}%")

    if med_up is not None:
        p = _pct_phrase(med_up, "MC median")
        if p:
            bits.append(p)

    if rk:
        try:
            sh = float(rk["sharpe"])
            dd = float(rk["max_drawdown"]) * 100.0
            bits.append(f"Sharpe {sh:.1f}, max drawdown ~{dd:.0f}%")
        except (KeyError, ValueError):
            pass

    ranks = it.get("model_ranks_in_pool") or {}
    if isinstance(ranks, dict) and ranks:
        g = ranks.get("growth")
        if g is not None:
            bits.append(f"Growth rank #{g} in pool")

    bits.append("Adversarial review before sizing — not a buy signal.")
    return join_bullets(bits, 400)


THEME_DEMAND: dict[str, str] = {
    "ai": (
        "Hyperscaler and enterprise AI capex remains the primary demand driver for accelerators, "
        "high-bandwidth memory, networking, and custom silicon. Watch customer concentration and "
        "capex digestion cycles."
    ),
    "cyber": (
        "Security spend tends to be more resilient than discretionary IT, but refresh cycles can "
        "elongate when budgets tighten. Platform consolidation favours vendors with broad suites."
    ),
    "energy": (
        "Power demand from data centres, electrification, and grid upgrades supports utilities, "
        "gas/nuclear baseload, and grid equipment. Commodity and rate-case outcomes still matter."
    ),
    "health": (
        "Innovation in biologics, devices, and services can outgrow macro, but payer pressure and "
        "clinical setbacks are ever-present risks."
    ),
    "quantum": (
        "Commercial quantum revenue remains early and uneven; demand is long-dated optionality. "
        "Funding runway and dilution dominate near-term narratives."
    ),
    "auto": (
        "Automation, aerospace, and reshoring capex support industrial names, but orders are "
        "cyclical — book-to-bill and backlog conversion are key checkpoints."
    ),
}


def bullets_to_html(text: str) -> str:
    """Turn middle-dot bullets into HTML paragraphs."""
    t = (text or "").strip()
    if not t or t == "—":
        return "<p class=\"muted\">—</p>"
    parts = [p.strip() for p in t.split(BULLET) if p.strip()]
    if len(parts) <= 1:
        return f"<p>{t}</p>"
    return "".join(f"<p>{html.escape(p)}</p>" for p in parts)


def html_escape(s: str) -> str:
    import html as html_mod

    return html_mod.escape(s)


def compute_research_status(
    rub: dict[str, str],
    theme_slug: str,
    premortem: str,
    override: str | None = None,
    *,
    pack: dict | None = None,
) -> str:
    if override in ("complete", "theme_only", "stub", "adversarial_complete"):
        return override
    if pack and pack.get("workflow_e_complete"):
        return "adversarial_complete"
    if theme_slug in ("quantum", "space"):
        return "theme_only"
    prem = (premortem or "").strip()
    if "[Auto stub]" in prem:
        return "stub"
    tot = rubric_total(rub)
    if tot is not None and tot >= 16:
        return "complete"
    return "stub"


def research_status_label(status: str) -> str:
    return {
        "complete": "Research: adversarial pack recommended",
        "adversarial_complete": "Research: adversarial pack on file — verify before sizing",
        "theme_only": "Research: theme only — full adversarial pack required",
        "stub": "Research: stub — complete adversarial review before sizing",
    }.get(status, "Research: status unknown")


def format_model_zones(
    scen: dict[str, str] | None,
    mc: dict[str, str] | None,
    dcf_mid: tuple[float, float] | None,
) -> str:
    parts: list[str] = []
    if scen:
        try:
            price = float(scen.get("price") or 0)
            wt = float(scen.get("weighted_upside") or 0)
            base = float(scen.get("base_upside") or scen.get("base_price") or 0)
            parts.append(f"Spot at export: ${price:.2f}.")
            parts.append(f"Scenario weighted implied change: {wt:+.0f}% vs spot.")
            bp = scen.get("base_price") or scen.get("bull_price")
            if bp:
                parts.append(f"Base case implied price ${float(scen.get('base_price', 0)):.2f}.")
        except (TypeError, ValueError):
            pass
    if mc:
        try:
            cur = float(mc["current_price"])
            med = float(mc["median_price"])
            p10 = float(mc["p10"])
            p90 = float(mc["p90"])
            med_up = (med / cur - 1) * 100 if cur > 0 else 0
            parts.append(
                f"Monte Carlo: P10 ${p10:.2f}, median ${med:.2f} ({med_up:+.0f}% vs spot), P90 ${p90:.2f}."
            )
        except (KeyError, ValueError, ZeroDivisionError):
            pass
    if dcf_mid and dcf_mid[0] > 0:
        p, u = dcf_mid
        parts.append(f"DCF mid growth × mid WACC anchor: ${p:.2f} ({u:+.0f}% vs spot).")
    if not parts:
        return "Model zones unavailable — re-run valuation refresh."
    read = ""
    if scen:
        try:
            wt = float(scen.get("weighted_upside") or 0)
            if wt < -15:
                read = " Spot is above weighted scenario — patience if you need margin of safety."
            elif wt > 30:
                read = " Models imply material upside vs spot — verify assumptions in filings."
        except (TypeError, ValueError):
            pass
    return join_bullets(parts, 900) + read


def format_section_prose(parts: list[str], max_chars: int = 1600) -> str:
    """Join clauses into one or two readable paragraphs for Monitor."""
    parts = [p.strip() for p in parts if p and p.strip()]
    if not parts:
        return "—"
    if len(parts) <= 2:
        return " ".join(parts)
    mid = max(1, len(parts) // 2)
    p1 = " ".join(parts[:mid])
    p2 = " ".join(parts[mid:])
    out = p1 + "\n\n" + p2
    if len(out) > max_chars:
        return out[: max_chars - 1] + "…"
    return out


def format_what_company_long(
    profile: dict[str, str], man: dict[str, str], earn: dict[str, str]
) -> str:
    summary = (profile.get("business_summary") or "").strip()
    link = (man.get("linkage_one_liner") or "").strip()
    theme_lbl = (man.get("theme_label") or man.get("theme_slug") or "").strip()
    bits: list[str] = []
    if summary:
        bits.append(summary)
    elif link:
        bits.append(link)
    if theme_lbl:
        bits.append(f"It sits in the {theme_lbl} sleeve of this research pack.")
    yoy = human_yoy(earn)
    if yoy:
        bits.append(yoy + ".")
    return format_section_prose(bits, 2000)


def format_explain_price_chart(scen: dict[str, str] | None, theme: str) -> str:
    parts: list[str] = [
        "This chart shows daily price candles from TradingView — useful for timing and volatility, not a buy signal on its own."
    ]
    if scen:
        try:
            price = float(scen.get("price") or 0)
            if price > 0:
                parts.append(f"Spot at last model export was about ${price:.2f}.")
        except (TypeError, ValueError):
            pass
    if theme:
        parts.append(f"Theme context: {theme}.")
    return format_section_prose(parts, 900)


def format_explain_scenario(scen: dict[str, str] | None) -> str:
    if not scen:
        return "Scenario model not available for this ticker — run a full refresh after it joins the core shortlist."
    try:
        wt = float(scen.get("weighted_upside") or 0)
        bear = float(scen.get("bear_upside") or 0)
        bull = float(scen.get("bull_upside") or 0)
        price = float(scen.get("price") or 0)
        wt_px = float(scen.get("weighted_price") or 0)
    except (TypeError, ValueError):
        return "Scenario outputs could not be read — check scenario_results.csv."
    parts = [
        "The bar spans bear, base, and bull implied prices from forward-earnings growth and exit multiples.",
        f"Probability-weighted case implies {wt:+.0f}% vs spot"
        + (f" (about ${wt_px:.2f})" if wt_px > 0 else "")
        + ".",
        f"Bear leg {bear:+.0f}% · bull leg {bull:+.0f}% — use the spread to see how much optimism is in the base case.",
    ]
    if wt < -10:
        parts.append("Weighted upside is negative: the market may already price a strong outcome.")
    elif wt > 25:
        parts.append("Weighted upside is high: confirm assumptions in the next filing before trusting the base case.")
    return format_section_prose(parts, 1100)


def format_explain_risk(risk: dict[str, str] | None) -> str:
    if not risk:
        return "Risk metrics need price history — available for core shortlist names after refresh."
    try:
        beta = float(risk.get("beta") or 0)
        vol = float(risk.get("volatility") or 0) * 100
        mdd = float(risk.get("max_drawdown") or 0) * 100
        sharpe = float(risk.get("sharpe") or 0)
        corr = float(risk.get("spy_correlation") or 0)
    except (TypeError, ValueError):
        return "Risk metrics could not be parsed."
    parts = [
        f"Beta {beta:.2f} measures sensitivity to the broad market; annualised volatility was about {vol:.0f}%.",
        f"Maximum drawdown over the lookback window was {mdd:.0f}% — how far the stock fell from peak to trough.",
        f"Sharpe {sharpe:.2f} summarises return per unit of risk; correlation with the S&P 500 was {corr:.2f}.",
    ]
    if beta > 1.4:
        parts.append("High beta: expect amplified moves versus the index in risk-on and risk-off days.")
    if corr < 0.35:
        parts.append("Low correlation can help diversification if the thesis is uncorrelated to mega-cap tech.")
    return format_section_prose(parts, 1100)


def format_explain_dcf(dcf_mid: tuple[float, float] | None, spot: float) -> str:
    if not dcf_mid or dcf_mid[0] <= 0:
        return (
            "The grid tests five growth rates against five discount rates (WACC). "
            "Each cell is an implied share price from a simplified cash-flow model — compare cells to spot; not a formal fair value."
        )
    p, u = dcf_mid
    parts = [
        "Each cell is an implied price from a discounted cash-flow sketch (growth × WACC).",
        f"Mid-grid anchor is about ${p:.2f} ({u:+.0f}% vs spot at export).",
        "Greener cells mean higher implied upside; red cells mean the model sees overvaluation under those assumptions.",
    ]
    return format_section_prose(parts, 1000)


def format_explain_monte_carlo(mc: dict[str, str] | None) -> str:
    if not mc:
        return "Monte Carlo paths are run for core names — 10,000 simulated prices using recent volatility."
    try:
        cur = float(mc.get("current_price") or 0)
        med = float(mc.get("median_price") or 0)
        p10 = float(mc.get("p10") or 0)
        p90 = float(mc.get("p90") or 0)
        p50 = float(mc.get("prob_50pct_up") or 0) * 100
        p30 = float(mc.get("prob_30pct_down") or 0) * 100
        med_up = (med / cur - 1) * 100 if cur > 0 else 0
    except (TypeError, ValueError):
        return "Monte Carlo outputs could not be read."
    parts = [
        f"The band runs from P10 ${p10:.2f} to P90 ${p90:.2f}; median path about ${med:.2f} ({med_up:+.0f}% vs spot).",
        f"Across simulated paths, {p50:.0f}% finished more than 50% above today's price and {p30:.0f}% fell more than 30%.",
        "This is a statistical summary of recent volatility — not a forecast of the thesis playing out.",
    ]
    return format_section_prose(parts, 1100)


def format_explain_rubric(rub: dict[str, str]) -> str:
    if not rub:
        return "Rubric scores not found — add a row in rubric_scores.csv."
    tot = rubric_total(rub)
    dims = [
        ("Growth", ri(rub, "growth")),
        ("Margins", ri(rub, "margins")),
        ("Balance sheet", ri(rub, "balance_sheet")),
        ("Durability", ri(rub, "durability")),
        ("Valuation", ri(rub, "valuation")),
        ("Tail risks", ri(rub, "tail_risks")),
    ]
    bits = [f"{label} {score}/5" for label, score in dims]
    lead = f"Composite rubric total {tot}/24 before tail-risk penalty." if tot is not None else "Six-dimension rubric:"
    return format_section_prose([lead, "Scores: " + ", ".join(bits) + "."], 900)


def format_explain_market_context(fh_line: str, earnings: str) -> str:
    parts = []
    if fh_line and fh_line != "—":
        parts.append(fh_line)
    if earnings and earnings not in ("no data", "N/A", "—"):
        if earnings.startswith("last "):
            parts.append(f"Earnings: last reported {earnings[5:].strip()}.")
        else:
            parts.append(f"Next earnings date on file: {earnings}.")
    parts.append("Headlines below are from Finnhub (last seven days) — verify material news in primary sources.")
    return format_section_prose(parts, 1000)


def format_at_a_glance(
    sw_tier: str,
    scen: dict[str, str] | None,
    mc: dict[str, str] | None,
    dcf_mid: tuple[float, float] | None,
    rub_total: int | None,
) -> str:
    bits: list[str] = []
    if sw_tier:
        bits.append(sw_tier)
    if rub_total is not None:
        bits.append(f"Rubric {rub_total}/24")
    if scen:
        try:
            bits.append(f"Scenario wt {float(scen.get('weighted_upside') or 0):+.0f}%")
        except (TypeError, ValueError):
            pass
    if mc:
        try:
            cur = float(mc.get("current_price") or 0)
            med = float(mc.get("median_price") or 0)
            if cur > 0:
                bits.append(f"MC median {(med / cur - 1) * 100:+.0f}%")
        except (TypeError, ValueError):
            pass
    if dcf_mid and dcf_mid[1]:
        bits.append(f"DCF mid {dcf_mid[1]:+.0f}%")
    return " · ".join(bits) if bits else "—"


def dcf_mid_from_rows(rows: list[dict[str, str]]) -> tuple[float, float] | None:
    if not rows:
        return None
    try:
        growths = sorted({round(float(r["growth_rate"]), 6) for r in rows if r.get("growth_rate")})
        waccs = sorted({round(float(r["wacc"]), 6) for r in rows if r.get("wacc")})
        if not growths or not waccs:
            return None
        g_mid = growths[len(growths) // 2]
        w_mid = waccs[len(waccs) // 2]
        for r in rows:
            if round(float(r.get("growth_rate") or 0), 6) == g_mid and round(
                float(r.get("wacc") or 0), 6
            ) == w_mid:
                return (float(r.get("implied_price") or 0), float(r.get("upside_pct") or 0))
    except (TypeError, ValueError, KeyError):
        return None
    return None


def format_deep_dive_sections(
    *,
    item: dict[str, Any],
    rub: dict[str, str],
    man: dict[str, str],
    profile: dict[str, str],
    earn: dict[str, str],
    scen: dict[str, str] | None,
    mc: dict[str, str] | None,
    risk: dict[str, str] | None,
    alloc_pct: str,
    prior_as_of: str,
    baseline: bool,
    dcf_rows: list[dict[str, str]] | None = None,
    fh_row: dict[str, str] | None = None,
) -> dict[str, str]:
    link = (man.get("linkage_one_liner") or "").strip()
    theme_slug = (man.get("theme_slug") or "").strip()
    theme_lbl = (man.get("theme_label") or theme_slug or "—").strip()
    summary = (profile.get("business_summary") or "").strip()
    products = (profile.get("key_products") or link or summary[:200] or "—").strip()
    website = (profile.get("website") or "").strip()
    sec = (profile.get("sec_edgar_url") or "").strip()
    holders = (profile.get("holders_top") or "—").strip()
    demand = THEME_DEMAND.get(theme_slug, THEME_DEMAND.get("ai", ""))

    verdict = format_verdict_summary(rub, scen, mc, risk, item)
    exec_text = verdict
    if len(exec_text) < 120:
        exec_text = verdict + " " + (item.get("why_this_name") or "")[:400]

    dcf_mid = dcf_mid_from_rows(dcf_rows or [])
    spot = 0.0
    if scen:
        try:
            spot = float(scen.get("price") or 0)
        except (TypeError, ValueError):
            pass
    tot = rubric_total(rub)
    tier = "Tier 2"
    if tot is not None:
        if tot >= 20:
            tier = "Tier 1"
        elif tot <= 12:
            tier = "Tier 3"
    fh_earn = (fh_row or {}).get("next_earnings") or ""

    sections = {
        "executive_summary": format_section_prose([exec_text, item.get("why_this_name") or ""], 1800),
        "what_company": format_what_company_long(profile, man, earn),
        "key_products": format_section_prose([products, link], 1200),
        "strategic_plays": format_section_prose(
            [item.get("why_this_name") or "", item.get("research_thesis") or link], 1500
        ),
        "theme_linkage": format_section_prose(
            [
                f"This name is mapped to the {theme_lbl} sleeve.",
                demand,
                link,
                f"Indicative allocation within sleeve: {alloc_pct}" if alloc_pct else "",
            ],
            1200,
        ),
        "demand_outlook": format_section_prose([demand, human_yoy(earn) or ""], 1200),
        "holders": holders,
        "market_context": format_explain_market_context(
            (item.get("market_context") or "—")[:900], str(fh_earn)
        ),
        "bull_case": format_section_prose([(item.get("qual_bull") or "—")], 1500),
        "bear_case": format_section_prose([(item.get("qual_bear") or "—")], 1500),
        "watch": format_section_prose([(item.get("qual_watch") or "—")], 1000),
        "kill": format_section_prose(
            [(item.get("key_risk_kill") or item.get("research_kill") or "—")], 1200
        ),
        "premortem": (item.get("research_premortem") or "")[:800],
        "links": join_bullets(
            [f"Website: {website}" if website else "", f"SEC filings: {sec}" if sec else ""],
            500,
        ),
        "signals_intro": (
            "First snapshot — signal deltas appear after the next full refresh."
            if baseline
            else f"Compared to prior refresh: {prior_as_of or 'last run'}."
        ),
        "model_zones": format_model_zones(scen, mc, dcf_mid),
        "at_a_glance": format_at_a_glance(tier, scen, mc, dcf_mid, tot),
        "explain_price_chart": format_explain_price_chart(scen, theme_lbl),
        "explain_scenario": format_explain_scenario(scen),
        "explain_risk": format_explain_risk(risk),
        "explain_dcf": format_explain_dcf(dcf_mid, spot),
        "explain_monte_carlo": format_explain_monte_carlo(mc),
        "explain_rubric": format_explain_rubric(rub),
        "explain_market_context": format_explain_market_context(
            (item.get("market_context") or "—"), str(fh_earn)
        ),
        "website": website,
        "sec_edgar_url": sec,
    }
    return sections
