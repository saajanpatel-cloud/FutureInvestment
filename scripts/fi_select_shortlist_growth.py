#!/usr/bin/env python3
"""
Select **at least 20** (up to 28) dashboard core tickers.

**Composite mode** (default when `universe_composite_rank.csv` exists): pool ~60 by
five-signal composite (scenario, rubric, risk, Monte Carlo, DCF percentiles) + tie-breaks;
theme caps; tier expansion from `universe_valuation_rank.csv` when present.

**Valuation-first fallback** (rank file only): pool by valuation_score + rubric tie-break.

**Legacy mode** (no rank files): rubric pool + four-lens Borda → caps.

Writes:
  research/watchlists/report_core_tickers.txt
  watchlist-ui/core-shortlist.json   (includes selection_memo + per-ticker model ranks)

Not investment advice.
"""
from __future__ import annotations

import csv
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
UI = ROOT / "watchlist-ui"
RUB = W / "rubric_scores.csv"
MAN = W / "universe_manifest.csv"
ERN = W / "earnings_data.csv"
OUT_TXT = W / "report_core_tickers.txt"
OUT_JSON = UI / "core-shortlist.json"
RANK_CSV = W / "universe_valuation_rank.csv"
COMPOSITE_CSV = W / "universe_composite_rank.csv"

SHORTLIST_MIN = 20
SHORTLIST_MAX = 28
POOL_TOP = 60
# Avoid screening out extreme YoY / early-stage names before any multi-model pass:
# keep most of the pool as "top by rubric composite total", then add a small YoY rescue slice.
POOL_BY_TOTAL = 52
POOL_YOY_RESCUE = 8
POOL_YOY_RESCUE_MIN = 30.0  # % YoY; must have earnings row

# Legacy 15-name sleeve (diff narrative only)
PREVIOUS_15 = {
    "AMAT",
    "ANET",
    "ETN",
    "FSLR",
    "FTNT",
    "IBM",
    "IONQ",
    "ISRG",
    "LLY",
    "NEE",
    "NVDA",
    "PANW",
    "QBTS",
    "ROK",
    "VST",
}

# Theme seat caps come from research/watchlists/theme_target_weights.json (largest remainder × SHORTLIST_MAX).

# Names that must stay on the core sleeve if they clear the pool + a minimum rubric bar
# (swap out the weakest consensus name in the same theme bucket if the theme is full).
ANCHOR_TICKERS: frozenset[str] = frozenset({"NVDA"})
MIN_ANCHOR_RUBRIC_TOTAL = 18  # G+M+BS+D+V−tail scale (~0–24); keeps anchors from rescuing weak names

# Thin sleeves: greedy fill to SHORTLIST_MIN can exhaust seats before the walk reaches a
# low-weight theme. When cap≥1 for this slug and a pool name clears the floor, swap in
# the best consensus-ranked name from that theme for the weakest non-anchor pick.
THEME_SEAT_SLUG = "quantum"
MIN_THEME_SEAT_RUBRIC_TOTAL = 8  # G+M+BS+D+V−tail (~6–10 band for representation)
METHOD_THEME_SEAT_NOTE = (
    f" Theme-seat ({THEME_SEAT_SLUG}): if that sleeve’s cap ≥1 and no {THEME_SEAT_SLUG} name is selected yet, "
    f"the best in-pool {THEME_SEAT_SLUG} in consensus order (rubric ≥{MIN_THEME_SEAT_RUBRIC_TOTAL}) may replace "
    "the weakest non-anchor name."
)
# When the manifest “quantum” sleeve mixes adjacent semi names, prefer explicit quantum-compute listings for the seat.
QUANTUM_COMPUTE_PURE: frozenset[str] = frozenset(
    {"IONQ", "QBTS", "RGTI", "QUBT", "ARQQ", "LAES", "HOLO"}
)

EU_LISTING_SUFFIXES: tuple[str, ...] = (
    ".PA",
    ".DE",
    ".AS",
    ".BR",
    ".CO",
    ".SW",
    ".HE",
    ".ST",
    ".MI",
    ".MC",
    ".LS",
    ".WA",
    ".VI",
    ".NA",
    ".LU",
    ".IR",
)


def clean_synced_note(note: str) -> str:
    n = (note or "").strip()
    for suf in ("; yfin — verify filings", "yfin — verify filings"):
        if n.endswith(suf):
            n = n[: -len(suf)].rstrip().rstrip(";").strip()
    return n


def listing_tie_bonus(ticker: str) -> float:
    """Tie-break: US > continental Europe > London (thematic sleeve; not a macro forecast)."""
    u = ticker.upper()
    if u.endswith(".L"):
        return 0.02
    for suf in EU_LISTING_SUFFIXES:
        if u.endswith(suf):
            return 0.15
    if "." in u:
        return 0.10
    return 0.45


def ensure_anchor_tickers(
    picked: list[str],
    pool_set: set[str],
    rub_by: dict[str, dict[str, str]],
    theme_by: dict[str, str],
    scores: dict[str, float],
    caps: dict[str, int],
) -> list[str]:
    """Swap in anchor names (e.g. NVDA) if they are in the pool, pass the rubric bar, but missed caps."""
    out = list(picked)
    protect = set(ANCHOR_TICKERS)
    for anchor in sorted(ANCHOR_TICKERS):
        if anchor in out:
            continue
        if anchor not in pool_set:
            continue
        tot_a = rubric_total(rub_by.get(anchor, {}))
        if tot_a is None or tot_a < MIN_ANCHOR_RUBRIC_TOTAL:
            continue
        slug_a = theme_by.get(anchor, "")
        if not slug_a:
            continue
        n_theme = sum(1 for x in out if theme_by.get(x) == slug_a)
        cap_a = caps.get(slug_a, 99)
        if n_theme >= cap_a:
            victims = [t for t in out if theme_by.get(t) == slug_a and t not in protect]
        else:
            victims = [t for t in out if t not in protect]
        if not victims:
            continue
        victim = min(victims, key=lambda t: (scores.get(t, 0.0), rubric_total(rub_by.get(t, {})) or 0))
        out[out.index(victim)] = anchor
    return out


def ensure_theme_seat(
    picked: list[str],
    pool_set: set[str],
    rub_by: dict[str, dict[str, str]],
    theme_by: dict[str, str],
    consensus_order: list[str],
    scores: dict[str, float],
    caps: dict[str, int],
    *,
    theme_slug: str,
    min_rubric_total: int,
    ck: dict[str, dict[str, str]] | None = None,
    rk: dict[str, dict[str, str]] | None = None,
    packs: dict[str, dict] | None = None,
) -> list[str]:
    """
    If `theme_slug` has cap ≥1 and no picked name uses that sleeve, swap in the first
    in-pool ticker on `consensus_order` that clears `min_rubric_total`, evicting the
    weakest score/ticker among non-anchor names (same victim rule as anchors).

    If the pool (e.g. top composite-60) contains no qualifying name in that sleeve,
    but `ck` is provided (composite universe), pick the best composite-ranked ticker
    in that sleeve that clears the rubric floor — so a thin policy weight (quantum)
    still appears when the sleeve exists in the ranked universe.
    """
    out = list(picked)
    protect = set(ANCHOR_TICKERS)
    use_pure = theme_slug == "quantum"
    adv = packs or {}
    if caps.get(theme_slug, 0) < 1:
        return out

    def seat_blocked(t: str) -> bool:
        from fi_adversarial import is_seat_blocked

        return is_seat_blocked(adv, t)

    def seated_bad(t: str) -> bool:
        if seat_blocked(t):
            return True
        if use_pure:
            p = adv.get(t, {}) or {}
            if p.get("shortlist_gate") == "reject_seat" or p.get("linkage_grade") == "weak":
                return True
            if t not in QUANTUM_COMPUTE_PURE and not p.get("quantum_pure"):
                return True
        return False

    seated = [t for t in out if theme_by.get(t) == theme_slug]
    if seated and not any(seated_bad(t) for t in seated):
        return out
    for t in seated:
        if seated_bad(t) and t in out:
            out.remove(t)

    def seat_rank_key(t: str) -> tuple:
        p = adv.get(t.upper()) or {}
        qp = 1 if p.get("quantum_pure") or t in QUANTUM_COMPUTE_PURE else 0
        seat = int(p.get("seat_score") or 0)
        try:
            pos = consensus_order.index(t)
        except ValueError:
            pos = 9999
        return (qp, seat, -pos)

    def qualifies(t: str) -> bool:
        if theme_by.get(t) != theme_slug:
            return False
        if seat_blocked(t):
            return False
        tot = rubric_total(rub_by.get(t, {}))
        return tot is not None and tot >= min_rubric_total

    chosen: str | None = None

    in_pool_q = [t for t in consensus_order if t in pool_set and qualifies(t)]
    in_pool_q.sort(key=seat_rank_key, reverse=True)
    if use_pure:
        pure_ordered = [t for t in in_pool_q if t in QUANTUM_COMPUTE_PURE or (adv.get(t, {}).get("quantum_pure"))]
        chosen = pure_ordered[0] if pure_ordered else (in_pool_q[0] if in_pool_q else None)
    else:
        chosen = in_pool_q[0] if in_pool_q else None

    if chosen is None and ck:
        outside: list[str] = []
        for t in ck:
            if not qualifies(t):
                continue
            outside.append(t)
        outside.sort(key=seat_rank_key, reverse=True)
        if outside:
            if use_pure:
                pure_out = [
                    t
                    for t in outside
                    if t in QUANTUM_COMPUTE_PURE or (adv.get(t, {}).get("quantum_pure"))
                ]
                chosen = pure_out[0] if pure_out else outside[0]
            else:
                chosen = outside[0]
    if not chosen:
        return out
    victims = [t for t in out if t not in protect]
    if not victims:
        return out
    victim = min(
        victims,
        key=lambda t: (scores.get(t, 0.0), rubric_total(rub_by.get(t, {})) or 0),
    )
    out[out.index(victim)] = chosen
    if chosen not in scores:
        if ck and chosen in ck:
            scores[chosen] = float(ck[chosen].get("composite_score") or 0.0)
        elif rk and chosen in rk:
            scores[chosen] = float(rk[chosen].get("valuation_score") or 0.0)
        else:
            scores[chosen] = 0.0
    return out


def safe_float(x) -> float | None:
    if x is None or x == "":
        return None
    try:
        v = float(x)
        if math.isnan(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def ri(row: dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(row[key])
    except (KeyError, ValueError):
        return default


def rubric_total(row: dict[str, str]) -> int | None:
    """G + M + BS + D + V − Tail (1–5 each)."""
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


def resilience_score(row: dict[str, str]) -> int:
    """Higher = stronger balance sheet / franchise shape in rubric space (ex growth & valuation)."""
    m = ri(row, "margins")
    bs = ri(row, "balance_sheet")
    d = ri(row, "durability")
    tail = ri(row, "tail_risks")
    return m + bs + d + (6 - tail)


def read_prior_core(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if re.fullmatch(r"[A-Z0-9.\-]{1,12}", s):
            out.add(s.upper())
    return out


def rank_pool(
    pool: list[str],
    rub_by: dict[str, dict[str, str]],
    earn: dict[str, dict[str, str]],
    theme_by: dict[str, str],
) -> dict[str, list[str]]:
    """Return model_name -> tickers ordered best-first within pool."""

    def yoy(t: str) -> float:
        y = safe_float(earn.get(t, {}).get("rev_yoy_pct"))
        return y if y is not None else -1e9

    rows = {t: rub_by[t] for t in pool}

    def sort_key_growth(t: str) -> tuple:
        r = rows[t]
        tot = rubric_total(r) or 0
        return (ri(r, "growth"), yoy(t), tot)

    def sort_key_quality(t: str) -> tuple:
        r = rows[t]
        tot = rubric_total(r) or 0
        return (tot, ri(r, "margins"), ri(r, "growth"))

    def sort_key_resilience(t: str) -> tuple:
        r = rows[t]
        return (resilience_score(r), ri(r, "growth"), yoy(t))

    def sort_key_momentum(t: str) -> tuple:
        r = rows[t]
        tot = rubric_total(r) or 0
        return (yoy(t), ri(r, "growth"), tot)

    g = sorted(pool, key=sort_key_growth, reverse=True)
    q = sorted(pool, key=sort_key_quality, reverse=True)
    res = sorted(pool, key=sort_key_resilience, reverse=True)
    mom = sorted(pool, key=sort_key_momentum, reverse=True)
    return {"growth": g, "quality": q, "resilience": res, "momentum": mom}


def borda_scores(pool: list[str], model_orders: dict[str, list[str]]) -> dict[str, float]:
    s = len(pool)
    scores: dict[str, float] = {t: 0.0 for t in pool}
    for _name, ordered in model_orders.items():
        for i, t in enumerate(ordered):
            # rank 0 = best → points s, then s-1, ...
            scores[t] += float(s - i)
    return scores


def pick_cap_constrained(
    ordered: list[str],
    theme_by: dict[str, str],
    caps: dict[str, int],
    n: int,
) -> tuple[list[str], list[str]]:
    """
    Greedy pick in `ordered` order. Returns (picked, deferred).
    `deferred` = tickers we skipped only because of caps (still high priority for backfill).
    """
    rem = dict(caps)
    picked: list[str] = []
    deferred: list[str] = []
    for t in ordered:
        if len(picked) >= n:
            break
        slug = theme_by.get(t, "")
        if not slug:
            continue
        if rem.get(slug, 0) <= 0:
            deferred.append(t)
            continue
        picked.append(t)
        rem[slug] -= 1
    return picked, deferred


def backfill(
    picked: list[str],
    candidates: list[str],
    universe_tot_order: list[str],
    pool_set: set[str],
    theme_by: dict[str, str],
    caps: dict[str, int],
    n: int,
) -> list[str]:
    """Fill to n using remaining cap slots only (never violate theme caps)."""
    out = list(picked)
    rem = dict(caps)
    for t in out:
        s = theme_by.get(t, "")
        if s in rem:
            rem[s] -= 1

    def try_list(lst: list[str]) -> None:
        nonlocal out, rem
        for t in lst:
            if len(out) >= n:
                return
            if t in out:
                continue
            if t not in pool_set:
                continue
            slug = theme_by.get(t, "")
            if not slug:
                continue
            if rem.get(slug, 0) <= 0:
                continue
            out.append(t)
            rem[slug] -= 1

    try_list(candidates)
    if len(out) < n:
        try_list(universe_tot_order)
    return out[:n]


def load_valuation_ranks(path: Path) -> dict[str, dict[str, str]] | None:
    if not path.is_file():
        return None
    out: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            t = (row.get("ticker") or "").strip().upper()
            if t:
                out[t] = row
    return out if len(out) >= 25 else None


def load_composite_ranks(path: Path) -> dict[str, dict[str, str]] | None:
    if not path.is_file():
        return None
    out: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            t = (row.get("ticker") or "").strip().upper()
            if t:
                out[t] = row
    return out if len(out) >= 25 else None


def ensure_anchors_in_pool(
    pool: list[str],
    pool_set: set[str],
    rub_by: dict[str, dict[str, str]],
    ck: dict[str, dict[str, str]],
) -> tuple[list[str], set[str]]:
    """Force anchor tickers into pool when rubric bar clears but composite rank missed top-N."""
    out = list(pool)
    pset = set(pool_set)
    for anchor in ANCHOR_TICKERS:
        if anchor in pset:
            continue
        if anchor not in ck:
            continue
        tot = rubric_total(rub_by.get(anchor, {}))
        if tot is None or tot < MIN_ANCHOR_RUBRIC_TOTAL:
            continue
        out.append(anchor)
        pset.add(anchor)
        print(f"WARN: anchor {anchor} added to pool below top-{POOL_TOP} composite cutoff", file=sys.stderr)
    return out, pset


def composite_pool(
    rub_by: dict[str, dict[str, str]],
    theme_by: dict[str, str],
    ck: dict[str, dict[str, str]],
    pool_top: int,
) -> tuple[list[str], set[str]]:
    """Top pool_top by composite_score, rubric total, listing tie-break."""
    cands: list[str] = []
    for t in ck:
        if not theme_by.get(t):
            continue
        if rubric_total(rub_by.get(t, {})) is None:
            continue
        cands.append(t)

    def sort_key(t: str) -> tuple[float, int, float]:
        sc = float(ck[t].get("composite_score") or 0.0)
        rt = rubric_total(rub_by[t]) or 0
        return (sc, rt, listing_tie_bonus(t))

    cands.sort(key=sort_key, reverse=True)
    pool = cands[:pool_top]
    pool_set = set(pool)
    return ensure_anchors_in_pool(pool, pool_set, rub_by, ck)


def valuation_pool(
    rub_by: dict[str, dict[str, str]],
    theme_by: dict[str, str],
    rk: dict[str, dict[str, str]],
    pool_top: int,
) -> tuple[list[str], set[str]]:
    """Top pool_top tickers by (valuation_score, rubric_total, listing_tie_bonus)."""
    cands: list[str] = []
    for t, row in rub_by.items():
        if not theme_by.get(t):
            continue
        if rubric_total(row) is None:
            continue
        if t not in rk:
            continue
        cands.append(t)

    def sort_key(t: str) -> tuple[float, int, float]:
        sc = float(rk[t].get("valuation_score") or 0.0)
        rt = rubric_total(rub_by[t]) or 0
        return (sc, rt, listing_tie_bonus(t))

    cands.sort(key=sort_key, reverse=True)
    pool = cands[:pool_top]
    return pool, set(pool)


def extend_shortlist_by_tier(
    picked: list[str],
    consensus_order: list[str],
    pool_set: set[str],
    theme_by: dict[str, str],
    caps: dict[str, int],
    tier_by: dict[str, int],
    max_n: int,
) -> list[str]:
    """After min names picked, add lower-ranked pool names while tier ≥ 1 and caps allow."""
    out = list(picked)
    rem = dict(caps)
    for x in out:
        s = theme_by.get(x, "")
        if s in rem:
            rem[s] -= 1
    have = set(out)
    for t in consensus_order:
        if len(out) >= max_n:
            break
        if t in have or t not in pool_set:
            continue
        if tier_by.get(t, 0) < 1:
            continue
        slug = theme_by.get(t, "")
        if not slug or rem.get(slug, 0) <= 0:
            continue
        out.append(t)
        have.add(t)
        rem[slug] -= 1
    return out


def main() -> None:
    from fi_adversarial import filter_pool_rejects, load_packs
    from fi_theme_targets import caps_from_weights, load_theme_weights

    adversarial_packs = load_packs()
    adversarial_disqualified: list[dict[str, str]] = []

    theme_target_weights = load_theme_weights()
    caps_budget = caps_from_weights(theme_target_weights, SHORTLIST_MAX)

    prior_file = read_prior_core(OUT_TXT)
    baseline = prior_file if prior_file else PREVIOUS_15

    earn: dict[str, dict[str, str]] = {}
    if ERN.is_file():
        with ERN.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                earn[r["ticker"].strip().upper()] = r

    theme_by: dict[str, str] = {}
    label_by: dict[str, str] = {}
    link_by: dict[str, str] = {}
    with MAN.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = r["ticker"].strip().upper()
            theme_by[t] = r["theme_slug"].strip()
            label_by[t] = r.get("theme_label", "").strip()
            link_by[t] = (r.get("linkage_one_liner") or "").strip()

    rub_by: dict[str, dict[str, str]] = {}
    with RUB.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            rub_by[r["ticker"].strip().upper()] = r

    # Full universe: manifest ∩ rubric with numeric total
    universe: list[tuple[str, int, str]] = []
    for t, row in rub_by.items():
        slug = theme_by.get(t)
        if not slug:
            continue
        tot = rubric_total(row)
        if tot is None:
            continue
        universe.append((t, tot, slug))

    universe.sort(key=lambda x: (x[1], x[0]), reverse=True)
    universe_tot_order = [t for t, _tot, _s in universe]

    def yoy_u(t: str) -> float | None:
        return safe_float(earn.get(t, {}).get("rev_yoy_pct"))

    rk = load_valuation_ranks(RANK_CSV)
    ck = load_composite_ranks(COMPOSITE_CSV)
    use_composite = ck is not None
    use_valuation = rk is not None and not use_composite

    if use_composite:
        pool, pool_set = composite_pool(rub_by, theme_by, ck, POOL_TOP)
        pool, adv_dropped = filter_pool_rejects(pool, adversarial_packs)
        pool_set = set(pool)
        for t in adv_dropped:
            p = adversarial_packs.get(t, {})
            adversarial_disqualified.append(
                {
                    "ticker": t,
                    "reason": f"adversarial shortlist_gate={p.get('shortlist_gate', 'reject')}",
                }
            )
        pool_by_total = pool[:POOL_BY_TOTAL]
        pool_rescue_tickers: list[str] = []
        model_orders = rank_pool(pool, rub_by, earn, theme_by)
        rank_by_model: dict[str, dict[str, int]] = {}
        for mname, ordered in model_orders.items():
            rank_by_model[mname] = {t: i + 1 for i, t in enumerate(ordered)}
        borda = borda_scores(pool, model_orders)
        comp_sc = {t: float(ck[t].get("composite_score") or 0.0) for t in pool}
        scores = {t: borda[t] + comp_sc[t] * 1e-6 for t in pool}
        consensus_order = sorted(
            pool,
            key=lambda t: (
                comp_sc[t],
                rubric_total(rub_by[t]) or 0,
                listing_tie_bonus(t),
                t,
            ),
            reverse=True,
        )
        picked, deferred = pick_cap_constrained(consensus_order, theme_by, caps_budget, SHORTLIST_MIN)
        cand_extra = [t for t in deferred if t not in consensus_order]
        picked = backfill(
            picked,
            consensus_order + cand_extra,
            universe_tot_order,
            pool_set,
            theme_by,
            caps_budget,
            SHORTLIST_MIN,
        )
        tier_by = {
            t: int(float(rk[t].get("tier") or 0)) if rk and t in rk else 1 for t in pool
        }
        picked = extend_shortlist_by_tier(
            picked,
            consensus_order,
            pool_set,
            theme_by,
            caps_budget,
            tier_by,
            SHORTLIST_MAX,
        )
        picked = ensure_theme_seat(
            picked,
            pool_set,
            rub_by,
            theme_by,
            consensus_order,
            scores,
            caps_budget,
            theme_slug=THEME_SEAT_SLUG,
            min_rubric_total=MIN_THEME_SEAT_RUBRIC_TOTAL,
            ck=ck,
            rk=rk,
            packs=adversarial_packs,
        )
        picked = ensure_anchor_tickers(picked, pool_set, rub_by, theme_by, scores, caps_budget)
    elif use_valuation:
        pool, pool_set = valuation_pool(rub_by, theme_by, rk, POOL_TOP)
        pool, adv_dropped = filter_pool_rejects(pool, adversarial_packs)
        pool_set = set(pool)
        for t in adv_dropped:
            p = adversarial_packs.get(t, {})
            adversarial_disqualified.append(
                {
                    "ticker": t,
                    "reason": f"adversarial shortlist_gate={p.get('shortlist_gate', 'reject')}",
                }
            )
        pool_by_total = pool[:POOL_BY_TOTAL]
        pool_rescue_tickers: list[str] = []
        model_orders = rank_pool(pool, rub_by, earn, theme_by)
        rank_by_model: dict[str, dict[str, int]] = {}
        for mname, ordered in model_orders.items():
            rank_by_model[mname] = {t: i + 1 for i, t in enumerate(ordered)}
        borda = borda_scores(pool, model_orders)
        val_sc = {t: float(rk[t].get("valuation_score") or 0.0) for t in pool}
        scores = {t: borda[t] + val_sc[t] * 1e-6 for t in pool}
        consensus_order = sorted(
            pool,
            key=lambda t: (
                val_sc[t],
                rubric_total(rub_by[t]) or 0,
                listing_tie_bonus(t),
                t,
            ),
            reverse=True,
        )
        picked, deferred = pick_cap_constrained(consensus_order, theme_by, caps_budget, SHORTLIST_MIN)
        cand_extra = [t for t in deferred if t not in consensus_order]
        picked = backfill(
            picked,
            consensus_order + cand_extra,
            universe_tot_order,
            pool_set,
            theme_by,
            caps_budget,
            SHORTLIST_MIN,
        )
        tier_by = {t: int(float(rk[t].get("tier") or 0)) for t in pool}
        picked = extend_shortlist_by_tier(
            picked,
            consensus_order,
            pool_set,
            theme_by,
            caps_budget,
            tier_by,
            SHORTLIST_MAX,
        )
        picked = ensure_theme_seat(
            picked,
            pool_set,
            rub_by,
            theme_by,
            consensus_order,
            scores,
            caps_budget,
            theme_slug=THEME_SEAT_SLUG,
            min_rubric_total=MIN_THEME_SEAT_RUBRIC_TOTAL,
            ck=ck,
            rk=rk,
            packs=adversarial_packs,
        )
        picked = ensure_anchor_tickers(picked, pool_set, rub_by, theme_by, scores, caps_budget)
    else:
        pool_by_total = [t for t, _tot, _s in universe[:POOL_BY_TOTAL]]
        base_set = set(pool_by_total)

        rescue: list[tuple[str, float]] = []
        for t, _tot, _s in universe:
            if t in base_set:
                continue
            y = yoy_u(t)
            if y is None or y < POOL_YOY_RESCUE_MIN:
                continue
            rescue.append((t, y))
        rescue.sort(key=lambda z: -z[1])
        rescue_tickers = [t for t, _y in rescue[:POOL_YOY_RESCUE]]

        pool = list(pool_by_total) + list(rescue_tickers)
        pool, adv_dropped = filter_pool_rejects(pool, adversarial_packs)
        pool_set = set(pool)
        for t in adv_dropped:
            p = adversarial_packs.get(t, {})
            adversarial_disqualified.append(
                {
                    "ticker": t,
                    "reason": f"adversarial shortlist_gate={p.get('shortlist_gate', 'reject')}",
                }
            )
        idx = POOL_BY_TOTAL
        while len(pool) < POOL_TOP and idx < len(universe):
            t = universe[idx][0]
            idx += 1
            if t in pool_set:
                continue
            pool.append(t)
            pool_set.add(t)

        pool_rescue_tickers = list(rescue_tickers)

        model_orders = rank_pool(pool, rub_by, earn, theme_by)
        scores = borda_scores(pool, model_orders)
        rank_by_model: dict[str, dict[str, int]] = {}
        for mname, ordered in model_orders.items():
            rank_by_model[mname] = {t: i + 1 for i, t in enumerate(ordered)}

        consensus_order = sorted(
            pool,
            key=lambda t: (scores[t] + listing_tie_bonus(t), rubric_total(rub_by[t]) or 0, t),
            reverse=True,
        )

        picked, deferred = pick_cap_constrained(consensus_order, theme_by, caps_budget, SHORTLIST_MAX)
        cand_extra = [t for t in deferred if t not in consensus_order]
        picked = backfill(
            picked,
            consensus_order + cand_extra,
            universe_tot_order,
            pool_set,
            theme_by,
            caps_budget,
            SHORTLIST_MAX,
        )
        picked = ensure_theme_seat(
            picked,
            pool_set,
            rub_by,
            theme_by,
            consensus_order,
            scores,
            caps_budget,
            theme_slug=THEME_SEAT_SLUG,
            min_rubric_total=MIN_THEME_SEAT_RUBRIC_TOTAL,
            ck=ck,
            rk=rk,
            packs=adversarial_packs,
        )
        picked = ensure_anchor_tickers(picked, pool_set, rub_by, theme_by, scores, caps_budget)

    quantum_seat_rationale = ""
    for t in picked:
        if theme_by.get(t) == THEME_SEAT_SLUG:
            p = adversarial_packs.get(t, {})
            quantum_seat_rationale = (p.get("seat_rationale") or f"{t} seated for {THEME_SEAT_SLUG} sleeve").strip()
            break

    adversarial_pending = [
        t
        for t in pool
        if t not in adversarial_packs or not adversarial_packs[t].get("workflow_e_complete")
    ]

    if len(picked) < SHORTLIST_MIN:
        print(
            f"WARN: shortlist has {len(picked)} tickers (< {SHORTLIST_MIN}); widen pool or relax caps.",
            file=sys.stderr,
        )

    picked_set = set(picked)
    added = sorted(picked_set - baseline)
    dropped = sorted(baseline - picked_set)

    # High YoY names outside pool (early-screen counterargument)
    high_yoy_outside: list[tuple[str, float]] = []
    for t, row in rub_by.items():
        if t in pool_set:
            continue
        if not theme_by.get(t):
            continue
        y = yoy_u(t)
        if y is not None and y >= 80.0:
            high_yoy_outside.append((t, y))
    high_yoy_outside.sort(key=lambda x: -x[1])
    high_yoy_outside = high_yoy_outside[:12]

    # Cap casualties: best consensus among pool not picked
    cap_casualties: list[str] = []
    for t in consensus_order:
        if t in picked_set:
            continue
        if len(cap_casualties) >= 8:
            break
        cap_casualties.append(t)

    if use_composite:
        method_str = (
            f"Five-signal composite: pool = top {POOL_TOP} by weighted percentile blend "
            f"(scenario, rubric, risk, Monte Carlo, DCF from {COMPOSITE_CSV.name}; weights in shortlist_weights.json), "
            f"then rubric total and US>EU>London tie-break. Theme caps fill to ≥{SHORTLIST_MIN}, "
            f"then expand to ≤{SHORTLIST_MAX} while valuation tier ≥ 1 when rank file present. "
            f"Borda lens ranks kept for comparison. Anchors {sorted(ANCHOR_TICKERS)} may enter pool below cutoff "
            f"or swap in when rubric ≥{MIN_ANCHOR_RUBRIC_TOTAL}."
            + METHOD_THEME_SEAT_NOTE
        )
        pool_breakdown = {
            "by_composite_head": pool_by_total,
            "yoy_rescue_added": pool_rescue_tickers,
        }
        counterarguments = [
            "Scenario, DCF, and Monte Carlo are correlated — weights spread but do not eliminate overlap.",
            "Percentile ranks are relative to this universe snapshot, not absolute quality.",
            "Tickers missing any universe signal row are excluded from composite (see fi_composite_universe_rank WARN).",
            "Theme caps can block a high composite name in a full bucket.",
            "US-listing tie-break is a liquidity preference, not a macro view.",
        ]
    elif use_valuation:
        method_str = (
            f"Valuation-first: pool = top {POOL_TOP} by (scenario valuation_score from {RANK_CSV.name}, "
            f"then rubric composite total, then US>EU>London listing tie-break). "
            f"Theme caps fill to ≥{SHORTLIST_MIN}, then expand to ≤{SHORTLIST_MAX} while valuation tier ≥ 1 "
            "(see fi_rank_universe.py tier rules). Borda ranks retained in JSON for comparison only. "
            f"Anchors {sorted(ANCHOR_TICKERS)} swap in as before when rubric total ≥{MIN_ANCHOR_RUBRIC_TOTAL}."
            + METHOD_THEME_SEAT_NOTE
        )
        pool_breakdown = {
            "by_valuation_head": pool_by_total,
            "yoy_rescue_added": pool_rescue_tickers,
        }
        counterarguments = [
            "Valuation scores depend on template scenario_assumptions rows for the full universe — garbage-in affects rank.",
            "fi_rank_universe uses a heuristic score from scenario weighted/base/bear upside only (MC/DCF not in composite).",
            "Theme caps can still block a high-score name in a saturated bucket.",
            "US-listing tie-break at equal valuation + rubric is a sleeve preference, not a macro view.",
            "Tier thresholds are configurable defaults — calibrate before treating Tier 3 as ‘comfortable’.",
        ]
    else:
        method_str = (
            f"Pool ≈{POOL_TOP} names: top {POOL_BY_TOTAL} by rubric composite total, plus up to {POOL_YOY_RESCUE} "
            f"'YoY rescue' names outside that slice with YoY ≥{POOL_YOY_RESCUE_MIN:g}% (then top-up by total if needed). "
            "Rubric is triage, not a truth model. Four rank-only lenses on the pool (growth / quality / resilience / momentum) "
            f"→ Borda consensus → greedy fill up to {SHORTLIST_MAX} names with theme caps (minimum {SHORTLIST_MIN} after backfill). "
            "Tie-break: slight preference for US-listed names (liquidity depth) vs EU/UK-style tickers at equal Borda. "
            f"Anchors {sorted(ANCHOR_TICKERS)} are forced into the sleeve if in the pool and rubric total ≥{MIN_ANCHOR_RUBRIC_TOTAL} "
            f"(G+M+BS+D+V−tail), swapping out the weakest same-theme name when the theme bucket is full."
            + METHOD_THEME_SEAT_NOTE
        )
        pool_breakdown = {
            "by_rubric_total": pool_by_total,
            "yoy_rescue_added": pool_rescue_tickers,
        }
        counterarguments = [
            "Theme caps are partly constrained by what the 60-name pool actually contains (e.g. few energy names can make an energy cap of 4 infeasible without widening the pool).",
            "Even with YoY rescue slots, very high-growth names below the rescue YoY floor can still miss the pool if rubric totals are weak.",
            "All four models use the same stale rubric and the same yfinance YoY snapshot — they are not independent data sources.",
            "Momentum (YoY-first) can reward one-off revenue spikes or acquisitions; resilience (balance sheet first) can overweight mature cash cows.",
            "Theme caps force diversification; that can exclude a fifth name in a dominant theme even if consensus prefers it.",
            "Greedy cap-filling walks consensus order; the last name in a thin bucket can have a much lower Borda score than the rest of the sleeve (review manually).",
            "US-listing tie-break is a dashboard preference (liquidity / coverage depth), not a macro forecast that US equities outperform EU or UK.",
        ]

    from fi_shortlist_delta import build_shortlist_delta

    shortlist_delta = build_shortlist_delta(
        picked=picked,
        added=added,
        dropped=dropped,
        cap_casualties=cap_casualties,
        pool_set=pool_set,
        theme_by=theme_by,
        rub_by=rub_by,
        earn=earn,
        scores=scores,
        rk=rk,
        ck=ck,
        shortlist_min=SHORTLIST_MIN,
        pool_top=POOL_TOP,
        caps=caps_budget,
    )

    memo = {
        "method": method_str,
        "shortlist_delta": shortlist_delta,
        "adversarial_pass_n": sum(
            1 for t in picked if adversarial_packs.get(t, {}).get("workflow_e_complete")
        ),
        "adversarial_pending": adversarial_pending[:20],
        "adversarial_disqualified": adversarial_disqualified,
        "quantum_seat_rationale": quantum_seat_rationale,
        "pool_breakdown": pool_breakdown,
        "why_not_top_20_by_rubric_alone": (
            "A single rubric total hides trade-offs between growth, quality, valuation scenario, risk, and distribution. "
            "The five-signal composite percentile blend forces names to score across models before theme caps apply."
            if use_composite
            else (
                "A single composite score hides trade-offs: extreme growers can look ‘bad’ on margins or tail risk, "
                "and high totals can reflect stale rubric cells. Multi-lens consensus reduces single-score tunnel vision "
                "while still anchoring on a broad-quality pool."
                if not use_valuation
                else "Valuation-led mode ranks from forward scenario outputs first; rubric is secondary for ties and pool margin calls."
            )
        ),
        "counterarguments": counterarguments,
        "what_to_watch_for": (
            "Compare cap_casualties and high_yoy_outside_pool: if a strategically important name appears there, "
            "consider manual overrides or widening the pool for the next pass."
        ),
        "pool_size": len(pool),
        "high_yoy_outside_pool": [{"ticker": a, "rev_yoy_pct": round(b, 1)} for a, b in high_yoy_outside],
        "cap_pressure_watchlist": cap_casualties,
        "theme_target_weights": theme_target_weights,
        "theme_seat_caps": caps_budget,
        "per_ticker_borda": {t: round(scores[t], 2) for t in picked},
        "composite_five_signal": use_composite,
        "valuation_first": use_valuation,
        "regional_policy": {
            "us_heavy_estimate": sum(1 for t in picked if listing_tie_bonus(t) >= 0.4),
            "london_estimate": sum(1 for t in picked if t.upper().endswith(".L")),
            "eu_listed_estimate": sum(
                1
                for t in picked
                if any(t.upper().endswith(s) for s in EU_LISTING_SUFFIXES)
            ),
            "note": (
                "US>EU>London tie-break at equal composite+rubric."
                if use_composite
                else "US>EU>London tie-break at equal valuation+rubric; pool orders by valuation_score first."
            ),
        },
    }

    header_line = (
        f"# {len(picked)} core tickers — five-signal composite pool ({POOL_TOP}) + tier expansion."
        if use_composite
        else (
            f"# {len(picked)} core tickers — valuation-first pool ({POOL_TOP}) + tier expansion."
            if use_valuation
            else (
                f"# {len(picked)} core tickers — multi-model consensus on a {POOL_TOP}-name pool "
                f"({POOL_BY_TOTAL} highest rubric totals + up to {POOL_YOY_RESCUE} YoY rescue ≥{POOL_YOY_RESCUE_MIN:g}%)."
            )
        )
    )
    OUT_TXT.write_text(
        "\n".join(
            [
                header_line,
                "# Dashboard / rubric subset (data-report-core). Regenerate rows: fi_rubric_html_rows.py + fi_embed_single_screen.py + fi_tag_rubric_report_core.py",
                "",
            ]
            + picked
            + [""]
        ),
        encoding="utf-8",
    )

    items = []
    for t in picked:
        slug = theme_by.get(t, "")
        lbl = label_by.get(t, "")
        pillar = f"{slug} — {lbl}" if lbl else slug
        r = rub_by[t]
        vt = ""
        vr = ""
        vs = ""
        cr = ""
        cs = ""
        if rk and t in rk:
            vt = str(int(float(rk[t].get("tier") or 0)))
            vr = (rk[t].get("valuation_rank") or "").strip()
            vs = (rk[t].get("valuation_score") or "").strip()
        if ck and t in ck:
            cr = (ck[t].get("composite_rank") or "").strip()
            cs = (ck[t].get("composite_score") or "").strip()
        notes_val = ""
        if use_composite and cr:
            notes_val = f"composite rank {cr} score {cs}; "
        elif use_valuation and vs:
            notes_val = f"val rank {vr} score {vs} tier T{vt}; "
        rg = rank_by_model["growth"].get(t)
        rq = rank_by_model["quality"].get(t)
        rr = rank_by_model["resilience"].get(t)
        rm = rank_by_model["momentum"].get(t)
        pool_ranks = (
            f"G#{rg if rg is not None else '—'} Q#{rq if rq is not None else '—'} "
            f"R#{rr if rr is not None else '—'} M#{rm if rm is not None else '—'}"
        )
        items.append(
            {
                "ticker": t,
                "pillar": pillar,
                "tier": "core",
                "valuation_tier": vt,
                "valuation_rank": vr,
                "valuation_score": vs,
                "composite_rank": cr,
                "composite_score": cs,
                "why_flagged": link_by.get(t, "")[:200],
                "notes": (
                    f"{notes_val}"
                    f"Borda {scores[t]:.1f}; ranks in pool — "
                    f"{pool_ranks}; "
                    f"rubric total {rubric_total(r) or 'n/a'} (G+M+BS+D+V−tail). {clean_synced_note(r.get('note') or '')[:180]}"
                ),
                "model_ranks_in_pool": {
                    "growth": rg,
                    "quality": rq,
                    "resilience": rr,
                    "momentum": rm,
                },
                "borda_points": round(scores[t], 2),
                "sentiment_mentions_csv": "research/watchlists/mentions.csv",
                "sentiment_note": "",
            }
        )

    UI.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(
            {
                "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "shortlist_n": len(picked),
                "shortlist_min": SHORTLIST_MIN,
                "shortlist_max": SHORTLIST_MAX,
                "pool_target_size": POOL_TOP,
                "pool_by_rubric_total_n": POOL_BY_TOTAL,
                "pool_yoy_rescue_n": POOL_YOY_RESCUE,
                "disclaimer": (
                    "Education/research only. Five-signal composite (scenario, rubric, risk, MC, DCF) — not a buy list. "
                    "Confirm material facts in filings."
                    if use_composite
                    else (
                        "Education/research only. Valuation-first rank from scenario templates + yfinance — not a buy list. "
                        "Confirm material facts in filings."
                        if use_valuation
                        else (
                            "Education/research only. Heuristic ensemble on rubric + yfinance — not a buy list. "
                            "Confirm material facts in filings."
                        )
                    )
                ),
                "selection_memo": memo,
                "items": items,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {OUT_TXT} and {OUT_JSON}", file=sys.stderr)
    print(f"Pool={len(pool)} models=4 shortlist={len(picked)}", file=sys.stderr)
    print("--- Diff vs prior report_core_tickers.txt (or legacy 15 if empty) ---", file=sys.stderr)
    print(f"ADDED ({len(added)}): " + ", ".join(added), file=sys.stderr)
    for t in added:
        r = rub_by[t]
        print(
            f"  + {t}: Borda={scores[t]:.1f} total={rubric_total(r)} theme={theme_by.get(t)}",
            file=sys.stderr,
        )
    print(f"DROPPED ({len(dropped)}): " + ", ".join(dropped), file=sys.stderr)
    for t in dropped:
        r = rub_by.get(t, {})
        print(
            f"  − {t}: total={rubric_total(r) if r else 'n/a'} — out of new shortlist or pool/caps/consensus",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
