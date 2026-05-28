#!/usr/bin/env python3
"""
Conviction tiers 1–4 from composite rank within the core shortlist (quartile split).

Not investment advice.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

TIER_LABELS: dict[int, tuple[str, str]] = {
    1: ("Tier 1 — Highest conviction", "var(--accent)"),
    2: ("Tier 2 — Strong composite", ""),
    3: ("Tier 3 — Core watchlist", ""),
    4: ("Tier 4 — Lower composite (theme / seat)", "var(--warn)"),
}

TIER_SUBLINE = "Grouped by composite-rank quartile within the core shortlist (five-signal blend)."


def load_composite_index(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {
            (r.get("ticker") or "").strip().upper(): r
            for r in csv.DictReader(f)
            if (r.get("ticker") or "").strip()
        }


def conviction_tier_from_position(i: int, n: int) -> int:
    """i = 0-indexed in shortlist sorted best composite first; n = shortlist size."""
    if n <= 0:
        return 2
    if n == 1:
        return 1
    return min(4, 1 + (i * 4) // n)


def assign_conviction_tiers(
    tickers: list[str],
    composite_by: dict[str, dict[str, str]],
) -> dict[str, dict[str, Any]]:
    """
    Return per-ticker dict with conviction_tier (1–4), composite_rank, composite_score.
    Tickers missing composite get tier 4 and empty rank fields.
    """
    out: dict[str, dict[str, Any]] = {}
    ranked: list[tuple[str, int]] = []
    missing: list[str] = []

    for t in tickers:
        u = t.strip().upper()
        row = composite_by.get(u)
        if not row:
            missing.append(u)
            continue
        try:
            cr = int(float(row.get("composite_rank") or 0))
        except (TypeError, ValueError):
            missing.append(u)
            continue
        if cr <= 0:
            missing.append(u)
            continue
        ranked.append((u, cr))

    ranked.sort(key=lambda x: (x[1], x[0]))
    n = len(ranked)

    for i, (t, cr) in enumerate(ranked):
        row = composite_by[t]
        out[t] = {
            "conviction_tier": conviction_tier_from_position(i, n),
            "composite_rank": str(cr),
            "composite_score": (row.get("composite_score") or "").strip(),
        }

    for t in missing:
        out[t] = {
            "conviction_tier": 4,
            "composite_rank": "",
            "composite_score": "",
        }

    return out


def tier_label(n: int) -> str:
    return TIER_LABELS.get(n, TIER_LABELS[2])[0]


def tier_color(n: int) -> str:
    return TIER_LABELS.get(n, TIER_LABELS[2])[1]


def rubric_fallback_tiers(
    tickers: list[str],
    rubric_total_fn,
    rub_by: dict[str, dict[str, str]],
) -> dict[str, dict[str, Any]]:
    """Four bands when composite CSV absent (legacy refresh only)."""
    out: dict[str, dict[str, Any]] = {}

    def band(tot: int | None) -> int:
        if tot is None:
            return 2
        if tot >= 20:
            return 1
        if tot >= 17:
            return 2
        if tot >= 13:
            return 3
        return 4

    for t in tickers:
        u = t.strip().upper()
        tot = rubric_total_fn(rub_by.get(u) or {})
        out[u] = {
            "conviction_tier": band(tot),
            "composite_rank": "",
            "composite_score": "",
        }
    return out
