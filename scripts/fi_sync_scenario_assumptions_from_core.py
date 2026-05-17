#!/usr/bin/env python3
"""
Keep research/watchlists/scenario_assumptions.csv aligned with the Decide
shortlist in research/watchlists/report_core_tickers.txt.

- Output tickers are exactly the core list (same order as the file).
- Rows for tickers that already exist in scenario_assumptions.csv are preserved.
- Missing tickers get a template row (by manifest theme_slug, then metric).

When syncing the core file, rows are seeded from `scenario_assumptions_universe.csv`
if present (same ticker), then overridden by any existing `scenario_assumptions.csv`
row so hand-edited core rows win.

**Universe pass:** `--write-universe` writes `scenario_assumptions_universe.csv` for
manifest ∩ rubric_scores (used before shortlist selection).

Run after fi_select_shortlist_growth.py (typically from refresh_watchlists.sh).
Then re-run fi_scenarios.py, fi_monte_carlo.py, fi_risk_metrics.py, fi_dcf_sensitivity.py
to refresh value outputs for the new set.

Not investment advice.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
CORE = W / "report_core_tickers.txt"
MAN = W / "universe_manifest.csv"
SCEN = W / "scenario_assumptions.csv"
RUB = W / "rubric_scores.csv"
SCEN_UNIVERSE = W / "scenario_assumptions_universe.csv"

FIELDNAMES = [
    "ticker",
    "company",
    "theme",
    "metric",
    "current_metric_note",
    "bull_cagr",
    "base_cagr",
    "bear_cagr",
    "bull_multiple",
    "base_multiple",
    "bear_multiple",
    "bull_prob",
    "base_prob",
    "bear_prob",
]

THEME_BY_SLUG: dict[str, str] = {
    "ai": "AI infrastructure & compute",
    "energy": "Energy transition & grids",
    "cyber": "Cybersecurity & digital trust",
    "auto": "Industrial automation & robotics",
    "health": "Health Tech",
    "quantum": "Quantum / frontier compute",
}

# Pre-profit / P&S style names — conservative template (edit after sync as needed).
PS_TICKERS: frozenset[str] = frozenset(
    {
        "IONQ",
        "QUBT",
        "APLD",
        "QBTS",
    }
)

EPS_TEMPLATE: dict[str, str] = {
    "metric": "eps",
    "current_metric_note": "Fwd EPS (placeholder — replace after filings pass)",
    "bull_cagr": "0.18",
    "base_cagr": "0.12",
    "bear_cagr": "0.04",
    "bull_multiple": "28",
    "base_multiple": "22",
    "bear_multiple": "15",
    "bull_prob": "0.25",
    "base_prob": "0.50",
    "bear_prob": "0.25",
}

PS_TEMPLATE: dict[str, str] = {
    "metric": "ps",
    "current_metric_note": "Rev/Sh (placeholder — pre-profit template)",
    "bull_cagr": "0.45",
    "base_cagr": "0.28",
    "bear_cagr": "0.10",
    "bull_multiple": "30",
    "base_multiple": "20",
    "bear_multiple": "12",
    "bull_prob": "0.20",
    "base_prob": "0.45",
    "bear_prob": "0.35",
}


def load_core(path: Path) -> list[str]:
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s.upper())
    return out


def load_manifest(path: Path) -> dict[str, dict[str, str]]:
    by_t: dict[str, dict[str, str]] = {}
    if not path.is_file():
        return by_t
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = (r.get("ticker") or "").strip().upper()
            if t:
                by_t[t] = r
    return by_t


def load_existing_scenarios(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {(row["ticker"] or "").strip().upper(): row for row in csv.DictReader(f)}


def build_row(
    ticker: str,
    man: dict[str, dict[str, str]],
    existing: dict[str, dict[str, str]],
) -> dict[str, str]:
    t = ticker.upper()
    if t in existing:
        row = dict(existing[t])
        for k in FIELDNAMES:
            row.setdefault(k, "")
        return {k: (row.get(k) or "").strip() for k in FIELDNAMES}

    mrow = man.get(t, {})
    slug = (mrow.get("theme_slug") or "").strip().lower()
    theme = THEME_BY_SLUG.get(slug, THEME_BY_SLUG["ai"])
    company = t
    tmpl = PS_TEMPLATE.copy() if t in PS_TICKERS else EPS_TEMPLATE.copy()
    out = {
        "ticker": t,
        "company": company,
        "theme": theme,
        **tmpl,
    }
    return {k: out.get(k, "") for k in FIELDNAMES}


def load_rubric_tickers(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    with path.open(encoding="utf-8", newline="") as f:
        return {(r.get("ticker") or "").strip().upper() for r in csv.DictReader(f) if (r.get("ticker") or "").strip()}


def write_universe_assumptions(manifest: Path, rub_path: Path, out_path: Path, dry_run: bool) -> int:
    """Template scenario rows for manifest ∩ rubric (valuation-first pipeline)."""
    man = load_manifest(manifest)
    rub_t = load_rubric_tickers(rub_path)
    tickers = sorted(
        [
            t
            for t in man
            if t in rub_t and (man[t].get("model_tier") or "full").strip().lower() == "full"
        ]
    )
    if not tickers:
        print("No tickers in manifest ∩ rubric_scores.csv", file=sys.stderr)
        return 2
    existing = load_existing_scenarios(out_path)
    rows = [build_row(t, man, existing) for t in tickers]
    if dry_run:
        print(f"[dry-run] would write {len(rows)} rows → {out_path}", file=sys.stderr)
        return 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {out_path} ({len(rows)} universe scenario rows)", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--core", type=Path, default=CORE)
    ap.add_argument("--manifest", type=Path, default=MAN)
    ap.add_argument("--scenarios", type=Path, default=SCEN)
    ap.add_argument(
        "--write-universe",
        action="store_true",
        help=f"Write {SCEN_UNIVERSE.name} for manifest ∩ rubric_scores (valuation pass); does not read --core.",
    )
    ap.add_argument("--universe-out", type=Path, default=SCEN_UNIVERSE, help="Output path for --write-universe")
    ap.add_argument("--rubric", type=Path, default=RUB, help="Rubric CSV for --write-universe ticker filter")
    ap.add_argument("--dry-run", action="store_true", help="Print diff only; do not write CSV")
    args = ap.parse_args()

    if args.write_universe:
        return write_universe_assumptions(args.manifest, args.rubric, args.universe_out, args.dry_run)

    if not args.core.is_file():
        print(f"Missing {args.core}", file=sys.stderr)
        return 2

    core = load_core(args.core)
    if not core:
        print("No tickers in core file", file=sys.stderr)
        return 2

    man = load_manifest(args.manifest)
    univ_path = SCEN_UNIVERSE
    univ = load_existing_scenarios(univ_path) if univ_path.is_file() else {}
    existing = load_existing_scenarios(args.scenarios)
    merged: dict[str, dict[str, str]] = {**univ, **existing}
    rows = [build_row(t, man, merged) for t in core]

    old_keys = list(existing.keys())
    new_keys = [r["ticker"] for r in rows]
    added = [t for t in new_keys if t not in existing]
    removed = [t for t in old_keys if t not in set(new_keys)]

    if added:
        print(f"+ {len(added)} scenario row(s) added: {', '.join(added[:20])}{'…' if len(added) > 20 else ''}", file=sys.stderr)
    if removed:
        print(f"− {len(removed)} scenario row(s) removed: {', '.join(removed)}", file=sys.stderr)
    if not added and not removed:
        print("scenario_assumptions.csv already matches core tickers (order may still refresh)", file=sys.stderr)

    if args.dry_run:
        return 0

    args.scenarios.parent.mkdir(parents=True, exist_ok=True)
    with args.scenarios.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {args.scenarios} ({len(rows)} rows)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
