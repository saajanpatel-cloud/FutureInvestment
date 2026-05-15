#!/usr/bin/env python3
"""Write watchlist-ui/watchlist.example.json from universe_manifest.csv."""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "research" / "watchlists" / "universe_manifest.csv"
DEFAULT_OUT = ROOT / "watchlist-ui" / "watchlist.example.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    items: list[dict[str, str]] = []
    with args.manifest.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            t = (row.get("ticker") or "").strip().upper()
            if not t:
                continue
            slug = (row.get("theme_slug") or "").strip()
            label = (row.get("theme_label") or "").strip()
            link = (row.get("linkage_one_liner") or "").strip()
            items.append(
                {
                    "ticker": t,
                    "pillar": f"{slug} — {label}",
                    "tier": "watch",
                    "why_flagged": link,
                    "notes": "",
                    "sentiment_mentions_csv": "research/watchlists/mentions.csv",
                    "sentiment_note": "",
                }
            )

    doc = {
        "as_of": date.today().isoformat(),
        "disclaimer": (
            "Education and research only. Not personalized investment advice. "
            "Verify all data. pillar encodes sleeve_theme_slug — label from universe_manifest.csv."
        ),
        "items": items,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(args.out.resolve())


if __name__ == "__main__":
    main()
