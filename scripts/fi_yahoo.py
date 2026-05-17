#!/usr/bin/env python3
"""
Yahoo Finance data access for FutureInvestment (via the ``yfinance`` package).

Yahoo does not issue a separate retail API key for this workflow; ``yfinance``
reads the same public quote/fundamentals endpoints the Yahoo Finance site uses.
Install: ``pip install -r scripts/requirements.txt``.

Not investment advice. Data may be delayed or wrong — verify in filings.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

DEFAULT_PROBE = "SPY"
DEFAULT_SLEEP = 0.12


@dataclass(frozen=True)
class YahooPingResult:
    ok: bool
    version: str
    probe_ticker: str
    last_price: float | None
    currency: str | None = None
    error: str | None = None


def require_yfinance():
    """Import yfinance or exit with install hint."""
    try:
        import yfinance as yf  # noqa: WPS433
    except ImportError as exc:
        raise SystemExit(
            "yfinance not installed. From repo root: "
            "python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt"
        ) from exc
    return yf


def version() -> str:
    yf = require_yfinance()
    return getattr(yf, "__version__", "unknown")


def probe_ticker() -> str:
    return (os.environ.get("YAHOO_PROBE_TICKER") or DEFAULT_PROBE).strip().upper() or DEFAULT_PROBE


def last_price(ticker: str) -> tuple[float | None, str | None]:
    """Return (price, currency) for a single symbol."""
    yf = require_yfinance()
    sym = ticker.strip().upper()
    t = yf.Ticker(sym)
    price: float | None = None
    currency: str | None = None
    try:
        fi = getattr(t, "fast_info", None)
        if fi is not None:
            price = fi.get("lastPrice") or fi.get("last_price") or fi.get("regularMarketPrice")
            currency = fi.get("currency")
    except Exception:
        pass
    if price is None:
        info = t.info or {}
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        currency = currency or info.get("currency")
    if price is not None:
        return float(price), currency
    return None, currency


def ping(ticker: str | None = None) -> YahooPingResult:
    """Connectivity check — fetches one liquid symbol."""
    yf = require_yfinance()
    sym = (ticker or probe_ticker()).strip().upper()
    try:
        price, currency = last_price(sym)
        if price is None:
            return YahooPingResult(
                ok=False,
                version=yf.__version__,
                probe_ticker=sym,
                last_price=None,
                currency=currency,
                error=f"No price returned for {sym}",
            )
        return YahooPingResult(
            ok=True,
            version=yf.__version__,
            probe_ticker=sym,
            last_price=price,
            currency=currency,
        )
    except Exception as exc:
        return YahooPingResult(
            ok=False,
            version=getattr(yf, "__version__", "unknown"),
            probe_ticker=sym,
            last_price=None,
            error=str(exc)[:240],
        )


def ticker(symbol: str):
    """``yfinance.Ticker`` for the normalized symbol."""
    yf = require_yfinance()
    return yf.Ticker(symbol.strip().upper())


def download_history(
    symbols: list[str],
    *,
    period: str = "2y",
    interval: str = "1d",
    auto_adjust: bool = True,
    threads: bool = True,
):
    """Batch OHLCV history (same signature as ``yfinance.download``)."""
    yf = require_yfinance()
    if not symbols:
        raise ValueError("symbols must be non-empty")
    return yf.download(
        " ".join(s.strip().upper() for s in symbols if s.strip()),
        period=period,
        interval=interval,
        auto_adjust=auto_adjust,
        threads=threads,
        progress=False,
        group_by="ticker",
    )


def safe_info_get(info: dict[str, Any] | None, key: str, default: Any = None) -> Any:
    if not info:
        return default
    try:
        val = info.get(key, default)
        return default if val is None else val
    except Exception:
        return default


def throttle(seconds: float = DEFAULT_SLEEP) -> None:
    time.sleep(max(0.0, seconds))
