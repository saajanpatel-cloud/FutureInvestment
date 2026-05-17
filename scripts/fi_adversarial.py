#!/usr/bin/env python3
"""
Adversarial Workflow E packs — load/save, batch selection, heuristics, shortlist gates.

Not investment advice.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
PACKS_PATH = W / "adversarial_packs.json"
MEMO_DIR = ROOT / "research" / "memoes" / "adversarial"

THEME_ONLY_SLUGS: frozenset[str] = frozenset({"quantum", "space"})
QUANTUM_COMPUTE_PURE: frozenset[str] = frozenset(
    {"IONQ", "QBTS", "RGTI", "QUBT", "ARQQ", "LAES", "HOLO"}
)
VALID_GATES = frozenset({"pass", "watch", "reject", "reject_seat"})
VALID_VERDICTS = frozenset({"pass", "watch", "reject", "needs_primary_research"})


def utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_packs() -> dict[str, dict[str, Any]]:
    if not PACKS_PATH.is_file():
        return {}
    try:
        doc = json.loads(PACKS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    raw = doc.get("packs") if isinstance(doc, dict) else doc
    if not isinstance(raw, dict):
        return {}
    return {k.strip().upper(): v for k, v in raw.items() if isinstance(v, dict)}


def save_packs(packs: dict[str, dict[str, Any]], *, meta: dict[str, Any] | None = None) -> None:
    PACKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "packs": packs,
    }
    if meta:
        doc["meta"] = meta
    PACKS_PATH.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def pack_complete(pack: dict[str, Any] | None) -> bool:
    if not pack:
        return False
    if not pack.get("workflow_e_complete"):
        return False
    gate = (pack.get("shortlist_gate") or "").strip()
    return gate in VALID_GATES


def earnings_ref_mtime(ern_path: Path) -> float:
    if ern_path.is_file():
        return ern_path.stat().st_mtime
    return 0.0


def pack_stale(pack: dict[str, Any], ern_mtime: float) -> bool:
    if not pack_complete(pack):
        return True
    as_of = (pack.get("as_of") or "").strip()
    if not as_of:
        return True
    gen = (pack.get("earnings_mtime") or 0.0)
    if ern_mtime > float(gen) + 1.0:
        return True
    return False


def is_theme_only_slug(theme_slug: str) -> bool:
    return (theme_slug or "").strip() in THEME_ONLY_SLUGS


def needs_adversarial(
    ticker: str,
    theme_slug: str,
    packs: dict[str, dict[str, Any]],
    *,
    in_pool: bool = False,
    in_prior_core: bool = False,
    force: bool = False,
    ern_mtime: float = 0.0,
) -> bool:
    del theme_slug, in_pool, in_prior_core  # batch union defines scope
    if force:
        return True
    pack = packs.get(ticker.upper())
    if pack_complete(pack) and not pack_stale(pack, ern_mtime):
        return False
    return True


def build_review_batch(
    theme_by: dict[str, str],
    pool: list[str],
    prior_core: set[str],
    packs: dict[str, dict[str, Any]],
    *,
    force: bool = False,
    universe: bool = False,
    ern_mtime: float = 0.0,
) -> list[str]:
    """Union: theme_only manifest tickers + pool + prior core missing/stale packs."""
    batch: set[str] = set()
    if universe:
        batch.update(t for t, slug in theme_by.items() if slug)
    else:
        for t, slug in theme_by.items():
            if is_theme_only_slug(slug):
                batch.add(t)
        batch.update(pool)
        batch.update(prior_core)

    out: list[str] = []
    for t in sorted(batch):
        slug = theme_by.get(t, "")
        if needs_adversarial(
            t,
            slug,
            packs,
            in_pool=t in set(pool),
            in_prior_core=t in prior_core,
            force=force,
            ern_mtime=ern_mtime,
        ):
            out.append(t)
    return out


def _rubric_total(row: dict[str, str]) -> int | None:
    from fi_narrative import rubric_total

    return rubric_total(row)


def _ri(row: dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(float(row.get(key) or default))
    except (TypeError, ValueError):
        return default


def heuristic_pack(
    ticker: str,
    rub: dict[str, str],
    man: dict[str, str],
    earn: dict[str, str],
    *,
    ern_mtime: float = 0.0,
) -> dict[str, Any]:
    """Rule-based Workflow E when no LLM API key (or parse failure)."""
    slug = (man.get("theme_slug") or "").strip()
    link = (man.get("linkage_one_liner") or "").strip()
    tot = _rubric_total(rub) or 0
    tail = _ri(rub, "tail_risks")
    growth = _ri(rub, "growth")
    val = _ri(rub, "valuation")
    t = ticker.upper()
    quantum_pure = t in QUANTUM_COMPUTE_PURE

    bear: list[str] = []
    if slug == "quantum" and not quantum_pure:
        bear.append(
            "Theme linkage is weak: name sits in quantum sleeve but revenue is not primarily quantum compute [soft]"
        )
        bear.append("Seat policy prefers pure-play quantum listings over adjacent semi equipment [soft]")
    if tail >= 4:
        bear.append("Elevated tail-risk score on rubric (regulation, concentration, or governance) [soft]")
    if growth <= 2:
        bear.append("Growth momentum weak — thesis may depend on optionality that never monetizes [soft]")
    if val <= 2 and growth >= 4:
        bear.append("Valuation stretch vs growth — multiple compression if growth decelerates [soft]")
    if slug in ("quantum", "space"):
        bear.append("Commercial revenue for the headline theme remains early or uneven — timing risk [soft]")
    if not bear:
        bear.append("Macro or cycle turns against the name [soft]")
        bear.append("Execution miss vs guidance [soft]")
    while len(bear) < 4:
        bear.append("Second-order customer or capex dependency not fully visible in snapshot [soft]")

    if slug == "quantum" and not quantum_pure:
        gate = "reject_seat"
        linkage = "weak"
        verdict = "watch"
        seat_score = 15
    elif tot < 10 and slug in THEME_ONLY_SLUGS:
        gate = "reject"
        linkage = "weak"
        verdict = "reject"
        seat_score = 5
    elif tail >= 4 and tot < 14:
        gate = "watch"
        linkage = "mixed"
        verdict = "watch"
        seat_score = 35
    else:
        gate = "pass"
        linkage = "strong" if link and quantum_pure else ("mixed" if link else "weak")
        verdict = "pass"
        seat_score = 55 + min(tot, 24) + (25 if quantum_pure else 0)

    premortem = (
        f"If this is a poor outcome in five years, the likely reason is "
        f"{'the theme pays off too late or never at scale' if slug in THEME_ONLY_SLUGS else 'growth stalls or the multiple resets lower'}."
    )
    kill = []
    if slug == "quantum":
        kill.append("Two consecutive quarters of cash burn acceleration without funded runway through 2027")
    kill.append("Material guidance cut vs consensus on revenue or margins")
    if quantum_pure:
        kill.append("Loss of key government or cloud partner contract disclosed in filings")

    rebuttal = [
        {
            "bear": bear[0],
            "response": "risk" if gate != "pass" else "rebuttal",
            "note": "Verify in 10-K/10-Q before sizing",
        }
    ]

    return {
        "workflow_e_complete": True,
        "as_of": utc_today(),
        "earnings_mtime": ern_mtime,
        "source": "heuristic",
        "verdict": verdict,
        "shortlist_gate": gate,
        "linkage_grade": linkage,
        "quantum_pure": quantum_pure,
        "seat_score": seat_score,
        "bear_bullets": bear[:6],
        "premortem": premortem,
        "rebuttal": rebuttal,
        "kill_criteria": kill,
        "seat_rationale": (
            f"{t}: gate={gate}, quantum_pure={quantum_pure}, seat_score={seat_score}, linkage={linkage}"
        ),
    }


def normalize_pack(raw: dict[str, Any], ticker: str) -> dict[str, Any]:
    gate = (raw.get("shortlist_gate") or "watch").strip().lower()
    if gate not in VALID_GATES:
        gate = "watch"
    verdict = (raw.get("verdict") or gate).strip().lower()
    if verdict not in VALID_VERDICTS:
        verdict = "watch" if gate == "watch" else ("reject" if gate.startswith("reject") else "pass")
    bears = raw.get("bear_bullets") or raw.get("bear_case") or []
    if isinstance(bears, str):
        bears = [b.strip() for b in re.split(r"[·\n;]", bears) if b.strip()]
    kill = raw.get("kill_criteria") or []
    if isinstance(kill, str):
        kill = [k.strip() for k in re.split(r"[·\n;]", kill) if k.strip()]
    t = ticker.upper()
    return {
        "workflow_e_complete": True,
        "as_of": (raw.get("as_of") or utc_today()).strip(),
        "earnings_mtime": raw.get("earnings_mtime", 0.0),
        "source": (raw.get("source") or "llm").strip(),
        "verdict": verdict,
        "shortlist_gate": gate,
        "linkage_grade": (raw.get("linkage_grade") or "mixed").strip(),
        "quantum_pure": bool(raw.get("quantum_pure")) or t in QUANTUM_COMPUTE_PURE,
        "seat_score": int(raw.get("seat_score") or 50),
        "bear_bullets": list(bears)[:8],
        "premortem": (raw.get("premortem") or "").strip(),
        "rebuttal": raw.get("rebuttal") if isinstance(raw.get("rebuttal"), list) else [],
        "kill_criteria": list(kill)[:6],
        "seat_rationale": (raw.get("seat_rationale") or "").strip(),
    }


def pack_bear_text(pack: dict[str, Any]) -> str:
    bullets = pack.get("bear_bullets") or []
    return " · ".join(str(b) for b in bullets if b)


def pack_kill_text(pack: dict[str, Any]) -> str:
    kills = pack.get("kill_criteria") or []
    return " · ".join(str(k) for k in kills if k)


def apply_pack_to_item(item: dict[str, Any], pack: dict[str, Any]) -> None:
    """Merge completed pack into core-shortlist item narrative fields."""
    if not pack_complete(pack):
        return
    bear = pack_bear_text(pack)
    kill = pack_kill_text(pack)
    prem = (pack.get("premortem") or "").strip()
    if bear:
        item["qual_bear"] = bear[:220]
    if kill:
        item["key_risk_kill"] = kill[:420]
        item["research_kill"] = kill[:420]
    if prem:
        item["research_premortem"] = prem[:800]
    item["adversarial_pack"] = {
        "verdict": pack.get("verdict"),
        "shortlist_gate": pack.get("shortlist_gate"),
        "seat_score": pack.get("seat_score"),
        "as_of": pack.get("as_of"),
    }


def shortlist_gate(packs: dict[str, dict[str, Any]], ticker: str) -> str:
    p = packs.get(ticker.upper()) or {}
    g = (p.get("shortlist_gate") or "pass").strip().lower()
    return g if g in VALID_GATES else "pass"


def is_pool_rejected(packs: dict[str, dict[str, Any]], ticker: str) -> bool:
    return shortlist_gate(packs, ticker) == "reject"


def is_seat_blocked(packs: dict[str, dict[str, Any]], ticker: str) -> bool:
    g = shortlist_gate(packs, ticker)
    return g in ("reject", "reject_seat")


def filter_pool_rejects(pool: list[str], packs: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    kept: list[str] = []
    dropped: list[str] = []
    for t in pool:
        if is_pool_rejected(packs, t):
            dropped.append(t)
        else:
            kept.append(t)
    return kept, dropped


def write_memo_md(ticker: str, pack: dict[str, Any]) -> None:
    try:
        MEMO_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    path = MEMO_DIR / f"{ticker.upper()}.md"
    lines = [
        f"# Adversarial pack — {ticker.upper()}",
        "",
        f"**Not investment advice.** Generated {pack.get('as_of', '')} ({pack.get('source', '')}).",
        "",
        f"**Verdict:** {pack.get('verdict')} · **Shortlist gate:** {pack.get('shortlist_gate')}",
        "",
        "## Bear case",
        "",
    ]
    for b in pack.get("bear_bullets") or []:
        lines.append(f"- {b}")
    lines.extend(["", "## Pre-mortem", "", pack.get("premortem") or "—", "", "## Kill criteria", ""])
    for k in pack.get("kill_criteria") or []:
        lines.append(f"- {k}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
