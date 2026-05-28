#!/usr/bin/env python3
"""
Per-theme demand scan and per-ticker growth linkage (heuristic + optional overrides).

Writes research/watchlists/theme_growth_lens.json for fi_enrich_core_shortlist.py.

Not investment advice.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from fi_portfolio_tickers import load_decide_union

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
OUT = W / "theme_growth_lens.json"
OVERRIDES = W / "theme_growth_overrides.json"
MAN = W / "universe_manifest.csv"
RUB = W / "rubric_scores.csv"
ERN = W / "earnings_data.csv"
NEWS = W / "finnhub_news.json"
THEME_WEIGHTS = W / "theme_target_weights.json"

LINKAGE_TIER_WEIGHT = {"direct": 3.0, "picks_shovels": 2.0, "sentiment_only": 0.5, "weak": 0.0}

THEME_DEMAND: dict[str, str] = {
    "ai": "Hyperscaler and enterprise AI capex — accelerators, HBM, networking, foundry capacity.",
    "energy": "Power demand from AI data centres, grid build-out, and conventional energy cash flows.",
    "cyber": "Platform consolidation and breach-driven security spend.",
    "auto": "Automation, aerospace/defence programmes, and reshoring capex.",
    "health": "Procedure volume and pipeline-driven biotech/pharma revenue.",
    "quantum": "Government programmes, commercial pilots, and space/launch cadence — often pre-profit.",
    "fintech": "Payments volume and rate-sensitive balances.",
}

IPO_RE = re.compile(r"\bIPO\b|initial public offering|listing", re.I)
GRANT_RE = re.compile(r"\bgrant\b|funding|DARPA|CHIPS|NQI|quantum initiative", re.I)


def load_manifest() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    with MAN.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = (r.get("ticker") or "").strip().upper()
            if t:
                out[t] = r
    return out


def load_rubric() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if not RUB.is_file():
        return out
    with RUB.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = (r.get("ticker") or "").strip().upper()
            if t:
                out[t] = r
    return out


def load_earnings() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if not ERN.is_file():
        return out
    with ERN.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = (r.get("ticker") or "").strip().upper()
            if t:
                out[t] = r
    return out


def load_news() -> dict[str, list[dict]]:
    if not NEWS.is_file():
        return {}
    try:
        doc = json.loads(NEWS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def rubric_total(row: dict[str, str]) -> int | None:
    try:
        return (
            int(row["growth"])
            + int(row["margins"])
            + int(row["balance_sheet"])
            + int(row["durability"])
            + int(row["valuation"])
            - int(row["tail_risks"])
        )
    except (KeyError, ValueError):
        return None


def yoy_pct(earn: dict[str, str]) -> float | None:
    for k in ("rev_yoy_pct", "revenue_yoy_pct"):
        try:
            return float(earn.get(k) or "")
        except (TypeError, ValueError):
            continue
    return None


def infer_linkage_tier(ticker: str, slug: str, link: str) -> str:
    link_l = link.lower()
    etf = ticker in {"QTUM", "SMH"} or "ETF" in link.upper()
    if etf:
        return "picks_shovels"
    space = slug == "quantum" and any(
        x in link_l for x in ("satellite", "launch", "space", "lunar", "orbit", "lander")
    )
    quantum = slug == "quantum" and any(x in link_l for x in ("quantum", "ion", "anneal"))
    if space and "spacex" not in link_l:
        if ticker in {"RKLB", "ASTS", "IRDM", "PL", "KTOS", "RDW", "VOYG", "MDA.TO"}:
            return "direct"
        if ticker in {"BKSY", "SPIR", "SATL", "SIDU", "LUNR"}:
            return "picks_shovels"
    if quantum:
        if ticker in {"IONQ", "RGTI", "QBTS", "INFQ"}:
            return "direct" if "hardware" in link_l or "systems" in link_l else "picks_shovels"
        if ticker in {"QUBT", "QTUM"}:
            return "sentiment_only" if ticker == "QUBT" else "picks_shovels"
    if slug == "ai" and any(x in link_l for x in ("memory", "gpu", "accelerator", "foundry", "hbm")):
        return "direct"
    if "refin" in link_l or "shale" in link_l or "mining" in link_l:
        return "direct"
    return "picks_shovels"


def growth_quality(yoy: float | None, rub: dict[str, str], tier: str) -> str:
    if tier == "sentiment_only":
        return "narrative_only"
    try:
        tail = int(rub.get("tail_risks") or 0)
        margins = int(rub.get("margins") or 0)
    except ValueError:
        tail, margins = 3, 3
    if yoy is not None and yoy > 80 and (margins <= 2 or tail >= 4):
        return "cyclical_peak_risk"
    note = (rub.get("note") or "").lower()
    if yoy is not None and yoy > 40 and tier in {"direct", "picks_shovels"}:
        if "grant" in note or "pre-profit" in note or "pre-revenue" in note:
            return "lumpy"
    return "sustainable"


def recent_catalysts(ticker: str, news_by: dict[str, list]) -> list[str]:
    arts = news_by.get(ticker) or news_by.get(ticker.replace(".", "-")) or []
    out: list[str] = []
    for a in arts[:8]:
        h = (a.get("headline") or "").strip()
        if not h:
            continue
        if IPO_RE.search(h) or GRANT_RE.search(h):
            out.append(h[:120])
        if len(out) >= 3:
            break
    return out


def growth_mechanism(ticker: str, slug: str, link: str, tier: str, yoy: float | None) -> str:
    parts = [link[:100] if link else f"{ticker} in {slug} sleeve."]
    if tier == "sentiment_only":
        parts.append("Price may move on theme beta without proportional revenue.")
    elif tier == "direct":
        parts.append("Revenue tied to theme spend if backlog/contracts convert.")
    if yoy is not None:
        parts.append(f"Latest revenue pace about {yoy:+.0f}% YoY — confirm in filings.")
    return " · ".join(parts)


def capture_score(ticker: str, rub: dict, earn: dict, tier: str) -> float:
    g = 0.0
    try:
        g += float(rub.get("growth") or 0) * 2.0
    except ValueError:
        pass
    yoy = yoy_pct(earn)
    if yoy is not None:
        g += min(yoy / 20.0, 5.0)
    g += LINKAGE_TIER_WEIGHT.get(tier, 0)
    tot = rubric_total(rub)
    if tot is not None:
        g += tot / 30.0
    return g


def main() -> int:
    if os_skip():
        print("FI_SKIP_GROWTH_LENS=1 — skipped", file=sys.stderr)
        return 0

    tickers = load_decide_union()
    man = load_manifest()
    rub_by = load_rubric()
    earn_by = load_earnings()
    news_by = load_news()
    overrides: dict = {}
    if OVERRIDES.is_file():
        try:
            overrides = json.loads(OVERRIDES.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    themes: dict[str, dict] = {}
    for slug, demand in THEME_DEMAND.items():
        themes[slug] = {
            "demand_driver": demand,
            "cycle_position": "mid build-out",
            "recent_theme_headlines": [],
        }

    by_theme: dict[str, list[tuple[str, float]]] = defaultdict(list)
    ticker_out: dict[str, dict] = {}

    for t in tickers:
        m = man.get(t, {})
        slug = (m.get("theme_slug") or "ai").strip().lower()
        link = (m.get("linkage_one_liner") or "").strip()
        rub = rub_by.get(t, {})
        earn = earn_by.get(t, {})
        tier = infer_linkage_tier(t, slug, link)
        yoy = yoy_pct(earn)
        qual = growth_quality(yoy, rub, tier)
        cats = recent_catalysts(t, news_by)
        score = capture_score(t, rub, earn, tier)
        by_theme[slug].append((t, score))
        ticker_out[t] = {
            "theme_slug": slug,
            "linkage_tier": tier,
            "growth_mechanism": growth_mechanism(t, slug, link, tier, yoy),
            "growth_quality": qual,
            "recent_catalysts": cats,
            "growth_capture_score": round(score, 2),
        }

    for slug, pairs in by_theme.items():
        pairs.sort(key=lambda x: -x[1])
        rank = {t: i + 1 for i, (t, _) in enumerate(pairs)}
        for t, _ in pairs:
            ticker_out[t]["within_theme_rank"] = rank.get(t)

    # Theme-level IPO/grant headlines from union news
    for slug in themes:
        headlines: list[str] = []
        for t in tickers:
            if (man.get(t, {}).get("theme_slug") or "").strip().lower() != slug:
                continue
            for h in ticker_out.get(t, {}).get("recent_catalysts") or []:
                if h not in headlines:
                    headlines.append(h)
            if len(headlines) >= 5:
                break
        themes[slug]["recent_theme_headlines"] = headlines[:5]

    ovr_cats = overrides.get("catalysts") or []
    for c in ovr_cats:
        if not isinstance(c, dict):
            continue
        for t in c.get("beneficiary_tickers") or []:
            tu = str(t).strip().upper()
            if tu in ticker_out:
                note = (c.get("linkage_note") or c.get("headline") or "").strip()
                if note:
                    ticker_out[tu].setdefault("recent_catalysts", [])
                    if note not in ticker_out[tu]["recent_catalysts"]:
                        ticker_out[tu]["recent_catalysts"].insert(0, note[:120])

    doc = {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "themes": themes,
        "tickers": ticker_out,
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote theme growth lens ({len(ticker_out)} tickers) → {OUT}", file=sys.stderr)
    return 0


def os_skip() -> bool:
    import os

    return os.environ.get("FI_SKIP_GROWTH_LENS", "").strip() == "1"


if __name__ == "__main__":
    raise SystemExit(main())
