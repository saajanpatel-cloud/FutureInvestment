#!/usr/bin/env python3
"""
Populate dashboard-facing narrative fields on each `core-shortlist.json` item.

Run after `fi_select_shortlist_growth.py` and `fi_finnhub_context.py` refresh.
Typically invoked from `scripts/refresh_watchlists.sh`.

Not investment advice.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from fi_adversarial import apply_pack_to_item, load_packs, pack_complete
from fi_narrative import (
    compute_research_status,
    format_deep_dive_sections,
    format_kill,
    format_premortem_stub,
    format_qual_bull_bear_watch,
    format_research_glance,
    format_research_thesis,
    format_why,
)
from fi_refresh_signals import enrich_all as enrich_refresh_signals
from fi_theme_targets import load_theme_weights

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
UI = ROOT / "watchlist-ui"
CORE_JSON = UI / "core-shortlist.json"
RUB = W / "rubric_scores.csv"
MAN = W / "universe_manifest.csv"
ERN = W / "earnings_data.csv"
FH_CSV = W / "finnhub_context.csv"
PROFILE_CSV = W / "company_profile.csv"
SCEN = W / "scenario_results.csv"
MC = W / "monte_carlo_results.csv"
RISK = W / "risk_metrics.csv"
DCF = W / "dcf_sensitivity.csv"
OVERRIDES = W / "company_overrides.json"
GROWTH_LENS = W / "theme_growth_lens.json"


def load_growth_lens() -> dict[str, dict]:
    if not GROWTH_LENS.is_file():
        return {}
    try:
        doc = json.loads(GROWTH_LENS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return doc.get("tickers") or {}


def apply_growth_lens(it: dict, t: str, lens_by: dict[str, dict]) -> None:
    row = lens_by.get(t)
    if not row:
        return
    mech = (row.get("growth_mechanism") or "").strip()
    qual = (row.get("growth_quality") or "").strip()
    tier = (row.get("linkage_tier") or "").strip()
    rank = row.get("within_theme_rank")
    cats = row.get("recent_catalysts") or []
    parts: list[str] = []
    if tier:
        parts.append(f"Growth linkage: {tier.replace('_', ' ')}")
    if mech:
        parts.append(mech)
    if qual:
        parts.append(f"Growth quality flag: {qual.replace('_', ' ')}")
    if rank is not None:
        parts.append(f"Within-theme growth rank #{rank}")
    if cats:
        parts.append("Recent catalysts: " + "; ".join(str(c) for c in cats[:2]))
    if not parts:
        return
    suffix = " · ".join(parts)
    w = (it.get("qual_watch") or "").strip()
    it["qual_watch"] = (w + " · " + suffix) if w else suffix
    it["growth_lens"] = row


def load_csv_map(path: Path, key: str) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    out: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            k = (r.get(key) or "").strip().upper()
            if k:
                out[k] = r
    return out


def format_market_context_row(fh: dict[str, str] | None) -> str:
    if fh:
        line = (fh.get("context_line") or "").strip()
        if line and line != "FINNHUB_API_KEY not configured.":
            return line
    return (
        "No Finnhub context — run fi_finnhub_context.py with FINNHUB_API_KEY in .env "
        "(see refresh_watchlists.sh)."
    )


def theme_weighted_alloc_strings(
    tickers: list[str], man: dict[str, dict[str, str]], weights: dict[str, float]
) -> dict[str, str]:
    from collections import Counter

    if not tickers:
        return {}
    cnt = Counter((man.get(t, {}).get("theme_slug") or "").strip() for t in tickers)
    cnt = {k: v for k, v in cnt.items() if k}
    present = set(cnt.keys())
    wp = sum(weights.get(s, 0.0) for s in present)
    out: dict[str, str] = {}
    if wp <= 1e-9:
        base = 100.0 / len(tickers)
        for t in tickers:
            out[t] = f"{base:.2f}%"
        return out
    raw: list[float] = []
    for t in tickers:
        s = (man.get(t, {}).get("theme_slug") or "").strip()
        theme_pts = 100.0 * weights.get(s, 0.0) / wp
        raw.append(theme_pts / cnt[s])
    rounded = [round(x, 2) for x in raw]
    drift = round(100.0 - sum(rounded), 2)
    if tickers and abs(drift) >= 0.001:
        rounded[-1] = round(rounded[-1] + drift, 2)
    for t, r in zip(tickers, rounded):
        out[t] = f"{r:.2f}%"
    return out


def main() -> None:
    if not CORE_JSON.is_file():
        print(f"Missing {CORE_JSON}", file=sys.stderr)
        sys.exit(2)

    doc = json.loads(CORE_JSON.read_text(encoding="utf-8"))
    items = doc.get("items") or []
    if not items:
        print("core-shortlist.json has no items", file=sys.stderr)
        sys.exit(2)

    rub_by = load_csv_map(RUB, "ticker")
    man_by = load_csv_map(MAN, "ticker")
    fh_by = load_csv_map(FH_CSV, "ticker")
    prof_by = load_csv_map(PROFILE_CSV, "ticker")
    scen_by = load_csv_map(SCEN, "ticker")
    mc_by = load_csv_map(MC, "ticker")
    risk_by = load_csv_map(RISK, "ticker")
    earn: dict[str, dict[str, str]] = load_csv_map(ERN, "ticker")
    dcf_by: dict[str, list[dict[str, str]]] = {}
    if DCF.is_file():
        with DCF.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                t = (row.get("ticker") or "").strip().upper()
                if t:
                    dcf_by.setdefault(t, []).append(row)

    ov: dict = {}
    if OVERRIDES.is_file():
        ov = json.loads(OVERRIDES.read_text(encoding="utf-8"))

    adversarial_packs = load_packs()
    lens_by = load_growth_lens()

    tickers = [(it.get("ticker") or "").strip().upper() for it in items if it.get("ticker")]
    weights = load_theme_weights()
    allocs = theme_weighted_alloc_strings(tickers, man_by, weights)

    delta = (doc.get("selection_memo") or {}).get("shortlist_delta") or {}
    prior_as_of = str(delta.get("prior_as_of") or doc.get("as_of") or "")
    baseline = bool(delta.get("baseline_established"))

    for it in items:
        t = (it.get("ticker") or "").strip().upper()
        if not t:
            continue
        rub = rub_by.get(t, {})
        man = man_by.get(t, {})
        slug = (man.get("theme_slug") or "").strip()
        link = (man.get("linkage_one_liner") or "").strip()
        theme_lbl = (man.get("theme_label") or man.get("theme_slug") or "").strip()
        e = earn.get(t, {})

        kill = format_kill(rub, slug)
        it["why_this_name"] = format_why(link, e, rub, it)
        it["market_context"] = format_market_context_row(fh_by.get(t))
        it.pop("social_sentiment", None)
        it.pop("sentiment_note", None)
        it["key_risk_kill"] = kill
        it["research_kill"] = kill
        it["research_thesis"] = format_research_thesis(link, e, rub)
        prem = format_premortem_stub(rub, slug)
        it["research_premortem"] = prem
        it["research_glance"] = format_research_glance(link, theme_lbl, kill)
        bull, bear, watch = format_qual_bull_bear_watch(rub, link, slug)
        it["qual_bull"] = bull
        it["qual_bear"] = bear
        it["qual_watch"] = watch
        it["alloc_pct"] = allocs.get(t, "")
        apply_growth_lens(it, t, lens_by)

        pack = adversarial_packs.get(t)
        if pack_complete(pack):
            apply_pack_to_item(it, pack)

        ovr = (ov.get(t) or {}) if isinstance(ov, dict) else {}
        prem_for_status = (it.get("research_premortem") or prem).strip()
        it["research_status"] = compute_research_status(
            rub,
            slug,
            prem_for_status,
            ovr.get("research_status"),
            pack=pack,
        )
        profile = prof_by.get(t, {})
        if ovr.get("business_summary"):
            profile = {**profile, "business_summary": ovr["business_summary"]}
        it["deep_dive"] = format_deep_dive_sections(
            item=it,
            rub=rub,
            man=man,
            profile=profile,
            earn=e,
            scen=scen_by.get(t),
            mc=mc_by.get(t),
            risk=risk_by.get(t),
            alloc_pct=allocs.get(t, ""),
            prior_as_of=prior_as_of,
            baseline=baseline,
            dcf_rows=dcf_by.get(t),
            fh_row=fh_by.get(t),
        )

    CORE_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    enrich_refresh_signals()
    print(f"Enriched {len(items)} items → {CORE_JSON}", file=sys.stderr)


if __name__ == "__main__":
    main()
