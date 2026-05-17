#!/usr/bin/env python3
"""Sort universe_manifest.csv: company name A–Z, then theme label A–Z, then ticker."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from fi_manifest import sort_manifest_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAN = ROOT / "research" / "watchlists" / "universe_manifest.csv"
DEFAULT_NAMES = ROOT / "research" / "watchlists" / "rubric_universe.csv"


def load_company_names(csv_path: Path) -> dict[str, str]:
    if not csv_path.is_file():
        return {}
    out: dict[str, str] = {}
    with csv_path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            t = (row.get("ticker") or "").strip().upper()
            if t:
                out[t] = (row.get("short_name") or t).strip()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MAN)
    ap.add_argument(
        "--names-csv",
        type=Path,
        default=DEFAULT_NAMES,
        help="short_name source (default rubric_universe.csv)",
    )
    args = ap.parse_args()
    man = args.manifest.resolve()
    if not man.is_file():
        print(f"Missing manifest: {man}", file=sys.stderr)
        return 2

    with man.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    if not fields:
        print("Empty manifest", file=sys.stderr)
        return 2

    names = load_company_names(args.names_csv.resolve())
    sorted_rows = sort_manifest_rows(rows, name_by_ticker=names)
    with man.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted_rows)
    print(f"Sorted {len(sorted_rows)} manifest rows → {man}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
