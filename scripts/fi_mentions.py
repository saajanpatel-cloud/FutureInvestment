#!/usr/bin/env python3
"""
Tier 0 forum sentiment helper: count occurrences of given tickers in pasted text.

Respects word boundaries on alphanumerics; not a sentiment model. Use only on
content you have rights to analyze; comply with platform ToS.

Usage:
  python fi_mentions.py --tickers NVDA,AMD --text-file paste.txt --csv out.csv
  cat paste.txt | python fi_mentions.py --tickers NVDA
  python fi_mentions.py --manifest research/watchlists/universe_manifest.csv --text-file paste.txt --csv research/watchlists/mentions.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path


def load_manifest_tickers(path: Path) -> list[str]:
    out: list[str] = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            t = (row.get("ticker") or "").strip().upper()
            if t:
                out.append(t)
    return out


def load_text(args: argparse.Namespace) -> str:
    if args.text_file:
        return Path(args.text_file).read_text(encoding="utf-8", errors="replace")
    return sys.stdin.read()


def normalize_tickers(raw: str) -> list[str]:
    out = []
    for t in raw.split(","):
        t = t.strip().upper()
        if t:
            out.append(t)
    return out


def count_mentions(body: str, tickers: list[str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    upper = body.upper()
    for sym in tickers:
        esc = re.escape(sym)
        patterns = [
            rf"\b{esc}\b",
            rf"\${esc}\b",
            rf"/{esc}\b",
        ]
        total = 0
        for pattern in patterns:
            total += len(re.findall(pattern, upper))
        counts[sym] = total
    return dict(counts)


def main() -> None:
    p = argparse.ArgumentParser(description="Count ticker mentions in text (Tier 0).")
    p.add_argument(
        "--tickers",
        help="Comma-separated symbols (optional if --manifest is set)",
    )
    p.add_argument(
        "--manifest",
        type=Path,
        help="universe_manifest.csv — same 70-name sleeve list as snapshot refresh",
    )
    p.add_argument("--text-file", help="Forum paste path (default stdin)")
    p.add_argument("--csv", help="Write CSV summary")
    args = p.parse_args()

    tickers: list[str] = []
    if args.manifest:
        tickers.extend(load_manifest_tickers(Path(args.manifest).resolve()))
    if args.tickers:
        tickers.extend(normalize_tickers(args.tickers))
    seen: set[str] = set()
    tickers = [t for t in tickers if not (t in seen or seen.add(t))]
    if not tickers:
        print("No tickers: use --manifest and/or --tickers.", file=sys.stderr)
        sys.exit(2)

    body = load_text(args)
    totals = count_mentions(body, tickers)

    rows = [{"ticker": k, "mentions": v, "chars_in_body": len(body)} for k, v in totals.items()]
    if args.csv:
        outp = Path(args.csv)
        outp.parent.mkdir(parents=True, exist_ok=True)
        with outp.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["ticker", "mentions", "chars_in_body"])
            w.writeheader()
            for r in rows:
                w.writerow(r)

    for r in rows:
        print(f"{r['ticker']}: {r['mentions']} mentions")


if __name__ == "__main__":
    main()
