#!/usr/bin/env python3
"""
Run Workflow E adversarial packs for flagged tickers before shortlist selection.

Writes research/watchlists/adversarial_packs.json (and optional research/memoes/adversarial/*.md).

Env: ANTHROPIC_API_KEY or OPENAI_API_KEY in repo-root .env
     FI_ADVERSARIAL_MAX=N cap per run (default 40)
     FI_SKIP_ADVERSARIAL=1 — refresh_watchlists.sh skips this script

Usage:
  python scripts/fi_adversarial_review.py
  python scripts/fi_adversarial_review.py --dry-run
  python scripts/fi_adversarial_review.py --force-adversarial --tickers IONQ,KLIC

Not investment advice.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from fi_adversarial import (
    PACKS_PATH,
    build_review_batch,
    earnings_ref_mtime,
    heuristic_pack,
    load_packs,
    normalize_pack,
    save_packs,
    write_memo_md,
)

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
UI = ROOT / "watchlist-ui"
RUB = W / "rubric_scores.csv"
MAN = W / "universe_manifest.csv"
ERN = W / "earnings_data.csv"
CORE_JSON = UI / "core-shortlist.json"
CORE_TXT = W / "report_core_tickers.txt"
COMPOSITE_CSV = W / "universe_composite_rank.csv"
RANK_CSV = W / "universe_valuation_rank.csv"
POOL_TOP = 60

SYSTEM = """You are an adversarial equity research verifier (Workflow E).
Output ONLY valid JSON (no markdown fences) matching this schema:
{
  "verdict": "pass|watch|reject|needs_primary_research",
  "shortlist_gate": "pass|watch|reject|reject_seat",
  "linkage_grade": "strong|mixed|weak",
  "quantum_pure": boolean,
  "seat_score": 0-100,
  "bear_bullets": ["at least 4 concrete failure modes; include timing risk; 2 non-obvious"],
  "premortem": "one sentence five-year failure mode",
  "rebuttal": [{"bear": "...", "response": "rebuttal|risk|accepted", "note": "..."}],
  "kill_criteria": ["observable triggers with dates/quarters where possible"],
  "seat_rationale": "one line for shortlist seat decisions"
}
Rules: education/research only; tag uncertain claims [soft]; do not invent filing citations; \
reject_seat for quantum-sleeve names without real quantum-compute revenue linkage."""


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env")


def _load_csv_map(path: Path, key: str) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    out: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            k = (r.get(key) or "").strip().upper()
            if k:
                out[k] = r
    return out


def _prior_core_tickers() -> set[str]:
    out: set[str] = set()
    if CORE_JSON.is_file():
        try:
            doc = json.loads(CORE_JSON.read_text(encoding="utf-8"))
            for it in doc.get("items") or []:
                t = (it.get("ticker") or "").strip().upper()
                if t:
                    out.add(t)
        except json.JSONDecodeError:
            pass
    if CORE_TXT.is_file():
        for line in CORE_TXT.read_text(encoding="utf-8").splitlines():
            s = line.strip().upper()
            if s and not s.startswith("#"):
                out.add(s)
    return out


def _build_pool(
    rub_by: dict[str, dict[str, str]],
    theme_by: dict[str, str],
) -> list[str]:
    from fi_select_shortlist_growth import (
        composite_pool,
        load_composite_ranks,
        load_valuation_ranks,
        valuation_pool,
    )

    ck = load_composite_ranks(COMPOSITE_CSV)
    rk = load_valuation_ranks(RANK_CSV)
    if ck:
        pool, _ = composite_pool(rub_by, theme_by, ck, POOL_TOP)
        return pool
    if rk:
        pool, _ = valuation_pool(rub_by, theme_by, rk, POOL_TOP)
        return pool
    universe: list[tuple[str, int]] = []
    from fi_narrative import rubric_total

    for t, row in rub_by.items():
        if not theme_by.get(t):
            continue
        tot = rubric_total(row)
        if tot is not None:
            universe.append((t, tot))
    universe.sort(key=lambda x: (-x[1], x[0]))
    return [t for t, _ in universe[:POOL_TOP]]


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
            "temperature": 0.25,
            "response_format": {"type": "json_object"},
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode())
    return (data["choices"][0]["message"]["content"] or "").strip()


def _call_anthropic(prompt: str, model: str) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    body = json.dumps(
        {
            "model": model,
            "max_tokens": 2048,
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
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode())
    parts = data.get("content") or []
    return "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()


def _parse_json_response(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return json.loads(t)


def _llm_available() -> tuple[str, str] | None:
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return "anthropic", os.environ.get("FI_ADVERSARIAL_MODEL", "").strip() or "claude-sonnet-4-20250514"
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return "openai", os.environ.get("FI_ADVERSARIAL_MODEL", "").strip() or "gpt-4o-mini"
    return None


def _build_prompt(
    ticker: str,
    rub: dict[str, str],
    man: dict[str, str],
    earn: dict[str, str],
) -> str:
    from fi_narrative import rubric_total

    tot = rubric_total(rub)
    lines = [
        f"Ticker: {ticker}",
        f"Theme: {man.get('theme_label', '')} ({man.get('theme_slug', '')})",
        f"Linkage: {man.get('linkage_one_liner', '')}",
        f"Rubric total: {tot}",
        f"Rubric dims: growth={rub.get('growth')} margins={rub.get('margins')} "
        f"balance_sheet={rub.get('balance_sheet')} durability={rub.get('durability')} "
        f"valuation={rub.get('valuation')} tail_risks={rub.get('tail_risks')}",
        f"Earnings snapshot: rev_yoy={earn.get('rev_yoy_pct')} gross_margin={earn.get('gross_margin_pct')} "
        f"op_margin={earn.get('op_margin_pct')}",
        f"Note: {rub.get('note', '')}",
    ]
    return "\n".join(lines)


def main() -> int:
    _load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="List batch only; no API/heuristic writes")
    ap.add_argument("--force-adversarial", action="store_true")
    ap.add_argument("--universe", action="store_true", help="Review all manifest tickers (slow)")
    ap.add_argument("--tickers", default="", help="Comma-separated; still respects max cap unless force")
    args = ap.parse_args()

    max_n = int(os.environ.get("FI_ADVERSARIAL_MAX", "40") or "40")
    rub_by = _load_csv_map(RUB, "ticker")
    theme_by: dict[str, str] = {}
    man_by: dict[str, dict[str, str]] = {}
    with MAN.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = r["ticker"].strip().upper()
            theme_by[t] = (r.get("theme_slug") or "").strip()
            man_by[t] = r
    earn = _load_csv_map(ERN, "ticker")
    ern_mtime = earnings_ref_mtime(ERN)
    packs = load_packs()
    pool = _build_pool(rub_by, theme_by)
    prior = _prior_core_tickers()

    if args.tickers:
        batch = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        batch = build_review_batch(
            theme_by,
            pool,
            prior,
            packs,
            force=args.force_adversarial,
            universe=args.universe,
            ern_mtime=ern_mtime,
        )

    if len(batch) > max_n and not args.force_adversarial:
        batch = batch[:max_n]
        print(f"WARN: capped adversarial batch to {max_n} (set FI_ADVERSARIAL_MAX or --force-adversarial)", file=sys.stderr)

    print(f"Adversarial batch: {len(batch)} tickers", file=sys.stderr)
    if args.dry_run:
        for t in batch:
            print(t)
        return 0

    llm = _llm_available()
    if not llm:
        print("No LLM API key — using heuristic Workflow E packs", file=sys.stderr)

    provider, model = llm or ("heuristic", "")
    reviewed = 0
    failed: list[str] = []

    for t in batch:
        rub = rub_by.get(t, {})
        man = man_by.get(t, {})
        e = earn.get(t, {})
        try:
            if llm:
                prompt = _build_prompt(t, rub, man, e)
                raw_text = (
                    _call_anthropic(prompt, model)
                    if provider == "anthropic"
                    else _call_openai(prompt, model)
                )
                parsed = _parse_json_response(raw_text)
                pack = normalize_pack(parsed, t)
                pack["source"] = "llm"
                pack["earnings_mtime"] = ern_mtime
            else:
                pack = heuristic_pack(t, rub, man, e, ern_mtime=ern_mtime)
            packs[t] = pack
            write_memo_md(t, pack)
            reviewed += 1
            print(f"  OK {t} gate={pack.get('shortlist_gate')} score={pack.get('seat_score')}", file=sys.stderr)
        except Exception as ex:
            failed.append(t)
            pack = heuristic_pack(t, rub, man, e, ern_mtime=ern_mtime)
            pack["source"] = "heuristic_fallback"
            packs[t] = pack
            write_memo_md(t, pack)
            reviewed += 1
            print(f"  WARN {t}: {ex} — heuristic fallback", file=sys.stderr)

    save_packs(
        packs,
        meta={
            "last_run_reviewed": reviewed,
            "last_run_failed": failed,
            "batch_size": len(batch),
        },
    )
    print(f"Wrote {PACKS_PATH} ({reviewed} reviewed)", file=sys.stderr)
    return 1 if failed and not reviewed else 0


if __name__ == "__main__":
    raise SystemExit(main())
