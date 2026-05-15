#!/usr/bin/env python3
"""
Blend five universe signals into a composite rank for shortlist pool selection.

Inputs (universe pass):
  universe_valuation_rank.csv, rubric_scores.csv, risk_metrics_universe.csv,
  monte_carlo_results_universe.csv, dcf_sensitivity_universe.csv
  shortlist_weights.json

Output:
  universe_composite_rank.csv

Not investment advice.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
DEFAULT_WEIGHTS = W / "shortlist_weights.json"
VAL_RANK = W / "universe_valuation_rank.csv"
RUB = W / "rubric_scores.csv"
RISK = W / "risk_metrics_universe.csv"
MC = W / "monte_carlo_results_universe.csv"
DCF = W / "dcf_sensitivity_universe.csv"
OUT = W / "universe_composite_rank.csv"

WACC_STEPS = [0.08, 0.09, 0.10, 0.11, 0.12]


def safe_float(x: str | float | None) -> float | None:
    if x is None or x == "":
        return None
    try:
        v = float(x)
        if math.isnan(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def load_csv(path: Path, key: str = "ticker") -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {(r.get(key) or "").strip().upper(): r for r in csv.DictReader(f) if (r.get(key) or "").strip()}


def rubric_total(row: dict[str, str]) -> int | None:
    try:
        g = int(row["growth"])
        m = int(row["margins"])
        bs = int(row["balance_sheet"])
        d = int(row["durability"])
        tail = int(row["tail_risks"])
        v = int(row["valuation"])
        return g + m + bs + d + v - tail
    except (KeyError, ValueError):
        return None


def percentile_map(raw: dict[str, float]) -> dict[str, float]:
    """Map raw scores to 0–100 percentile (higher raw = higher percentile)."""
    if not raw:
        return {}
    items = sorted(raw.items(), key=lambda x: x[1])
    n = len(items)
    if n == 1:
        return {items[0][0]: 50.0}
    out: dict[str, float] = {}
    for i, (t, _) in enumerate(items):
        out[t] = round(100.0 * i / (n - 1), 2)
    return out


def dcf_center_upside(dcf_rows: list[dict[str, str]]) -> float | None:
    """Upside % at center of 5×5 grid (middle growth × 10% WACC)."""
    if not dcf_rows:
        return None
    by_key: dict[tuple[float, float], float] = {}
    upsides: list[float] = []
    for r in dcf_rows:
        g = safe_float(r.get("growth_rate"))
        w = safe_float(r.get("wacc"))
        u = safe_float(r.get("upside_pct"))
        if g is None or w is None or u is None:
            continue
        by_key[(round(g, 8), round(w, 8))] = u
        upsides.append(u)
    mid_g = sorted({round(safe_float(r.get("growth_rate")) or 0, 8) for r in dcf_rows})[2] if len(dcf_rows) >= 5 else None
    mid_w = 0.10
    if mid_g is not None and (mid_g, mid_w) in by_key:
        return by_key[(mid_g, mid_w)]
    if upsides:
        upsides.sort()
        return upsides[len(upsides) // 2]
    return None


def load_weights(path: Path) -> dict[str, float]:
    if not path.is_file():
        return {"scenario": 0.30, "rubric": 0.25, "risk": 0.20, "monte_carlo": 0.15, "dcf": 0.10}
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {
        "scenario": float(doc.get("scenario", 0.30)),
        "rubric": float(doc.get("rubric", 0.25)),
        "risk": float(doc.get("risk", 0.20)),
        "monte_carlo": float(doc.get("monte_carlo", 0.15)),
        "dcf": float(doc.get("dcf", 0.10)),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    weights = load_weights(args.weights)
    wsum = sum(weights.values())
    if wsum <= 0:
        print("Weights must sum > 0", file=sys.stderr)
        return 2
    weights = {k: v / wsum for k, v in weights.items()}

    val = load_csv(VAL_RANK)
    rub = load_csv(RUB)
    risk = load_csv(RISK)
    mc = load_csv(MC)

    dcf_by: dict[str, list[dict[str, str]]] = defaultdict(list)
    if DCF.is_file():
        with DCF.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                t = (r.get("ticker") or "").strip().upper()
                if t:
                    dcf_by[t].append(r)

    # Eligible universe: rubric with total (manifest filter via rubric file)
    eligible: list[str] = []
    for t, row in rub.items():
        if rubric_total(row) is not None:
            eligible.append(t)

    if len(eligible) < 25:
        print(f"Too few rubric tickers ({len(eligible)})", file=sys.stderr)
        return 2

    scen_raw: dict[str, float] = {}
    rub_raw: dict[str, float] = {}
    risk_raw: dict[str, float] = {}
    mc_raw: dict[str, float] = {}
    dcf_raw: dict[str, float] = {}
    missing: dict[str, list[str]] = defaultdict(list)

    for t in eligible:
        if t in val:
            scen_raw[t] = safe_float(val[t].get("valuation_score")) or 0.0
        else:
            missing[t].append("scenario")

        rt = rubric_total(rub[t])
        if rt is not None:
            rub_raw[t] = float(rt)
        else:
            missing[t].append("rubric")

        rr = risk.get(t)
        if rr:
            beta = safe_float(rr.get("beta")) or 1.0
            sharpe = safe_float(rr.get("sharpe")) or 0.0
            mdd = safe_float(rr.get("max_drawdown")) or -1.0
            risk_raw[t] = sharpe + (-mdd) - max(0.0, beta - 1.5) * 0.5
        else:
            missing[t].append("risk")

        mr = mc.get(t)
        if mr:
            p50 = safe_float(mr.get("prob_50pct_up")) or 0.0
            p30 = safe_float(mr.get("prob_30pct_down")) or 0.0
            mc_raw[t] = p50 - 0.5 * p30
        else:
            missing[t].append("monte_carlo")

        du = dcf_center_upside(dcf_by.get(t, []))
        if du is not None:
            dcf_raw[t] = du
        else:
            missing[t].append("dcf")

    # Require all five signals for composite (exclude incomplete)
    complete = [
        t
        for t in eligible
        if t in scen_raw and t in rub_raw and t in risk_raw and t in mc_raw and t in dcf_raw
    ]
    excluded = len(eligible) - len(complete)
    if excluded:
        print(f"WARN: {excluded} tickers excluded (missing ≥1 universe signal)", file=sys.stderr)

    pct_scen = percentile_map({t: scen_raw[t] for t in complete})
    pct_rub = percentile_map({t: rub_raw[t] for t in complete})
    pct_risk = percentile_map({t: risk_raw[t] for t in complete})
    pct_mc = percentile_map({t: mc_raw[t] for t in complete})
    pct_dcf = percentile_map({t: dcf_raw[t] for t in complete})

    rows: list[dict[str, str]] = []
    for t in complete:
        comp = (
            weights["scenario"] * pct_scen[t]
            + weights["rubric"] * pct_rub[t]
            + weights["risk"] * pct_risk[t]
            + weights["monte_carlo"] * pct_mc[t]
            + weights["dcf"] * pct_dcf[t]
        )
        tier = val[t].get("tier", "") if t in val else ""
        rows.append(
            {
                "ticker": t,
                "composite_score": f"{comp:.4f}",
                "pct_scenario": f"{pct_scen[t]:.2f}",
                "pct_rubric": f"{pct_rub[t]:.2f}",
                "pct_risk": f"{pct_risk[t]:.2f}",
                "pct_mc": f"{pct_mc[t]:.2f}",
                "pct_dcf": f"{pct_dcf[t]:.2f}",
                "valuation_rank": (val[t].get("valuation_rank") or "") if t in val else "",
                "valuation_score": (val[t].get("valuation_score") or "") if t in val else "",
                "tier": tier,
                "_sc": comp,
            }
        )

    rows.sort(key=lambda x: -float(x["_sc"]))
    for i, row in enumerate(rows, start=1):
        row["composite_rank"] = str(i)
        del row["_sc"]

    fieldnames = [
        "ticker",
        "composite_rank",
        "composite_score",
        "pct_scenario",
        "pct_rubric",
        "pct_risk",
        "pct_mc",
        "pct_dcf",
        "valuation_rank",
        "valuation_score",
        "tier",
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(
        f"Wrote {args.out} ({len(rows)} tickers, weights={weights})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
