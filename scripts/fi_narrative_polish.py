#!/usr/bin/env python3
"""
Optional LLM polish for narrative fields on core-shortlist.json (and optionally rubric notes).

Not run by refresh_watchlists.sh. Next full refresh overwrites polished text unless you
copy wording into research/watchlists/qualitative_overrides.json (future).

Env: ANTHROPIC_API_KEY or OPENAI_API_KEY in repo-root .env

Usage:
  python scripts/fi_narrative_polish.py --dry-run --tickers NVDA
  python scripts/fi_narrative_polish.py --write --fields why_this_name,qual_bull

Not investment advice.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_JSON = ROOT / "watchlist-ui" / "core-shortlist.json"
RUB = ROOT / "research" / "watchlists" / "rubric_scores.csv"

DEFAULT_FIELDS = [
    "why_this_name",
    "market_context",
    "key_risk_kill",
    "research_thesis",
    "research_premortem",
    "qual_bull",
    "qual_bear",
    "qual_watch",
]

SYSTEM = (
    "You polish equity research table cells. Keep middle-dot bullets (·) between clauses. "
    "Use simple English. Do not add buy/sell advice. Do not invent numbers or facts not in the input. "
    "Stay under the max character limit given."
)


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env")


def _call_openai(prompt: str, model: str) -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
    return (data["choices"][0]["message"]["content"] or "").strip()


def _call_anthropic(prompt: str, model: str) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    body = json.dumps(
        {
            "model": model,
            "max_tokens": 1024,
            "system": SYSTEM,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
    parts = data.get("content") or []
    return "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()


def polish_text(text: str, field: str, max_len: int, provider: str, model: str) -> str:
    prompt = (
        f"Field: {field}\nMax length: {max_len} characters\n"
        f"Input:\n{text}\n\nReturn only the polished cell text."
    )
    if provider == "anthropic":
        out = _call_anthropic(prompt, model)
    else:
        out = _call_openai(prompt, model)
    if len(out) > max_len:
        out = out[: max_len - 1] + "…"
    return out


def main() -> int:
    _load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--tickers", default="", help="Comma-separated; default all core items")
    ap.add_argument("--fields", default=",".join(DEFAULT_FIELDS))
    ap.add_argument("--rubric-csv", action="store_true", help="Also polish rubric_scores.csv note column")
    ap.add_argument("--provider", choices=("openai", "anthropic"), default="openai")
    ap.add_argument("--model", default="")
    args = ap.parse_args()
    if not args.dry_run and not args.write:
        print("Specify --dry-run or --write", file=sys.stderr)
        return 2

    model = args.model or (
        "claude-sonnet-4-20250514" if args.provider == "anthropic" else "gpt-4o-mini"
    )
    fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    tickers_filter = {t.strip().upper() for t in args.tickers.split(",") if t.strip()}

    doc = json.loads(CORE_JSON.read_text(encoding="utf-8"))
    items = doc.get("items") or []
    limits = {
        "why_this_name": 520,
        "market_context": 420,
        "key_risk_kill": 420,
        "research_thesis": 520,
        "research_premortem": 420,
        "research_kill": 420,
        "qual_bull": 220,
        "qual_bear": 220,
        "qual_watch": 220,
    }

    for it in items:
        t = (it.get("ticker") or "").strip().upper()
        if tickers_filter and t not in tickers_filter:
            continue
        for field in fields:
            old = (it.get(field) or "").strip()
            if not old:
                continue
            new = polish_text(old, field, limits.get(field, 400), args.provider, model)
            print(f"{t} {field}:\n  was: {old[:120]}…\n  now: {new[:120]}…\n")
            if args.write:
                it[field] = new
                if field == "key_risk_kill":
                    it["research_kill"] = new

    if args.write:
        CORE_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {CORE_JSON}", file=sys.stderr)

    if args.rubric_csv and RUB.is_file():
        rows = list(csv.DictReader(RUB.open(encoding="utf-8", newline="")))
        fn = list(rows[0].keys()) if rows else []
        for row in rows:
            t = row["ticker"].strip().upper()
            if tickers_filter and t not in tickers_filter:
                continue
            old = (row.get("note") or "").strip()
            if not old:
                continue
            new = polish_text(old, "rubric_note", 220, args.provider, model)
            print(f"{t} rubric note polished")
            if args.write:
                row["note"] = new
        if args.write and fn:
            with RUB.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fn, lineterminator="\n")
                w.writeheader()
                w.writerows(rows)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
