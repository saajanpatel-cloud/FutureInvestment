#!/usr/bin/env python3
"""
Shared helpers for research/watchlists/universe_manifest.csv.

Columns: ticker, theme_slug, theme_label, linkage_one_liner
theme_slug must match rubric filter values: ai, energy, cyber, auto, health, fintech, quantum.
Not investment advice.
"""
from __future__ import annotations

import csv
from pathlib import Path

REQUIRED_FIELDS = ("ticker", "theme_slug", "theme_label", "linkage_one_liner")


def load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    out: list[dict[str, str]] = []
    for i, row in enumerate(rows):
        for k in REQUIRED_FIELDS:
            if k not in row or row[k] is None:
                raise ValueError(f"{path}: row {i + 2} missing column {k!r}")
        t = row["ticker"].strip().upper()
        if not t:
            raise ValueError(f"{path}: row {i + 2} has empty ticker")
        out.append(
            {
                "ticker": t,
                "theme_slug": row["theme_slug"].strip(),
                "theme_label": row["theme_label"].strip(),
                "linkage_one_liner": row["linkage_one_liner"].strip(),
            }
        )
    return out


def manifest_ticker_order(path: Path) -> list[str]:
    return [r["ticker"] for r in load_manifest(path)]


def manifest_by_ticker(path: Path) -> dict[str, dict[str, str]]:
    return {r["ticker"]: r for r in load_manifest(path)}


def manifest_sort_key(
    row: dict[str, str],
    name_by_ticker: dict[str, str] | None = None,
) -> tuple[str, str, str]:
    """Default table order: company name A–Z, then theme label A–Z, then ticker."""
    t = row["ticker"].strip().upper()
    names = name_by_ticker or {}
    name = (names.get(t) or t).strip().upper()
    theme = (row.get("theme_label") or row.get("theme_slug") or "").strip().upper()
    return (name, theme, t)


def sort_manifest_rows(
    rows: list[dict[str, str]],
    *,
    name_by_ticker: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    return sorted(rows, key=lambda r: manifest_sort_key(r, name_by_ticker))


def fmt_mcap(x: str) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    if v >= 1e12:
        return f"{v / 1e12:.2f}T"
    if v >= 1e9:
        return f"{v / 1e9:.1f}B"
    return f"{v / 1e6:.0f}M"


def fmt_num(x: str | None, nd: int = 2) -> str:
    if x is None or x == "" or str(x).lower() in ("nan", "none"):
        return "—"
    try:
        v = float(x)
        if abs(v) > 1e6:
            return f"{v:.2g}"
        return f"{v:.{nd}f}"
    except (TypeError, ValueError):
        return "—"
