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
