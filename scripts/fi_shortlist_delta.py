#!/usr/bin/env python3
"""
Build selection_memo.shortlist_delta vs _shortlist_prior.json (last refresh).

Called from fi_select_shortlist_growth.py after pick.
Not investment advice.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fi_embed_core import PRIOR_JSON, W
from fi_select_shortlist_growth import rubric_total, safe_float

ROOT = Path(__file__).resolve().parents[1]
RANK_CSV = W / "universe_valuation_rank.csv"
COMPOSITE_CSV = W / "universe_composite_rank.csv"

REASON_LABELS: dict[str, str] = {
    "consensus_pick": "Composite pool + theme cap",
    "backfill": "Backfill to minimum shortlist size",
    "theme_cap": "Theme bucket full",
    "below_composite_pool": "Outside top composite pool",
    "below_valuation_pool": "Outside top valuation pool",
    "not_in_pool": "Outside selection pool",
    "no_signal_data": "Missing universe model row",
    "consensus_fell": "In pool but lost after cap ranking",
}


def load_prior() -> dict[str, Any]:
    if not PRIOR_JSON.is_file():
        return {}
    try:
        return json.loads(PRIOR_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def ticker_metrics(
    t: str,
    rub_by: dict[str, dict[str, str]],
    earn: dict[str, dict[str, str]],
    scores: dict[str, float],
    rk: dict[str, dict[str, str]] | None,
    ck: dict[str, dict[str, str]] | None,
) -> dict[str, Any]:
    r = rub_by.get(t, {})
    tot = rubric_total(r)
    yoy = safe_float(earn.get(t, {}).get("rev_yoy_pct"))
    out: dict[str, Any] = {
        "rubric_total": tot,
        "borda": round(scores.get(t, 0.0), 1) if t in scores else None,
        "rev_yoy_pct": round(yoy, 1) if yoy is not None else None,
    }
    if rk and t in rk:
        out["valuation_rank"] = (rk[t].get("valuation_rank") or "").strip()
        try:
            out["valuation_score"] = float(rk[t].get("valuation_score") or 0)
        except (TypeError, ValueError):
            pass
    if ck and t in ck:
        out["composite_rank"] = (ck[t].get("composite_rank") or "").strip()
        try:
            out["composite_score"] = float(ck[t].get("composite_score") or 0)
        except (TypeError, ValueError):
            pass
        for k in ("pct_scenario", "pct_rubric", "pct_risk", "pct_mc", "pct_dcf"):
            v = (ck[t].get(k) or "").strip()
            if v:
                out[k] = v
    return out


def drop_reason(
    t: str,
    cap_casualties: list[str],
    pool_set: set[str],
    theme_by: dict[str, str],
    picked: list[str],
    rk: dict[str, dict[str, str]] | None,
    ck: dict[str, dict[str, str]] | None,
    pool_top: int,
    caps: dict[str, int],
) -> tuple[str, str]:
    slug = theme_by.get(t, "")
    cap = caps.get(slug, 0)
    if t in cap_casualties:
        holders = [p for p in picked if theme_by.get(p) == slug]
        note = (
            f"{slug} cap (max {cap}): slots held by "
            f"{', '.join(holders[:4]) or 'other names'}."
            if holders
            else f"Theme cap ({slug}, max {cap}) filled before this name ranked in."
        )
        return "theme_cap", note

    if ck is not None:
        if t not in ck:
            return "no_signal_data", "Missing one or more universe signals (scenario/risk/MC/DCF/rubric)."
        if t not in pool_set:
            cr = (ck[t].get("composite_rank") or "?").strip()
            return (
                "below_composite_pool",
                f"Composite rank #{cr} — outside top ~{pool_top} pool this refresh.",
            )
        return "consensus_fell", "In composite pool but did not make the cap-constrained shortlist."

    if t not in pool_set:
        if rk and t in rk:
            vr = (rk[t].get("valuation_rank") or "?").strip()
            return (
                "below_valuation_pool",
                f"Valuation rank #{vr} — outside top ~{pool_top} pool this refresh.",
            )
        return "not_in_pool", "Not in the selection pool (missing valuation rank or rubric)."

    return "consensus_fell", "In pool but did not make the cap-constrained shortlist after ranking."


def add_reason(t: str, picked: list[str], shortlist_min: int) -> str:
    if len(picked) <= shortlist_min and t == picked[-1]:
        return "backfill"
    return "consensus_pick"


def quality_movers(
    watch: set[str],
    rub_by: dict[str, dict[str, str]],
    earn: dict[str, dict[str, str]],
    scores: dict[str, float],
    prior_by: dict[str, dict[str, Any]],
    picked_set: set[str],
    rk: dict[str, dict[str, str]] | None,
    ck: dict[str, dict[str, str]] | None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for t in watch:
        cur = ticker_metrics(t, rub_by, earn, scores, rk, ck)
        prev = prior_by.get(t) or {}
        dr = None
        if prev.get("rubric_total") is not None and cur.get("rubric_total") is not None:
            dr = cur["rubric_total"] - int(prev["rubric_total"])
        dy = None
        if prev.get("rev_yoy_pct") is not None and cur.get("rev_yoy_pct") is not None:
            dy = round(float(cur["rev_yoy_pct"]) - float(prev["rev_yoy_pct"]), 1)
        db = None
        if prev.get("borda") is not None and cur.get("borda") is not None:
            db = round(float(cur["borda"]) - float(prev["borda"]), 1)
        dcr = None
        if prev.get("composite_rank") and cur.get("composite_rank"):
            try:
                dcr = int(prev["composite_rank"]) - int(cur["composite_rank"])
            except ValueError:
                pass
        note_parts: list[str] = []
        if dr is not None and dr != 0:
            note_parts.append(f"rubric {'+' if dr > 0 else ''}{dr}")
        if dy is not None and abs(dy) >= 1:
            note_parts.append(f"YoY {'+' if dy > 0 else ''}{dy}%")
        if db is not None and abs(db) >= 1:
            note_parts.append(f"Borda {'+' if db > 0 else ''}{db}")
        if dcr is not None and dcr != 0:
            note_parts.append(f"composite rank {'+' if dcr > 0 else ''}{dcr}")
        if not note_parts:
            if cur.get("composite_rank"):
                note_parts.append(f"composite #{cur['composite_rank']}")
            elif not prev:
                continue
            else:
                continue
        in_out = "on shortlist" if t in picked_set else "off shortlist"
        rows.append(
            {
                "ticker": t,
                "delta_rubric": dr,
                "delta_yoy_pct": dy,
                "delta_borda": db,
                "in_shortlist": t in picked_set,
                "note": " · ".join(note_parts) + f" · {in_out}",
            }
        )
    rows.sort(
        key=lambda x: (
            -(abs(x["delta_rubric"] or 0)),
            -(abs(x["delta_borda"] or 0) if x["delta_borda"] is not None else 0),
        ),
    )
    return rows[:limit]


def build_shortlist_delta(
    *,
    picked: list[str],
    added: list[str],
    dropped: list[str],
    cap_casualties: list[str],
    pool_set: set[str],
    theme_by: dict[str, str],
    rub_by: dict[str, dict[str, str]],
    earn: dict[str, dict[str, str]],
    scores: dict[str, float],
    rk: dict[str, dict[str, str]] | None,
    ck: dict[str, dict[str, str]] | None,
    shortlist_min: int,
    pool_top: int = 60,
    caps: dict[str, int] | None = None,
) -> dict[str, Any]:
    caps_use = caps if caps is not None else {}
    prior = load_prior()
    prior_tickers = set(prior.get("tickers") or [])
    prior_by = prior.get("by_ticker") or {}
    as_of_prior = prior.get("as_of") or ""

    added_rows: list[dict[str, Any]] = []
    for t in added:
        code = add_reason(t, picked, shortlist_min)
        m = ticker_metrics(t, rub_by, earn, scores, rk, ck)
        added_rows.append(
            {
                "ticker": t,
                "reason": code,
                "reason_label": REASON_LABELS.get(code, code),
                "theme": theme_by.get(t, ""),
                **m,
            }
        )

    dropped_rows: list[dict[str, Any]] = []
    for t in dropped:
        code, note = drop_reason(
            t, cap_casualties, pool_set, theme_by, picked, rk, ck, pool_top, caps_use
        )
        prev = prior_by.get(t, {})
        dropped_rows.append(
            {
                "ticker": t,
                "reason": code,
                "reason_label": REASON_LABELS.get(code, code),
                "note": note,
                "prior_rubric_total": prev.get("rubric_total"),
                "prior_borda": prev.get("borda"),
                "prior_composite_rank": prev.get("composite_rank"),
                **ticker_metrics(t, rub_by, earn, scores, rk, ck),
            }
        )

    watch: set[str] = set(picked) | set(dropped) | set(cap_casualties[:8])
    if prior_tickers:
        watch |= prior_tickers

    movers = quality_movers(watch, rub_by, earn, scores, prior_by, set(picked), rk, ck)

    return {
        "prior_as_of": as_of_prior or None,
        "baseline_established": not bool(prior_tickers),
        "selection_mode": "composite_five_signal" if ck else ("valuation_first" if rk else "legacy_borda"),
        "added": added_rows,
        "dropped": dropped_rows,
        "unchanged_count": len(set(picked) & prior_tickers),
        "quality_movers": movers,
    }
