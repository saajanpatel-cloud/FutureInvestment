#!/usr/bin/env python3
"""
Markdown report scaffold for FutureInvestment thematic runs.

Embeds snapshot table if fi_snapshot data exists, then placeholder sections for
latent demand, linkage, sentiment, adversarial pack, watchlist, disqual log, plus
Future Impact trade log, quarterly INVEST/HOLD/REDUCE/SELL, and deployed-vs-cap
placeholders (see research/sources/future-impact/BASELINE.md).
Not investment advice.

Usage:
  python fi_report_scaffold.py --tickers NVDA,AMD --out ../research/watchlists/run-2026-05-05.md
  python fi_report_scaffold.py --file example_tickers.txt --out report.md
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def load_tickers_file(path: Path) -> list[str]:
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line.upper())
    return out


def parse_tickers_arg(s: str) -> list[str]:
    return [t.strip().upper() for t in s.split(",") if t.strip()]


def load_manifest_tickers(path: Path) -> list[str]:
    import csv

    out: list[str] = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            t = (row.get("ticker") or "").strip().upper()
            if t:
                out.append(t)
    return out


def strip_snapshot_embed(md: str) -> str:
    """Remove duplicate title/disclaimer from fi_snapshot.md; keep table onward."""
    lines = md.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("|") and "ticker" in stripped.lower():
            return "\n".join(lines[idx:]).strip() + "\n"
    return md.strip() + "\n"


def run_snapshot_md(tickers: list[str], root: Path) -> str:
    """Invoke fi_snapshot.py in same directory; return markdown body or error note."""
    snap = root / "fi_snapshot.py"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tickf:
        tick_path = Path(tickf.name)
        tickf.write("\n".join(tickers) + "\n")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        cmd = [
            sys.executable,
            str(snap),
            "--file",
            str(tick_path),
            "--md",
            str(tmp_path),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root))
        if r.returncode != 0:
            return (
                "_Snapshot failed (install `scripts/requirements.txt` and retry)._\n\n"
                f"```\n{r.stderr or r.stdout}\n```\n"
            )
        text = tmp_path.read_text(encoding="utf-8")
        return strip_snapshot_embed(text)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            tick_path.unlink(missing_ok=True)
        except Exception:
            pass


def build_report(tickers: list[str], scripts_dir: Path) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snap_md = run_snapshot_md(tickers, scripts_dir)
    tick_lines = "\n".join(f"- {t}" for t in tickers)

    return f"""# FutureInvestment thematic run scaffold

Generated (UTC): `{now}`

**Not personalized investment advice.** Education and research only. Verify all facts in filings and primary sources.

## Universe (this run)

{tick_lines}

## Indicative market snapshot (yfinance)

{snap_md}

---

## Pillar latent-demand memos (Workflow A)

Repeat per pillar (Technology, Healthcare, Energy, Space, Cross-cutting).

### Pillar: _name_

- Problem statement:
- Evidence ladder ([hard] / [soft] with citations):
- Why now / why not yet:
- Inflection triggers (positive and negative):
- Second-best outcomes:
- Unknowns / not found:

---

## Candidate map and linkage (picks-and-shovels)

| Ticker | Pillar | Linkage to latent need | Theme-only / watch / shortlist |
|--------|--------|------------------------|--------------------------------|
|        |        |                        |                                |

---

## Company one-pagers and scoring (Workflow C + rubric)

One section per shortlist ticker: exposure, thesis, falsifiers, metrics snapshot, scoring table.

---

## Optional sentiment (Workflow D)

_Paste structured notes or attach mentions CSV from `fi_mentions.py`._

- Counter-thesis (why sentiment might be wrong):

---

## Adversarial pack (Workflow E) for proposed top picks only

Per ticker: bull thesis, steel-manned bear (4+ bullets, timing attack), pre-mortem, rebuttal map, kill criteria.

---

## Watchlist and disqualification log (Workflow F)

### Ranked watchlist (why flagged)

### Disqualified (why rejected)

### Change log vs prior run

---

## Future Impact sleeve — trade log (one row per position)

Personalised defaults: see `research/sources/future-impact/BASELINE.md` (£7.5k cap, drip, theme weights).

| Field | Notes |
|-------|--------|
| ID | Incremental position # |
| Theme | From baseline table (e.g. AI infrastructure & compute) |
| Ticker & name | |
| Exchange | NYSE / NASDAQ / LSE / etc. |
| Account | ISA / SIPP / GIA |
| Entry date | |
| Avg cost | Incl. FX and fees |
| Size (£ / % of sleeve) | Update each review |
| Thesis (3–5 bullets) | Structural role, drivers, mispricing angle |
| KPIs (2–4) | Theme-specific + growth / margin / balance sheet |
| Valuation at entry | EV/Rev, EV/EBIT, P/E vs peers |
| Risk flags | Regulation, concentration, tech risk |
| Exit / trim criteria | When REDUCE or SELL |

### Example row (template only)

- _Fill after your own analysis—not a recommendation._

---

## Quarterly review — map each position to one action

For each holding: thesis status (Intact / Improving / Deteriorating / Broken); fundamentals vs expectations; valuation vs peers; size vs target weight.

| Action | When |
|--------|------|
| **INVEST** | Thesis intact/improving; fundamentals on track; valuation attractive/reasonable; size below target |
| **HOLD** | Thesis intact; on track; fair value; size OK |
| **REDUCE** | Thesis intact but rich valuation or oversized vs target |
| **SELL** | Thesis broken or fundamentals/valuation no longer justify the name |

After each name, summarize: counts and % of sleeve in each action bucket. Check alignment to **BASELINE.md** theme weights.

---

## Deployed vs cap (optional tracker)

| | £ |
|--|--|
| **Sleeve cap** | 7,500 |
| **Deployed to date** | _sum of fills_ |
| **Remaining to cap** | _cap minus deployed_ |

"""


def main() -> None:
    p = argparse.ArgumentParser(description="Write Markdown report scaffold.")
    p.add_argument("--tickers", help="Comma-separated symbols")
    p.add_argument("--file", help="Newline-separated tickers file")
    p.add_argument(
        "--manifest",
        type=Path,
        help="universe_manifest.csv (same 70-name sleeve list as HTML refresh)",
    )
    p.add_argument(
        "--out",
        required=True,
        help="Output Markdown path (e.g. research/watchlists/run.md)",
    )
    args = p.parse_args()

    scripts_dir = Path(__file__).resolve().parent
    tickers: list[str] = []
    if args.manifest:
        tickers.extend(load_manifest_tickers(Path(args.manifest).resolve()))
    if args.tickers:
        tickers.extend(parse_tickers_arg(args.tickers))
    if args.file:
        tickers.extend(load_tickers_file(Path(args.file)))
    seen: set[str] = set()
    tickers = [t for t in tickers if not (t in seen or seen.add(t))]
    if not tickers:
        print("No tickers: use --manifest, --tickers, and/or --file.", file=sys.stderr)
        sys.exit(2)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_report(tickers, scripts_dir), encoding="utf-8")
    print(str(out.resolve()))


if __name__ == "__main__":
    main()
