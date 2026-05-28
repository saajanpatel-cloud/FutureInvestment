#!/usr/bin/env python3
"""Shared helpers for DRAFT Stock-Deep Dive pilot (FI_DRAFT_TICKERS). Not investment advice."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
UI = ROOT / "watchlist-ui"
CORE_TXT = W / "report_core_tickers.txt"
DEFAULT_PILOT = "core"


def load_draft_tickers() -> list[str]:
    raw = os.environ.get("FI_DRAFT_TICKERS", DEFAULT_PILOT).strip()
    if not raw:
        raw = DEFAULT_PILOT
    if raw.lower() in ("core", "decide_union", "union"):
        try:
            from fi_portfolio_tickers import load_decide_union

            u = load_decide_union()
            if u:
                return u
        except ImportError:
            pass
        if CORE_TXT.is_file():
            out: list[str] = []
            for line in CORE_TXT.read_text(encoding="utf-8").splitlines():
                s = line.strip().upper()
                if s and not s.startswith("#"):
                    out.append(s)
            return out
        return [DEFAULT_PILOT]
    return [t.strip().upper() for t in raw.split(",") if t.strip()]


def draft_skipped() -> bool:
    return os.environ.get("FI_SKIP_DRAFT_REPORT", "").strip() == "1"
