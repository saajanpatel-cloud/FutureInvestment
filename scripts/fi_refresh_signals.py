#!/usr/bin/env python3
"""Compute per-ticker bullish/bearish refresh_signals vs prior snapshot. Not investment advice."""
from __future__ import annotations

import json
from typing import Any

from fi_embed_core import CORE_JSON, PRIOR_JSON, W, load_csv_index
from fi_narrative import ri, rubric_total, safe_float

FH = W / "finnhub_context.csv"
SCEN = W / "scenario_results.csv"
MC = W / "monte_carlo_results.csv"
RUB = W / "rubric_scores.csv"
ERN = W / "earnings_data.csv"
COMP = W / "universe_composite_rank.csv"


def _skew_rank(s: str) -> int:
    s = (s or "").strip().lower()
    if "buy" in s and "sell" not in s:
        return 2
    if "sell" in s:
        return 0
    if "mixed" in s:
        return 1
    return -1


def _insider_rank(label: str) -> int:
    s = (label or "").strip().lower()
    if "bullish" in s:
        return 2
    if "bearish" in s:
        return 0
    return 1


def _sig(label: str, detail: str) -> dict[str, str]:
    return {"label": label, "detail": detail}


def compute_refresh_signals(
    ticker: str,
    *,
    prior: dict[str, Any],
    rub: dict[str, str],
    fh: dict[str, str],
    scen: dict[str, str],
    mc: dict[str, str],
    earn: dict[str, str],
    comp: dict[str, str],
    delta: dict[str, Any],
    baseline: bool,
) -> dict[str, list[dict[str, str]]]:
    bullish: list[dict[str, str]] = []
    bearish: list[dict[str, str]] = []
    if baseline or not prior:
        return {"bullish": bullish, "bearish": bearish}

    cur_sk = fh.get("analyst_skew", "")
    pri_sk = str(prior.get("analyst_skew") or "")
    if cur_sk and pri_sk:
        cr, pr = _skew_rank(cur_sk), _skew_rank(pri_sk)
        if cr > pr:
            bullish.append(_sig("Analyst skew improved", f"Now {cur_sk} vs {pri_sk} last refresh."))
        elif cr < pr:
            bearish.append(_sig("Analyst skew worsened", f"Now {cur_sk} vs {pri_sk} last refresh."))

    cur_in = fh.get("insider_mspr", "")
    pri_in = str(prior.get("insider_mspr") or "")
    if cur_in and pri_in:
        cr, pr = _insider_rank(cur_in), _insider_rank(pri_in)
        if cr > pr:
            bullish.append(_sig("Insider tone more bullish", cur_in))
        elif cr < pr:
            bearish.append(_sig("Insider tone more bearish", cur_in))

    yoy = safe_float(earn.get("rev_yoy_pct") or earn.get("revenue_yoy_pct"))
    yoy_p = safe_float(prior.get("rev_yoy_pct"))
    if yoy is not None and yoy_p is not None:
        dy = yoy - yoy_p
        if dy >= 5:
            bullish.append(_sig("Revenue momentum strengthened", f"YoY pace up {dy:+.1f} pp vs prior refresh."))
        elif dy <= -5:
            bearish.append(_sig("Revenue momentum weakened", f"YoY pace down {dy:+.1f} pp vs prior refresh."))

    tot = rubric_total(rub)
    tot_p = prior.get("rubric_total")
    if tot is not None and tot_p is not None:
        try:
            dr = tot - int(tot_p)
            if dr >= 2:
                bullish.append(_sig("Scorecard strengthened", f"Rubric total {dr:+d} to {tot}/24."))
            elif dr <= -2:
                bearish.append(_sig("Scorecard weakened", f"Rubric total {dr:+d} to {tot}/24."))
        except (TypeError, ValueError):
            pass

    tail = ri(rub, "tail_risks", 0)
    tail_p = prior.get("rubric_tail")
    if tail_p is not None:
        try:
            tp = int(tail_p)
            if tail < tp:
                bullish.append(_sig("Tail risk eased", f"Tail score {tp} → {tail}."))
            elif tail > tp and tail >= 4:
                bearish.append(_sig("Tail risk elevated", f"Tail score {tp} → {tail}."))
        except (TypeError, ValueError):
            pass

    rk_cur = safe_float(comp.get("composite_rank")) if comp else None
    rk_p = safe_float(prior.get("composite_rank"))
    if rk_cur is not None and rk_p is not None:
        dcr = rk_p - rk_cur
        if dcr >= 10:
            bullish.append(_sig("Composite rank improved", f"Rank #{int(rk_p)} → #{int(rk_cur)}."))
        elif dcr <= -10:
            bearish.append(_sig("Composite rank slipped", f"Rank #{int(rk_p)} → #{int(rk_cur)}."))

    w_up = safe_float(scen.get("weighted_upside"))
    w_up_p = safe_float(prior.get("weighted_upside"))
    if w_up is not None and w_up_p is not None:
        dw = w_up - w_up_p
        if dw >= 10:
            bullish.append(_sig("Valuation support improved", f"Weighted scenario Δ% up {dw:+.0f} pp."))
        elif dw <= -10:
            bearish.append(_sig("Valuation stress increased", f"Weighted scenario Δ% down {dw:+.0f} pp."))

    p50 = safe_float(mc.get("prob_50pct_up"))
    p50_p = safe_float(prior.get("prob_50pct_up"))
    if p50 is not None and p50_p is not None and p50 - p50_p >= 5:
        bullish.append(_sig("Monte Carlo upside probability rose", f"P(>50% up) {p50_p:.1f}% → {p50:.1f}%."))
    p30 = safe_float(mc.get("prob_30pct_down"))
    p30_p = safe_float(prior.get("prob_30pct_down"))
    if p30 is not None and p30_p is not None:
        if p30 - p30_p >= 5:
            bearish.append(_sig("Monte Carlo downside risk rose", f"P(>30% down) {p30_p:.1f}% → {p30:.1f}%."))
        elif p30_p - p30 >= 5:
            bullish.append(_sig("Monte Carlo downside eased", f"P(>30% down) {p30_p:.1f}% → {p30:.1f}%."))

    db = safe_float(prior.get("borda"))
    # current borda from selection memo if needed - skip for v1

    added = {a.get("ticker") for a in (delta.get("added") or [])}
    if ticker in added:
        bullish.append(_sig("Added to shortlist", "Entered the Decide core set this refresh."))

    return {"bullish": bullish, "bearish": bearish}


def enrich_all() -> None:
    if not CORE_JSON.is_file():
        return
    doc = json.loads(CORE_JSON.read_text(encoding="utf-8"))
    delta = (doc.get("selection_memo") or {}).get("shortlist_delta") or {}
    baseline = bool(delta.get("baseline_established"))

    prior_by: dict[str, dict] = {}
    if PRIOR_JSON.is_file():
        prior_by = json.loads(PRIOR_JSON.read_text(encoding="utf-8")).get("by_ticker") or {}

    rub_by = load_csv_index(RUB)
    fh_by = load_csv_index(FH)
    scen_by = load_csv_index(SCEN)
    mc_by = load_csv_index(MC)
    earn_by = load_csv_index(ERN)
    comp_by = load_csv_index(COMP) if COMP.is_file() else {}

    for it in doc.get("items") or []:
        t = (it.get("ticker") or "").strip().upper()
        if not t:
            continue
        it["refresh_signals"] = compute_refresh_signals(
            t,
            prior=prior_by.get(t) or {},
            rub=rub_by.get(t, {}),
            fh=fh_by.get(t, {}),
            scen=scen_by.get(t, {}),
            mc=mc_by.get(t, {}),
            earn=earn_by.get(t, {}),
            comp=comp_by.get(t, {}),
            delta=delta,
            baseline=baseline,
        )

    CORE_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    enrich_all()
    print("Updated refresh_signals on core-shortlist.json", file=sys.stderr)
