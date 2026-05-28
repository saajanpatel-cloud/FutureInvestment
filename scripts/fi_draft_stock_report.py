#!/usr/bin/env python3
"""
Generate DRAFT Stock-Deep Dive executive narratives (FI_DRAFT_TICKERS, default NVDA).

Writes draft_report on matching core-shortlist.json items.
Not investment advice.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fi_adversarial import load_packs
from fi_draft_common import ROOT, W, UI, draft_skipped, load_draft_tickers
from fi_draft_price_zones import compute_price_zones
from fi_narrative import (
    dcf_mid_from_rows,
    format_at_a_glance_prose,
    format_deep_dive_sections,
    format_explain_dcf,
    format_explain_market_context,
    format_explain_monte_carlo,
    format_explain_risk,
    format_explain_scenario,
    format_section_prose,
    format_verdict_summary,
    human_yoy,
    rubric_total,
    summarize_financial_history,
)

CORE_JSON = UI / "core-shortlist.json"
MAN = W / "universe_manifest.csv"
RUB = W / "rubric_scores.csv"
ERN = W / "earnings_data.csv"
SCEN = W / "scenario_results.csv"
MC = W / "monte_carlo_results.csv"
RISK = W / "risk_metrics.csv"
DCF = W / "dcf_sensitivity.csv"
PROFILE = W / "company_profile.csv"
FH = W / "finnhub_context.csv"
FH_NEWS = W / "finnhub_news.json"
FIN_HIST = W / "financial_history.csv"
MEMO_DIR = ROOT / "research" / "memoes" / "draft_reports"

SYSTEM = """You are a senior equity research analyst writing an executive investment report.
Output ONLY valid JSON (no markdown fences) matching the schema given.
Rules: education/research only; no personalized buy/sell advice as certainty.
Use ONLY numbers and facts from the input bundle — do not invent filings or earnings beats.
Mention the ticker and company name in every section. Write 2–4 short paragraphs per section (no bullet lists, no middle-dot chains).
When refresh_signals, finnhub, or holders_top are present in the bundle, weave them into the relevant sections explicitly.
Do not use generic sector boilerplate unless it appears in the bundle.
Populate self_check with data_gaps, contradictions_found, corrections_applied after reviewing your own draft.
If why_this_name conflicts with company long_name, flag in contradictions_found.
Use price_zones numbers exactly in valuation section."""

SCHEMA_HINT = """{
  "sections": {
    "at_a_glance": "string",
    "investment_thesis": "string",
    "financial_health": "string",
    "competitive_moat": "string",
    "moat_score": 1-10,
    "valuation": "string",
    "growth_outlook": "string",
    "risks_ranked": [{"risk":"", "severity":"high|med|low"}],
    "bull_bear_debate": {"bull":"", "bear":"", "conclusion":""},
    "latest_earnings": "string",
    "verdict": {
      "rating": "Buy|Hold|Avoid",
      "short": "1y outlook",
      "medium": "3y outlook",
      "long": "5y+ outlook",
      "catalysts": ["..."],
      "major_risks": ["..."]
    }
  },
  "self_check": {
    "data_gaps": [],
    "contradictions_found": [],
    "corrections_applied": []
  }
}"""


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env")


def load_csv_map(path: Path, key: str) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    out: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            k = (r.get(key) or "").strip().upper()
            if k:
                out[k] = r
    return out


def load_fin_history() -> list[dict[str, str]]:
    if not FIN_HIST.is_file():
        return []
    with FIN_HIST.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_dcf_by_ticker() -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    if not DCF.is_file():
        return out
    with DCF.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            t = (row.get("ticker") or "").strip().upper()
            if t:
                out.setdefault(t, []).append(row)
    return out


def _call_openai(prompt: str, model: str) -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.25,
            "response_format": {"type": "json_object"},
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=240) as resp:
        data = json.loads(resp.read().decode())
    return (data["choices"][0]["message"]["content"] or "").strip()


def _call_anthropic(prompt: str, model: str) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    body = json.dumps(
        {
            "model": model,
            "max_tokens": 8192,
            "system": SYSTEM,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=240) as resp:
        data = json.loads(resp.read().decode())
    parts = data.get("content") or []
    return "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()


def _parse_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)


def _fmt_zone(z: dict[str, Any]) -> str:
    bl, bh = z.get("buy_low"), z.get("buy_high")
    sl, sh = z.get("sell_low"), z.get("sell_high")
    spot = z.get("spot")
    parts = []
    if spot is not None:
        parts.append(f"Spot about ${spot:,.2f}")
    if bl is not None and bh is not None:
        parts.append(f"potential buy zone ${bl:,.2f}–${bh:,.2f}")
    if sl is not None and sh is not None:
        parts.append(f"potential sell/trim zone ${sl:,.2f}–${sh:,.2f}")
    return " · ".join(parts)


def _verdict_horizons(
    *,
    ticker: str,
    item: dict[str, Any],
    scen: dict[str, str] | None,
    fh: dict[str, str] | None,
) -> tuple[str, str, str]:
    watch = (item.get("qual_watch") or "Next earnings and guidance").strip()
    kill = (item.get("key_risk_kill") or item.get("research_kill") or "").strip()
    earn_hint = (fh or {}).get("next_earnings") or ""
    short = format_section_prose([watch[:300], f"Next earnings: {earn_hint}" if earn_hint else ""], 500)
    wt = ""
    if scen:
        try:
            wt = f"Scenario-weighted upside about {float(scen.get('weighted_upside') or 0):+.0f}% vs spot."
        except (TypeError, ValueError):
            pass
    medium = format_section_prose(
        [wt, (item.get("qual_bull") or "")[:400], kill[:200] if kill else ""],
        600,
    )
    long_p = format_section_prose(
        [(item.get("why_this_name") or "")[:400], "Revisit rubric and adversarial pack each refresh."],
        500,
    )
    return short, medium, long_p


def heuristic_report(
    *,
    ticker: str,
    item: dict[str, Any],
    rub: dict[str, str],
    man: dict[str, str],
    profile: dict[str, str],
    earn: dict[str, str],
    scen: dict[str, str] | None,
    mc: dict[str, str] | None,
    risk: dict[str, str] | None,
    fh: dict[str, str] | None,
    zones: dict[str, Any],
    fin_sum: dict[str, str],
    dcf_rows: list[dict[str, str]] | None,
) -> dict[str, Any]:
    dcf_mid = dcf_mid_from_rows(dcf_rows or [])
    dd = format_deep_dive_sections(
        item=item,
        rub=rub,
        man=man,
        profile=profile,
        earn=earn,
        scen=scen,
        mc=mc,
        risk=risk,
        alloc_pct=item.get("alloc_pct") or "",
        prior_as_of="",
        baseline=False,
        dcf_rows=dcf_rows,
        fh_row=fh,
    )
    tot = rubric_total(rub)
    dur = int(rub.get("durability") or 3)
    moat_score = min(10, max(1, dur * 2))
    wt = (scen or {}).get("weighted_upside", "")
    rating = "Hold"
    try:
        wtu = float(str(wt).replace("%", ""))
        if wtu > 40 and tot and tot >= 18:
            rating = "Buy"
        elif wtu < 0 or (tot and tot <= 12):
            rating = "Avoid"
    except (TypeError, ValueError):
        pass

    risks = []
    if item.get("key_risk_kill"):
        risks.append({"risk": str(item["key_risk_kill"])[:200], "severity": "high"})
    if item.get("qual_bear"):
        risks.append({"risk": str(item["qual_bear"])[:200], "severity": "med"})
    if not risks:
        risks.append({"risk": f"{ticker}: review kill criteria in the rubric pack.", "severity": "med"})
    v_short, v_medium, v_long = _verdict_horizons(ticker=ticker, item=item, scen=scen, fh=fh)
    spot = 0.0
    if scen:
        try:
            spot = float(scen.get("price") or 0)
        except (TypeError, ValueError):
            pass
    return {
        "sections": {
            "at_a_glance": format_at_a_glance_prose(
                ticker, profile, rub, scen, mc, fh, item, dcf_mid=dcf_mid
            ),
            "investment_thesis": format_section_prose(
                [
                    (profile.get("business_summary") or "")[:800],
                    item.get("why_this_name") or "",
                    dd.get("theme_linkage") or "",
                ],
                2000,
            ),
            "financial_health": format_section_prose(
                [
                    fin_sum.get("summary", ""),
                    f"Financial trend: {fin_sum.get('trend_label', 'mixed')}.",
                    (profile.get("holders_top") or "")[:400],
                    dd.get("explain_rubric") or "",
                ],
                2000,
            ),
            "competitive_moat": format_section_prose(
                [
                    f"Moat score {moat_score}/10 (rubric durability {dur}/5).",
                    dd.get("bull_case") or "",
                ],
                2000,
            ),
            "moat_score": moat_score,
            "valuation": format_section_prose(
                [
                    _fmt_zone(zones),
                    dd.get("model_zones") or "",
                    format_explain_scenario(scen),
                    format_explain_dcf(dcf_mid, spot),
                ],
                2500,
            ),
            "growth_outlook": (dd.get("demand_outlook") or "")[:2000],
            "risks_ranked": risks,
            "bull_bear_debate": {
                "bull": format_section_prose([(item.get("qual_bull") or "—")], 1200),
                "bear": format_section_prose([(item.get("qual_bear") or "—")], 1200),
                "conclusion": format_verdict_summary(rub, scen, mc, risk, item)[:800],
            },
            "latest_earnings": format_section_prose(
                [
                    dd.get("market_context") or item.get("market_context") or "",
                    format_explain_market_context(
                        (item.get("market_context") or "")[:400],
                        str((fh or {}).get("next_earnings") or ""),
                    ),
                    human_yoy(earn) or "",
                ],
                1500,
            ),
            "verdict": {
                "rating": rating,
                "short": v_short,
                "medium": v_medium,
                "long": v_long,
                "catalysts": [(item.get("qual_watch") or f"{ticker} earnings")[:120]],
                "major_risks": [r["risk"] for r in risks[:2]],
            },
        },
        "self_check": {
            "data_gaps": zones.get("data_gaps") or [],
            "contradictions_found": [],
            "corrections_applied": ["Heuristic template used — no LLM self-check pass."],
        },
    }


def _load_finnhub_articles(ticker: str, limit: int = 8) -> list[dict[str, Any]]:
    if not FH_NEWS.is_file():
        return []
    try:
        doc = json.loads(FH_NEWS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    rows = doc.get(ticker) or doc.get(ticker.upper()) or []
    if isinstance(rows, dict):
        rows = rows.get("articles") or rows.get("news") or []
    return list(rows)[:limit] if isinstance(rows, list) else []


def build_bundle(
    ticker: str,
    item: dict[str, Any],
    rub: dict[str, str],
    man: dict[str, str],
    profile: dict[str, str],
    earn: dict[str, str],
    scen: dict[str, str] | None,
    mc: dict[str, str] | None,
    risk: dict[str, str] | None,
    fh: dict[str, str] | None,
    zones: dict[str, Any],
    fin_sum: dict[str, str],
    pack: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "long_name": profile.get("long_name") or man.get("name"),
        "why_this_name": item.get("why_this_name"),
        "theme": man.get("theme_label") or man.get("theme_slug"),
        "rubric": rub,
        "earnings": earn,
        "scenario": scen,
        "monte_carlo": mc,
        "risk": risk,
        "finnhub": fh,
        "finnhub_articles": _load_finnhub_articles(ticker),
        "holders_top": profile.get("holders_top"),
        "refresh_signals": item.get("refresh_signals"),
        "price_zones": zones,
        "financial_history": fin_sum,
        "qual_bull": item.get("qual_bull"),
        "qual_bear": item.get("qual_bear"),
        "qual_watch": item.get("qual_watch"),
        "adversarial": pack,
        "deep_dive_headline": (item.get("deep_dive") or {}).get("executive_summary"),
        "deep_dive": item.get("deep_dive"),
    }


def generate_llm(bundle: dict[str, Any], zones: dict[str, Any]) -> dict[str, Any]:
    provider = "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "openai"
    model = os.environ.get("FI_DRAFT_MODEL") or (
        "claude-sonnet-4-20250514" if provider == "anthropic" else "gpt-4o"
    )
    prompt = (
        f"Schema:\n{SCHEMA_HINT}\n\n"
        f"price_zones (use exactly in valuation):\n{json.dumps(zones, indent=2)}\n\n"
        f"Facts bundle:\n{json.dumps(bundle, indent=2)[:28000]}"
    )
    raw = _call_anthropic(prompt, model) if provider == "anthropic" else _call_openai(prompt, model)
    doc = _parse_json(raw)
    if "sections" not in doc:
        raise ValueError("LLM response missing sections")
    return doc


def write_memo(ticker: str, report: dict[str, Any]) -> None:
    MEMO_DIR.mkdir(parents=True, exist_ok=True)
    path = MEMO_DIR / f"{ticker}.md"
    sec = report.get("sections") or {}
    lines = [f"# DRAFT report — {ticker}", f"as_of: {report.get('as_of')}", ""]
    for key in (
        "at_a_glance",
        "investment_thesis",
        "financial_health",
        "competitive_moat",
        "valuation",
        "growth_outlook",
        "latest_earnings",
    ):
        if sec.get(key):
            lines.append(f"## {key.replace('_', ' ').title()}\n\n{sec[key]}\n")
    v = sec.get("verdict") or {}
    if v:
        lines.append(f"## Verdict\n\n**{v.get('rating')}**\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    _load_dotenv()
    if draft_skipped():
        print("SKIP: FI_SKIP_DRAFT_REPORT=1", file=sys.stderr)
        return 0
    tickers = load_draft_tickers()
    if not CORE_JSON.is_file():
        print(f"Missing {CORE_JSON}", file=sys.stderr)
        return 2

    rub_by = load_csv_map(RUB, "ticker")
    man_by = load_csv_map(MAN, "ticker")
    prof_by = load_csv_map(PROFILE, "ticker")
    earn_by = load_csv_map(ERN, "ticker")
    scen_by = load_csv_map(SCEN, "ticker")
    mc_by = load_csv_map(MC, "ticker")
    risk_by = load_csv_map(RISK, "ticker")
    fh_by = load_csv_map(FH, "ticker")
    dcf_by = load_dcf_by_ticker()
    fin_rows = load_fin_history()
    packs = load_packs()

    doc = json.loads(CORE_JSON.read_text(encoding="utf-8"))
    items = doc.get("items") or []
    by_ticker = {(it.get("ticker") or "").strip().upper(): it for it in items if it.get("ticker")}
    as_of = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    has_llm = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"))

    for ticker in tickers:
        it = by_ticker.get(ticker)
        if not it:
            print(f"WARN: {ticker} not on core shortlist — skip", file=sys.stderr)
            continue
        rub = rub_by.get(ticker, {})
        man = man_by.get(ticker, {})
        profile = prof_by.get(ticker, {})
        earn = earn_by.get(ticker, {})
        scen = scen_by.get(ticker)
        mc = mc_by.get(ticker)
        risk = risk_by.get(ticker)
        zones = compute_price_zones(
            scen=scen, mc=mc, earn=earn, dcf_rows=dcf_by.get(ticker)
        )
        fin_sum = summarize_financial_history(ticker, fin_rows)
        bundle = build_bundle(
            ticker,
            it,
            rub,
            man,
            profile,
            earn,
            scen,
            mc,
            risk,
            fh_by.get(ticker),
            zones,
            fin_sum,
            packs.get(ticker),
        )
        try:
            if has_llm:
                llm_doc = generate_llm(bundle, zones)
                sections = llm_doc.get("sections") or {}
                self_check = llm_doc.get("self_check") or {}
            else:
                llm_doc = heuristic_report(
                    ticker=ticker,
                    item=it,
                    rub=rub,
                    man=man,
                    profile=profile,
                    earn=earn,
                    scen=scen,
                    mc=mc,
                    risk=risk,
                    fh=fh_by.get(ticker),
                    zones=zones,
                    fin_sum=fin_sum,
                    dcf_rows=dcf_by.get(ticker),
                )
                sections = llm_doc["sections"]
                self_check = llm_doc["self_check"]
        except Exception as ex:
            print(f"WARN: {ticker} LLM failed ({ex}) — heuristic", file=sys.stderr)
            llm_doc = heuristic_report(
                ticker=ticker,
                item=it,
                rub=rub,
                man=man,
                profile=profile,
                earn=earn,
                scen=scen,
                mc=mc,
                risk=risk,
                fh=fh_by.get(ticker),
                zones=zones,
                fin_sum=fin_sum,
                dcf_rows=dcf_by.get(ticker),
            )
            sections = llm_doc["sections"]
            self_check = llm_doc["self_check"]

        gaps = list(self_check.get("data_gaps") or [])
        gaps.extend(zones.get("data_gaps") or [])
        self_check["data_gaps"] = list(dict.fromkeys(gaps))

        it["draft_report"] = {
            "sections": sections,
            "price_zones": zones,
            "self_check": self_check,
            "as_of": as_of,
            "pilot": False,
            "source": "llm" if has_llm else "heuristic",
        }
        if self_check.get("data_gaps"):
            print(f"  {ticker} self-check gaps: {'; '.join(self_check['data_gaps'][:3])}", file=sys.stderr)
        write_memo(ticker, it["draft_report"])
        print(f"  {ticker}: draft_report written ({'LLM' if has_llm else 'heuristic'})", file=sys.stderr)

    CORE_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {CORE_JSON} for {','.join(tickers)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
