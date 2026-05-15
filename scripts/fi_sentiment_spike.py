#!/usr/bin/env python3
"""
Spike / compare sentiment providers for FutureInvestment.

Writes research/watchlists/_spike_sentiment_<provider>.json with raw + rubric scores.

Usage:
  python scripts/fi_sentiment_spike.py --provider finnhub --tickers NVDA,ARGX,SAF
  python scripts/fi_sentiment_spike.py --provider all --tickers NVDA,ARGX.BR,SAF.PA
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "research" / "watchlists"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env", override=False)


def _finnhub_symbol(ticker: str) -> str:
    """Map manifest tickers to Finnhub US symbol (strip exchange suffix)."""
    t = ticker.strip().upper()
    for sep in (".", "-"):
        if sep in t:
            t = t.split(sep)[0]
    return t


def _fetch_finnhub(symbol: str, api_key: str) -> dict[str, Any]:
    q = urllib.parse.urlencode({"symbol": symbol, "token": api_key})
    url = f"https://finnhub.io/api/v1/stock/social-sentiment?{q}"
    req = urllib.request.Request(url)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=25) as resp:
        body = json.loads(resp.read().decode())
    latency_ms = round((time.perf_counter() - t0) * 1000)
    return {"latency_ms": latency_ms, "symbol_queried": symbol, "body": body}


def _summarize_finnhub(body: dict[str, Any]) -> dict[str, Any]:
    """Extract mention + score hints from Finnhub social-sentiment payload."""
    out: dict[str, Any] = {"has_data": False}
    reddit = body.get("reddit") or []
    twitter = body.get("twitter") or []
    if not isinstance(reddit, list):
        reddit = [reddit] if reddit else []
    if not isinstance(twitter, list):
        twitter = [twitter] if twitter else []

    def _latest(series: list) -> dict | None:
        if not series:
            return None
        if isinstance(series[0], dict):
            return series[-1]
        return None

    rl, tl = _latest(reddit), _latest(twitter)
    if rl or tl:
        out["has_data"] = True
    if rl:
        out["reddit_mention"] = rl.get("mention")
        out["reddit_positive"] = rl.get("positiveScore")
        out["reddit_negative"] = rl.get("negativeScore")
        out["reddit_score"] = rl.get("score")
    if tl:
        out["twitter_mention"] = tl.get("mention")
        out["twitter_positive"] = tl.get("positiveScore")
        out["twitter_negative"] = tl.get("negativeScore")
        out["twitter_score"] = tl.get("score")
    return out


def _score_rubric(has_data: bool, latency_ms: int, summary: dict[str, Any]) -> dict[str, int]:
    """Simple 1–5 rubric for spike comparison (documented in JSON output)."""
    coverage = 5 if has_data else 1
    latency = 5 if latency_ms < 800 else (4 if latency_ms < 2000 else 3)
    fields = 5 if summary.get("reddit_score") is not None or summary.get("twitter_score") is not None else 2
    return {
        "coverage": coverage,
        "latency": latency,
        "field_richness": fields,
        "free_tier_ok": 4,
        "tos_clarity": 5,
        "eu_uk_usefulness": 3 if has_data else 1,
    }


def run_finnhub(tickers: list[str], api_key: str) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for raw_t in tickers:
        sym = _finnhub_symbol(raw_t)
        row: dict[str, Any] = {"ticker": raw_t, "finnhub_symbol": sym}
        try:
            fetched = _fetch_finnhub(sym, api_key)
            summary = _summarize_finnhub(fetched["body"])
            rubric = _score_rubric(summary["has_data"], fetched["latency_ms"], summary)
            row.update(
                {
                    "ok": True,
                    "latency_ms": fetched["latency_ms"],
                    "summary": summary,
                    "rubric": rubric,
                    "raw": fetched["body"],
                }
            )
        except urllib.error.HTTPError as e:
            row.update({"ok": False, "error": f"HTTP {e.code}", "detail": e.read().decode()[:500]})
        except Exception as e:
            row.update({"ok": False, "error": str(e)})
        results.append(row)
        time.sleep(0.35)
    return {
        "provider": "finnhub",
        "endpoint": "GET /stock/social-sentiment",
        "ts": datetime.now(timezone.utc).isoformat(),
        "tickers": tickers,
        "results": results,
    }


def run_social_stock_sentiment_note(tickers: list[str]) -> dict[str, Any]:
    """Document whether optional PyPI package is importable (no upstream key assumed)."""
    note: dict[str, Any] = {
        "provider": "social-stock-sentiment",
        "ts": datetime.now(timezone.utc).isoformat(),
        "tickers": tickers,
        "importable": False,
        "skipped_reason": None,
    }
    try:
        import social_stock_sentiment  # noqa: F401
        note["importable"] = True
        note["skipped_reason"] = (
            "Package present but spike does not call paid upstream; use Finnhub for v1."
        )
    except ImportError:
        note["skipped_reason"] = "Package not installed; pip install social-stock-sentiment to retry."
    return note


def main() -> None:
    _load_dotenv()
    ap = argparse.ArgumentParser(description="Spike sentiment providers.")
    ap.add_argument("--provider", choices=("finnhub", "compare", "all"), default="finnhub")
    ap.add_argument("--tickers", default="NVDA,ARGX.BR,SAF.PA")
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=WATCH,
        help="Directory for _spike_sentiment_*.json",
    )
    args = ap.parse_args()
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    providers = []
    if args.provider in ("finnhub", "all"):
        providers.append("finnhub")
    if args.provider in ("compare", "all"):
        providers.append("social-stock-sentiment")

    for p in providers:
        if p == "finnhub":
            key = (os.environ.get("FINNHUB_API_KEY") or "").strip()
            if not key:
                payload = {
                    "provider": "finnhub",
                    "error": "FINNHUB_API_KEY not set in .env",
                    "hint": "Register at https://finnhub.io/register — free tier; add FINNHUB_API_KEY= to .env",
                    "tickers": tickers,
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
            else:
                payload = run_finnhub(tickers, key)
            path = out_dir / "_spike_sentiment_finnhub.json"
        else:
            payload = run_social_stock_sentiment_note(tickers)
            path = out_dir / "_spike_sentiment_social_stock_sentiment.json"

        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {path}", file=sys.stderr)
        if payload.get("error"):
            print(f"  ⚠ {payload['error']}", file=sys.stderr)
        for r in payload.get("results") or []:
            if r.get("ok"):
                s = r.get("summary") or {}
                print(
                    f"  {r['ticker']} → {r.get('finnhub_symbol')}: "
                    f"has_data={s.get('has_data')} rubric={r.get('rubric')}",
                    file=sys.stderr,
                )
            else:
                print(f"  {r.get('ticker', '?')}: {r.get('error')}", file=sys.stderr)


if __name__ == "__main__":
    main()
