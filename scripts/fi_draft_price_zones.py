#!/usr/bin/env python3
"""
Deterministic buy/sell price zones for DRAFT Stock-Deep Dive from scenario, MC, DCF, analyst targets.

Not investment advice.
"""
from __future__ import annotations

from typing import Any

from fi_narrative import dcf_mid_from_rows, safe_float


def _min_present(*vals: float | None) -> float | None:
    xs = [v for v in vals if v is not None and v > 0]
    return min(xs) if xs else None


def _max_present(*vals: float | None) -> float | None:
    xs = [v for v in vals if v is not None and v > 0]
    return max(xs) if xs else None


def compute_price_zones(
    *,
    scen: dict[str, str] | None,
    mc: dict[str, str] | None,
    earn: dict[str, str] | None,
    dcf_rows: list[dict[str, str]] | None,
) -> dict[str, Any]:
    scen = scen or {}
    mc = mc or {}
    earn = earn or {}
    spot = safe_float(scen.get("price"))
    bear_px = safe_float(scen.get("bear_price"))
    base_px = safe_float(scen.get("base_price"))
    bull_px = safe_float(scen.get("bull_price"))
    p10 = safe_float(mc.get("p10"))
    p90 = safe_float(mc.get("p90"))
    a_low = safe_float(earn.get("analyst_target_low"))
    a_high = safe_float(earn.get("analyst_target_high"))
    dcf_mid = dcf_mid_from_rows(dcf_rows or [])
    dcf_px = dcf_mid[0] if dcf_mid else None

    buy_low = _min_present(bear_px, p10, a_low)
    buy_high = _min_present(base_px, dcf_px, spot)
    if buy_low is not None and buy_high is not None and buy_low > buy_high:
        buy_low, buy_high = buy_high, buy_low

    if base_px is not None:
        sell_low = base_px if spot is None or spot <= base_px else max(base_px, spot)
    else:
        sell_low = spot
    sell_high = _max_present(bull_px, p90, a_high)

    methodology = (
        "Potential buy zone spans model bear/P10/low analyst target through base/DCF mid "
        "(capped near spot when already discounted). Potential sell/trim zone runs from "
        "base through bull/P90/high analyst target. Education only — verify in filings."
    )
    if (
        buy_low is not None
        and buy_high is not None
        and sell_low is not None
        and sell_high is not None
        and buy_high >= sell_low
    ):
        methodology += " Ranges overlap — models do not show a clear discount buffer."

    gaps: list[str] = []
    if bear_px is None:
        gaps.append("scenario_bear")
    if base_px is None:
        gaps.append("scenario_base")
    if bull_px is None:
        gaps.append("scenario_bull")

    def rnd(x: float | None) -> float | None:
        return round(x, 2) if x is not None else None

    return {
        "spot": rnd(spot),
        "buy_low": rnd(buy_low),
        "buy_high": rnd(buy_high),
        "sell_low": rnd(sell_low),
        "sell_high": rnd(sell_high),
        "currency": "USD",
        "methodology": methodology,
        "data_gaps": gaps,
    }
