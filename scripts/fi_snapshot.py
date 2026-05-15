#!/usr/bin/env python3
"""
Indicative equity snapshot: **yfinance primary**, optional **Stooq** last-close for
missing Yahoo prices, optional **FMP** (`FMP_API_KEY` or `FINANCIAL_MODELING_PREP_KEY`)
for price backfill. Adds `regulatory_lookup_url` for non-US names (best-effort search).

Not investment advice. Data may be delayed, incomplete, or wrong; verify with
primary filings before any decision.

Usage:
  python fi_snapshot.py --tickers NVDA,AMD --csv out.csv
  python fi_snapshot.py --file example_tickers.txt --md ../research/watchlists/snapshot.md
  python fi_snapshot.py --manifest ../research/watchlists/universe_manifest.csv --csv ../research/watchlists/rubric_universe.csv
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

try:
    import pandas as pd
    import yfinance as yf
except ImportError:
    print("Install deps: pip install -r scripts/requirements.txt", file=sys.stderr)
    raise


def _safe_float(x: Any) -> str:
    if x is None:
        return ""
    try:
        if isinstance(x, (int, float)) and pd.notna(x):
            return str(round(float(x), 6))
        return str(x)
    except Exception:
        return ""


def load_manifest_tickers(path: Path) -> list[str]:
    import csv

    out: list[str] = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            t = (row.get("ticker") or "").strip().upper()
            if t:
                out.append(t)
    return out


def load_tickers(args: argparse.Namespace) -> list[str]:
    raw: list[str] = []
    if getattr(args, "manifest", None):
        raw.extend(load_manifest_tickers(Path(args.manifest)))
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            raw.append(line.upper())
    if args.tickers:
        raw.extend(t.strip().upper() for t in args.tickers.split(",") if t.strip())
    seen: set[str] = set()
    out: list[str] = []
    for t in raw:
        if t not in seen:
            seen.add(t)
            out.append(t)
    if not out:
        print("No tickers provided. Use --manifest, --tickers, and/or --file.", file=sys.stderr)
        sys.exit(2)
    return out


def _normalize_cik(raw: Any) -> str:
    """Return zero-padded 10-digit CIK string, or empty if missing."""
    if raw is None or raw == "":
        return ""
    if isinstance(raw, bool):
        return ""
    if isinstance(raw, (int, float)):
        if isinstance(raw, float) and pd.isna(raw):
            return ""
        try:
            n = int(raw)
        except (ValueError, OverflowError):
            return ""
        if n <= 0:
            return ""
        return str(n).zfill(10)
    s = str(raw).strip()
    if not s:
        return ""
    if s.replace(".", "", 1).isdigit() and "." in s:
        try:
            return str(int(float(s))).zfill(10)
        except ValueError:
            return ""
    if s.isdigit():
        return s.zfill(10)
    return s


def _sec_edgar_url(info: dict[str, Any]) -> tuple[str, str]:
    """Return (cik, sec_edgar_url) when CIK present (US filings entry point)."""
    cik = _normalize_cik(info.get("cik"))
    if not cik:
        return "", ""
    url = (
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK="
        + cik
        + "&type=&dateb=&owner=exclude&count=40"
    )
    return cik, url


def _sec_company_search_url(symbol: str) -> str:
    """SEC company search by ticker (fallback when CIK missing)."""
    return "https://www.sec.gov/edgar/searchedgar/companysearch.html?q=" + quote(symbol)


def _to_stooq_daily_symbol(ticker: str) -> str | None:
    """Map Yahoo-style tickers to Stooq daily CSV symbols (best-effort; free Stooq)."""
    u = ticker.strip().upper()
    if not u:
        return None
    if "." not in u:
        return f"{u.lower()}.us"
    base, suf = u.rsplit(".", 1)
    suf_l = suf.lower()
    base_l = base.lower()
    stooq_country = {
        "l": "uk",
        "pa": "fr",
        "de": "de",
        "as": "nl",
        "sw": "ch",
        "mi": "it",
        "mc": "es",
        "br": "be",
        "co": "dk",
        "st": "se",
        "he": "fi",
        "vi": "at",
        "ir": "ie",
        "na": "nl",
        "lu": "lu",
        "ls": "pt",
        "wa": "pl",
    }.get(suf_l)
    if stooq_country:
        return f"{base_l}.{stooq_country}"
    return f"{base_l}.{suf_l}"


def _stooq_last_close(ticker: str) -> str:
    sym = _to_stooq_daily_symbol(ticker)
    if not sym:
        return ""
    url = f"https://stooq.com/q/d/l/?s={quote(sym)}&i=d"
    try:
        req = Request(url, headers={"User-Agent": "FutureInvestment-fi_snapshot/1.0"})
        with urlopen(req, timeout=20) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return ""
    parts = lines[-1].split(",")
    if len(parts) < 5:
        return ""
    try:
        v = float(parts[4])
        if v <= 0:
            return ""
        return _safe_float(v)
    except (TypeError, ValueError):
        return ""


def _fmp_last_price(ticker: str) -> str:
    """Optional FMP quote when FMP_API_KEY is set (free tier subject to limits)."""
    key = (os.environ.get("FMP_API_KEY") or os.environ.get("FINANCIAL_MODELING_PREP_KEY") or "").strip()
    if not key:
        return ""
    u = quote(ticker.upper(), safe="")
    url = f"https://financialmodelingprep.com/api/v3/quote-short/{u}?apikey={quote(key)}"
    try:
        req = Request(url, headers={"User-Agent": "FutureInvestment-fi_snapshot/1.0"})
        with urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    try:
        arr = json.loads(raw)
        if not isinstance(arr, list) or not arr:
            return ""
        px = arr[0].get("price")
        if px is None:
            return ""
        v = float(px)
        if v <= 0:
            return ""
        return _safe_float(v)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ""


def _regulatory_lookup_url(symbol: str, exchange: str, currency: str) -> str:
    """Non-US issuer search helpers (best-effort; human follow-up)."""
    u = symbol.strip().upper()
    ex = (exchange or "").upper()
    if u.endswith(".L") or "LSE" in ex or "LONDON" in ex:
        q = quote(u.replace(".L", "").replace(".", " ") + " site:londonstockexchange.com")
        return "https://www.google.com/search?q=" + q
    if any(u.endswith(s) for s in (".PA", ".DE", ".AS", ".SW", ".MI", ".MC")) or any(
        x in ex for x in ("EURONEXT", "XETRA", "SIX", "MILAN", "MADRID")
    ):
        q = quote(u + " investor relations annual report")
        return "https://www.google.com/search?q=" + q
    return ""


def fetch_row(symbol: str) -> dict[str, str]:
    t = yf.Ticker(symbol)
    info = dict(t.info or {})
    hist = t.history(period="5d")
    last_close = ""
    if not hist.empty and "Close" in hist.columns:
        last_close = _safe_float(float(hist["Close"].iloc[-1]))
    cik, sec_url = _sec_edgar_url(info)
    sec_search = _sec_company_search_url(symbol)
    sources = ["yfinance"]

    if not last_close:
        sq = _stooq_last_close(symbol)
        if sq:
            last_close = sq
            sources.append("stooq(close)")
    if not last_close:
        fmp = _fmp_last_price(symbol)
        if fmp:
            last_close = fmp
            sources.append("fmp(price)")

    reg_url = _regulatory_lookup_url(symbol, str(info.get("exchange") or ""), str(info.get("currency") or ""))

    return {
        "ticker": symbol,
        "short_name": str(info.get("shortName") or info.get("longName") or ""),
        "currency": str(info.get("currency") or ""),
        "exchange": str(info.get("exchange") or ""),
        "quote_type": str(info.get("quoteType") or ""),
        "sector": str(info.get("sector") or ""),
        "industry": str(info.get("industry") or ""),
        "market_cap": _safe_float(info.get("marketCap")),
        "enterprise_value": _safe_float(info.get("enterpriseValue")),
        "trailing_pe": _safe_float(info.get("trailingPE")),
        "forward_pe": _safe_float(info.get("forwardPE")),
        "price_to_book": _safe_float(info.get("priceToBook")),
        "profit_margins": _safe_float(info.get("profitMargins")),
        "revenue_growth": _safe_float(info.get("revenueGrowth")),
        "earnings_growth": _safe_float(info.get("earningsGrowth")),
        "last_close_5d": last_close,
        "fifty_two_week_high": _safe_float(info.get("fiftyTwoWeekHigh")),
        "fifty_two_week_low": _safe_float(info.get("fiftyTwoWeekLow")),
        "cik": cik,
        "sec_edgar_url": sec_url,
        "sec_company_search_url": sec_search,
        "regulatory_lookup_url": reg_url,
        "data_source": "+".join(sources) + " (indicative)",
    }


def rows_to_dataframe(rows: list[dict[str, str]]) -> "pd.DataFrame":
    return pd.DataFrame(rows)


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    rows = []
    for _, row in df.iterrows():
        cells = [str(row[c]).replace("|", "\\|") for c in cols]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, sep, *rows])


def write_md(df: pd.DataFrame, path: Path, generated_at: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# FutureInvestment: indicative snapshot",
        "",
        f"Generated (UTC): `{generated_at}`",
        "",
        "**Not investment advice.** yfinance + optional Stooq/FMP price backfill; verify with filings.",
        "",
        _df_to_markdown_table(df),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="Indicative ticker snapshot via yfinance.")
    p.add_argument(
        "--manifest",
        help="CSV with a ticker column (e.g. universe_manifest.csv); preserves row order",
    )
    p.add_argument("--tickers", help="Comma-separated symbols, e.g. NVDA,AMD")
    p.add_argument("--file", help="Path to newline-separated tickers")
    p.add_argument("--csv", help="Write CSV to this path")
    p.add_argument("--md", help="Write Markdown table to this path")
    args = p.parse_args()

    if not args.csv and not args.md:
        p.error("Provide at least one of --csv or --md")

    tickers = load_tickers(args)
    rows = []
    for sym in tickers:
        try:
            rows.append(fetch_row(sym))
        except Exception as e:
            sq = _stooq_last_close(sym)
            fmp = _fmp_last_price(sym) if not sq else ""
            lc = sq or fmp
            parts = ["error:yfinance"]
            if sq:
                parts.append("stooq(close)")
            elif fmp:
                parts.append("fmp(price)")
            rows.append(
                {
                    "ticker": sym,
                    "short_name": "",
                    "currency": "",
                    "exchange": "",
                    "quote_type": "",
                    "sector": "",
                    "industry": "",
                    "market_cap": "",
                    "enterprise_value": "",
                    "trailing_pe": "",
                    "forward_pe": "",
                    "price_to_book": "",
                    "profit_margins": "",
                    "revenue_growth": "",
                    "earnings_growth": "",
                    "last_close_5d": lc,
                    "fifty_two_week_high": "",
                    "fifty_two_week_low": "",
                    "cik": "",
                    "sec_edgar_url": "",
                    "sec_company_search_url": _sec_company_search_url(sym),
                    "regulatory_lookup_url": _regulatory_lookup_url(sym, "", ""),
                    "data_source": "+".join(parts) + f"; {e}",
                }
            )

    df = rows_to_dataframe(rows)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if args.csv:
        write_csv(df, Path(args.csv))
    if args.md:
        write_md(df, Path(args.md), now)
    print(json.dumps({"ok": True, "tickers": tickers, "rows": len(rows), "utc": now}, indent=2))


if __name__ == "__main__":
    main()
