#!/usr/bin/env python3
"""Pull company profile fields for core shortlist tickers (yfinance). Not investment advice."""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
CORE_TXT = W / "report_core_tickers.txt"
OUT = W / "company_profile.csv"
OVERRIDES = W / "company_overrides.json"


def load_tickers() -> list[str]:
    out: list[str] = []
    for line in CORE_TXT.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.append(s.upper())
    return out


def _normalize_cik(raw) -> str:
    if raw is None or raw == "":
        return ""
    try:
        n = int(float(raw))
        return str(n).zfill(10) if n > 0 else ""
    except (TypeError, ValueError):
        return ""


def sec_urls(symbol: str, info: dict) -> tuple[str, str]:
    cik = _normalize_cik(info.get("cik"))
    if cik:
        url = (
            "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK="
            + cik
            + "&type=&dateb=&owner=exclude&count=40"
        )
        return cik, url
    from urllib.parse import quote

    return "", "https://www.sec.gov/edgar/searchedgar/companysearch.html?q=" + quote(symbol)


def top_holders_text(ticker) -> str:
    try:
        import yfinance as yf
    except ImportError:
        return ""
    t = yf.Ticker(ticker)
    parts: list[str] = []
    try:
        inst = t.institutional_holders
        if inst is not None and not inst.empty and "Holder" in inst.columns:
            for _, row in inst.head(5).iterrows():
                name = str(row.get("Holder", "")).strip()
                pct = row.get("pctHeld") or row.get("% Out")
                if name:
                    if pct is not None and str(pct) != "nan":
                        try:
                            parts.append(f"{name} ({float(pct) * 100:.1f}%)")
                        except (TypeError, ValueError):
                            parts.append(name)
                    else:
                        parts.append(name)
    except Exception:
        pass
    if not parts:
        try:
            maj = t.major_holders
            if maj is not None and not maj.empty:
                for _, row in maj.head(3).iterrows():
                    parts.append(str(row.iloc[0]).strip()[:60])
        except Exception:
            pass
    return " · ".join(parts[:5])


def fetch_row(ticker: str, ov: dict) -> dict[str, str]:
    import yfinance as yf

    t = yf.Ticker(ticker)
    info = dict(t.info or {})
    cik, sec_url = sec_urls(ticker, info)
    summary = (info.get("longBusinessSummary") or "").strip()
    if len(summary) > 800:
        summary = summary[:797] + "…"
    website = (info.get("website") or "").strip()
    if not website.startswith("http"):
        website = ("https://" + website) if website else ""
    holders = top_holders_text(ticker)
    row = {
        "ticker": ticker,
        "long_name": (info.get("longName") or info.get("shortName") or ticker).strip()[:120],
        "sector": str(info.get("sector") or "").strip(),
        "industry": str(info.get("industry") or "").strip(),
        "website": website,
        "business_summary": summary,
        "holders_top": holders,
        "sec_edgar_url": sec_url,
        "sec_cik": cik,
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    o = ov.get(ticker) or {}
    for k in ("key_products", "key_plays", "business_summary", "website", "research_status"):
        if o.get(k):
            row[k] = str(o[k]).strip()
    return row


def main() -> int:
    tickers = load_tickers()
    if not tickers:
        print("No tickers", file=sys.stderr)
        return 2
    ov: dict = {}
    if OVERRIDES.is_file():
        ov = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    rows = [fetch_row(t, ov) for t in tickers]
    fields = [
        "ticker",
        "long_name",
        "sector",
        "industry",
        "website",
        "business_summary",
        "holders_top",
        "sec_edgar_url",
        "sec_cik",
        "as_of",
        "key_products",
        "key_plays",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"Wrote {len(rows)} rows → {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
