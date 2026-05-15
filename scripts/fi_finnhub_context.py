#!/usr/bin/env python3
"""
Finnhub market context for FutureInvestment core tickers (free-tier endpoints).

Pulls analyst recommendation trend, insider MSPR, 7-day company-news count, and
recent/next earnings hint. Replaces deprecated social-sentiment pipeline.

Not investment advice. Secondary to rubric and valuation; not retail social tone.

Usage:
  python scripts/fi_finnhub_context.py --tickers-file research/watchlists/report_core_tickers.txt \\
    --csv research/watchlists/finnhub_context.csv \\
    --html research/watchlists/finnhub_context_fragment.html
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

NEWS_LOOKBACK_DAYS = 7
INSIDER_LOOKBACK_MONTHS = 18
SLEEP_BETWEEN_TICKERS = 0.35

# Display order: tables appear in this sequence (non-empty groups only).
_ANALYST_SKEW_GROUP_ORDER = ("buy-heavy", "mixed", "sell-heavy", "no data")

_ANALYST_SKEW_GROUP_TITLE = {
    "buy-heavy": "Buy-heavy (analysts)",
    "mixed": "Mixed (analysts)",
    "sell-heavy": "Sell-heavy (analysts)",
    "no data": "No analyst data or incomplete",
}

_STYLE_BLOCK = """\
<style>
.context-skew-wrap { margin: 0.75rem 0; }
.context-skew-table {
  width: 100%;
  max-width: 56rem;
  border-collapse: collapse;
  font-size: 0.82rem;
  margin: 0.35rem 0 1rem;
}
.context-skew-table th,
.context-skew-table td {
  border: 1px solid var(--line, #243044);
  padding: 0.35rem 0.5rem;
  text-align: left;
  vertical-align: top;
}
.context-skew-table thead th {
  background: var(--panel, #141a24);
  font-weight: 600;
}
.context-skew-table tbody tr:nth-child(even) {
  background: color-mix(in srgb, var(--panel, #141a24) 55%, transparent);
}
.context-skew-group-title {
  font-size: 0.95rem;
  font-weight: 600;
  margin: 0.85rem 0 0.25rem;
}
.context-skew-group-title:first-child { margin-top: 0.25rem; }
</style>"""


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env", override=False)


def _api_key() -> str:
    return (os.environ.get("FINNHUB_API_KEY") or "").strip()


def _finnhub_symbol(ticker: str) -> str:
    t = ticker.strip().upper()
    for sep in (".", "-"):
        if sep in t:
            t = t.split(sep)[0]
    return t


def _normalize_tickers(raw: str) -> list[str]:
    return [t.strip().upper() for t in raw.split(",") if t.strip()]


def _tickers_from_file(path: Path) -> list[str]:
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.append(s.upper())
    return out


def _dedup(tickers: list[str]) -> list[str]:
    seen: set[str] = set()
    return [t for t in tickers if not (t in seen or seen.add(t))]  # type: ignore[func-returns-value]


def _fetch(path: str, params: dict[str, str]) -> Any | None:
    params = {**params, "token": _api_key()}
    q = urllib.parse.urlencode(params)
    url = f"https://finnhub.io/api/v1/{path}?{q}"
    try:
        with urllib.request.urlopen(url, timeout=25) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  ⚠ Finnhub {path} HTTP {e.code}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ⚠ Finnhub {path}: {e}", file=sys.stderr)
        return None


def _analyst_skew(symbol: str) -> str:
    data = _fetch("stock/recommendation", {"symbol": symbol})
    if not isinstance(data, list) or not data:
        return "no data"
    latest = data[-1]
    if not isinstance(latest, dict):
        return "no data"
    bull = int(latest.get("strongBuy") or 0) + int(latest.get("buy") or 0)
    bear = int(latest.get("sell") or 0) + int(latest.get("strongSell") or 0)
    hold = int(latest.get("hold") or 0)
    total = bull + hold + bear
    if total == 0:
        return "no data"
    bull_pct = bull / total * 100
    if bull_pct >= 65:
        return "buy-heavy"
    if bull_pct <= 35:
        return "sell-heavy"
    return "mixed"


def _insider_mspr(symbol: str) -> str:
    end = date.today()
    start = end - timedelta(days=INSIDER_LOOKBACK_MONTHS * 31)
    data = _fetch(
        "stock/insider-sentiment",
        {"symbol": symbol, "from": start.isoformat(), "to": end.isoformat()},
    )
    if not isinstance(data, dict):
        return "no data"
    rows = data.get("data") or []
    if not rows:
        return "no data"
    last = rows[-1]
    if not isinstance(last, dict):
        return "no data"
    mspr = last.get("mspr")
    if mspr is None:
        return "no data"
    try:
        v = float(mspr)
    except (TypeError, ValueError):
        return "no data"
    if v >= 25:
        return f"bullish MSPR {v:.0f}"
    if v <= -25:
        return f"bearish MSPR {v:.0f}"
    return f"neutral MSPR {v:.0f}"


def _news_count_7d(symbol: str) -> int | str:
    end = date.today()
    start = end - timedelta(days=NEWS_LOOKBACK_DAYS)
    data = _fetch(
        "company-news",
        {"symbol": symbol, "from": start.isoformat(), "to": end.isoformat()},
    )
    if not isinstance(data, list):
        return "N/A"
    return len(data)


def _next_earnings(symbol: str) -> str:
    data = _fetch("stock/earnings", {"symbol": symbol})
    if not isinstance(data, list) or not data:
        return "no data"
    today = date.today()
    future: list[date] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        period = (row.get("period") or "").strip()[:10]
        if not period:
            continue
        try:
            d = date.fromisoformat(period)
        except ValueError:
            continue
        if d >= today:
            future.append(d)
    if future:
        return min(future).isoformat()
    last = data[0]
    if isinstance(last, dict) and last.get("period"):
        return f"last {str(last.get('period'))[:10]}"
    return "no data"


def _build_context_line(
    analyst: str, insider: str, news: int | str, earnings: str, scan_day: str
) -> str:
    from fi_narrative import format_market_context

    news_n = news if isinstance(news, int) else None
    missing = (
        analyst == "no data"
        and insider == "no data"
        and news_n is None
        and earnings == "no data"
    )
    return format_market_context(
        analyst,
        insider,
        news_n,
        earnings,
        missing_symbol=missing,
    )


def _context_for_ticker(ticker: str) -> dict[str, Any]:
    sym = _finnhub_symbol(ticker)
    analyst = _analyst_skew(sym)
    insider = _insider_mspr(sym)
    news = _news_count_7d(sym)
    earnings = _next_earnings(sym)
    scan_day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    line = _build_context_line(analyst, insider, news, earnings, scan_day)
    return {
        "ticker": ticker,
        "finnhub_symbol": sym,
        "analyst_skew": analyst,
        "insider_mspr": insider,
        "news_7d": news,
        "next_earnings": earnings,
        "context_line": line,
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


_CSV_FIELDS = [
    "ticker",
    "finnhub_symbol",
    "analyst_skew",
    "insider_mspr",
    "news_7d",
    "next_earnings",
    "context_line",
    "last_updated",
]


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"  ✓ Wrote {path} ({len(rows)} rows)", file=sys.stderr)


def _news_display(news: int | str) -> str:
    if isinstance(news, int):
        return str(news)
    return str(news)


def _skew_bucket(row: dict[str, Any]) -> str:
    """Map analyst_skew to a display bucket (buy-heavy, mixed, sell-heavy, no data)."""
    s = str(row.get("analyst_skew") or "").strip().lower()
    if s in ("buy-heavy", "buy heavy"):
        return "buy-heavy"
    if s in ("sell-heavy", "sell heavy"):
        return "sell-heavy"
    if s == "mixed":
        return "mixed"
    return "no data"


def _partition_by_skew(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {k: [] for k in _ANALYST_SKEW_GROUP_ORDER}
    for r in rows:
        out[_skew_bucket(r)].append(r)
    return out


def _table_row_html(r: dict[str, Any]) -> str:
    t = html.escape(str(r.get("ticker") or ""))
    a = html.escape(str(r.get("analyst_skew") or ""))
    ins = html.escape(str(r.get("insider_mspr") or ""))
    news_raw = r.get("news_7d")
    news_s = _news_display(news_raw) if news_raw not in (None, "") else "N/A"
    n = html.escape(news_s)
    earn = html.escape(str(r.get("next_earnings") or ""))
    return (
        f"        <tr><td><strong>{t}</strong></td><td>{a}</td><td>{ins}</td>"
        f"<td>{n}</td><td>{earn}</td></tr>"
    )


def _build_skew_group_table(group_key: str, group_rows: list[dict[str, Any]]) -> str:
    title = _ANALYST_SKEW_GROUP_TITLE.get(group_key, group_key)
    head = (
        "        <thead>\n"
        "          <tr>\n"
        '            <th scope="col">Ticker</th>\n'
        '            <th scope="col">Analysts</th>\n'
        '            <th scope="col">Insiders</th>\n'
        '            <th scope="col">News (7d)</th>\n'
        '            <th scope="col">Earnings</th>\n'
        "          </tr>\n"
        "        </thead>\n"
    )
    body_rows = "\n".join(_table_row_html(r) for r in group_rows)
    return (
        f'    <h3 class="context-skew-group-title">{html.escape(title)}</h3>\n'
        f'    <table class="context-skew-table">\n{head}'
        f"        <tbody>\n{body_rows}\n        </tbody>\n    </table>"
    )


def _build_html(rows: list[dict[str, Any]], ts: str, has_key: bool) -> str:
    if not has_key:
        return (
            '<section id="market-context">\n'
            "  <h2>Market context</h2>\n"
            '  <p class="muted">Set <code>FINNHUB_API_KEY</code> in <code>.env</code> '
            "and run <code>python scripts/fi_finnhub_context.py</code>.</p>\n"
            "</section>\n"
        )
    parts = _partition_by_skew(rows)
    group_blocks: list[str] = []
    for key in _ANALYST_SKEW_GROUP_ORDER:
        grp = parts.get(key) or []
        if not grp:
            continue
        group_blocks.append(_build_skew_group_table(key, grp))

    intro_skew = (
        "Rows are grouped by <strong>analyst recommendation skew</strong> (buy-heavy, mixed, sell-heavy). "
        "Names with missing or incomplete recommendation data appear under "
        "<strong>No analyst data or incomplete</strong>."
    )

    section_inner = (
        "\n".join(
            [
                _STYLE_BLOCK,
                '<section id="market-context">',
                "  <h2>Market context (Finnhub)</h2>",
                '  <p class="section-purpose"><strong>What is this?</strong> Free-tier Finnhub '
                "signals: analyst recommendation mix, insider MSPR, recent headline count, "
                "and earnings timing. Not retail social sentiment; not a trading signal.</p>",
                f"  <p class=\"section-purpose\">{intro_skew}</p>",
                f'  <p class="muted">Generated {ts}. Not investment advice.</p>',
                '  <div class="context-skew-wrap">',
            ]
            + [f"    {block}" for block in group_blocks]
            + ["  </div>", "</section>", ""]
        )
    )
    return section_inner


def main() -> None:
    _load_dotenv()
    ap = argparse.ArgumentParser(description="Finnhub market context for tickers.")
    ap.add_argument("--tickers", help="Comma-separated symbols")
    ap.add_argument("--tickers-file", type=Path, help="One ticker per line")
    ap.add_argument("--csv", help="Output CSV path")
    ap.add_argument("--html", help="Output HTML fragment path")
    args = ap.parse_args()

    if not args.csv and not args.html:
        ap.error("Provide at least one of --csv or --html")

    tickers: list[str] = []
    if args.tickers_file:
        tickers.extend(_tickers_from_file(args.tickers_file.resolve()))
    if args.tickers:
        tickers.extend(_normalize_tickers(args.tickers))
    tickers = _dedup(tickers)
    if not tickers:
        print("No tickers: use --tickers-file and/or --tickers.", file=sys.stderr)
        sys.exit(2)

    has_key = bool(_api_key())
    if not has_key:
        print(
            "  ℹ FINNHUB_API_KEY not set in `.env` — register at https://finnhub.io/register",
            file=sys.stderr,
        )

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows: list[dict[str, Any]] = []
    for ticker in tickers:
        print(f"  Fetching {ticker}…", file=sys.stderr)
        if has_key:
            rows.append(_context_for_ticker(ticker))
            time.sleep(SLEEP_BETWEEN_TICKERS)
        else:
            rows.append({
                "ticker": ticker,
                "finnhub_symbol": _finnhub_symbol(ticker),
                "analyst_skew": "N/A",
                "insider_mspr": "N/A",
                "news_7d": "N/A",
                "next_earnings": "N/A",
                "context_line": "FINNHUB_API_KEY not configured.",
                "last_updated": ts,
            })

    if args.csv:
        _write_csv(rows, Path(args.csv))
    if args.html:
        html_out = _build_html(rows, ts, has_key)
        outp = Path(args.html)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(html_out, encoding="utf-8")
        print(f"  ✓ Wrote {outp}", file=sys.stderr)

    for r in rows:
        print(f"  {r['ticker']}: {r.get('context_line', '')}", file=sys.stderr)


if __name__ == "__main__":
    main()
