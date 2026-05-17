#!/usr/bin/env python3
"""
Verify Yahoo Finance connectivity (yfinance) before a refresh.

Usage:
  python scripts/fi_yahoo_health.py
  python scripts/fi_yahoo_health.py --probe AAPL

Exit 0 when a probe price is returned; non-zero on failure.
Writes research/watchlists/yahoo_status.json on success.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fi_yahoo import ping, probe_ticker

ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "research" / "watchlists" / "yahoo_status.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe", default=None, help=f"Symbol to test (default: {probe_ticker()} or YAHOO_PROBE_TICKER)")
    ap.add_argument("--no-write", action="store_true", help="Do not write yahoo_status.json")
    args = ap.parse_args()

    result = ping(args.probe)
    if result.ok:
        cur = f" {result.currency}" if result.currency else ""
        print(
            f"OK: Yahoo Finance (yfinance {result.version}) — "
            f"{result.probe_ticker} {result.last_price:.2f}{cur}"
        )
        if not args.no_write:
            STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
            STATUS_PATH.write_text(
                json.dumps(
                    {
                        "source": "yahoo_finance",
                        "client": "yfinance",
                        "version": result.version,
                        "probe_ticker": result.probe_ticker,
                        "last_price": result.last_price,
                        "currency": result.currency,
                        "checked_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        return 0

    print(f"FAIL: Yahoo Finance — {result.error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
