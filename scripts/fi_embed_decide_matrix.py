#!/usr/bin/env python3
"""
Replace the <tbody> of the Decide reconciliation table in SINGLE_SCREEN_REPORT.html
with one row per ticker in report_core_tickers.txt.

Fills cells from (when present):
  - rubric_scores.csv — composite total G+M+BS+D+V−tail
  - universe_manifest.csv — short theme label
  - scenario_results.csv — weighted upside, weighted price
  - monte_carlo_results.csv — median upside %, prob columns
  - risk_metrics.csv — Sharpe, max drawdown

Missing value-model rows show em dash until you re-run fi_scenarios.py / fi_monte_carlo.py /
fi_risk_metrics.py after syncing scenario_assumptions.csv.

Usage:
  python3 scripts/fi_embed_decide_matrix.py

Not investment advice.
"""
from __future__ import annotations

import csv
import html
import json
import re
import sys
from pathlib import Path

from fi_narrative import format_verdict_summary

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
HTML = W / "SINGLE_SCREEN_REPORT.html"
CORE = W / "report_core_tickers.txt"
RUB = W / "rubric_scores.csv"
MAN = W / "universe_manifest.csv"
SC_RES = W / "scenario_results.csv"
MC_RES = W / "monte_carlo_results.csv"
RISK = W / "risk_metrics.csv"
CORE_JSON = ROOT / "watchlist-ui" / "core-shortlist.json"


def load_core() -> list[str]:
    out: list[str] = []
    for line in CORE.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s.upper())
    return out


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


def load_rubric() -> dict[str, dict[str, str]]:
    if not RUB.is_file():
        return {}
    with RUB.open(encoding="utf-8", newline="") as f:
        return {(r.get("ticker") or "").strip().upper(): r for r in csv.DictReader(f)}


def load_manifest_short_theme() -> dict[str, str]:
    if not MAN.is_file():
        return {}
    out: dict[str, str] = {}
    with MAN.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = (r.get("ticker") or "").strip().upper()
            if not t:
                continue
            lbl = (r.get("theme_label") or r.get("theme_slug") or "").strip()
            if "—" in lbl:
                lbl = lbl.split("—")[0].strip()
            if "&" in lbl:
                lbl = lbl.replace("&amp;", "&")
            out[t] = lbl[:42] + ("…" if len(lbl) > 42 else "")
    return out


def load_shortlist_items() -> dict[str, dict]:
    if not CORE_JSON.is_file():
        return {}
    try:
        doc = json.loads(CORE_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {
        (it.get("ticker") or "").strip().upper(): it
        for it in (doc.get("items") or [])
        if it.get("ticker")
    }


def load_csv_index(path: Path, key: str) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {(r.get(key) or "").strip().upper(): r for r in csv.DictReader(f)}


def fmt_pct_signed(x: float | None) -> str:
    if x is None:
        return "—"
    if x >= 0:
        return f"+{x:.0f}%"
    return f"{x:.0f}%"


def fmt_price_cell(x: float | None) -> str:
    if x is None:
        return "—"
    if x >= 1000:
        return f"${x:,.0f}"
    return f"${x:,.2f}"


def rubric_class(tot: int | None) -> str:
    if tot is None:
        return ""
    if tot >= 18:
        return ' class="s-high"'
    if tot <= 8:
        return ' class="s-low"'
    return ""


def verdict_cell_class(tot: int | None, sharpe: float | None, dd_frac: float | None) -> str:
    """Background tint for plain-language verdict column."""
    caution = (tot is not None and tot <= 10) or (sharpe is not None and sharpe < -0.25) or (
        dd_frac is not None and dd_frac <= -0.55
    )
    positive = (tot is not None and tot >= 18) and not caution
    if caution:
        return ' class="verdict-cell verdict-caution"'
    if positive:
        return ' class="verdict-cell verdict-positive"'
    return ' class="verdict-cell verdict-neutral"'


def median_up_pct(mc: dict[str, str]) -> float | None:
    try:
        cur = float(mc["current_price"])
        med = float(mc["median_price"])
        if cur <= 0:
            return None
        return (med / cur - 1.0) * 100.0
    except (KeyError, ValueError, ZeroDivisionError):
        return None


def build_tbody(
    tickers: list[str],
    rub_by: dict[str, dict[str, str]],
    theme_by: dict[str, str],
    sc_by: dict[str, dict[str, str]],
    mc_by: dict[str, dict[str, str]],
    rk_by: dict[str, dict[str, str]],
    items_by: dict[str, dict],
) -> str:
    lines: list[str] = []
    for t in tickers:
        rub = rub_by.get(t, {})
        tot = rubric_total(rub)
        tot_s = str(tot) if tot is not None else "—"
        rcls = rubric_class(tot)
        th = html.escape(theme_by.get(t, "—"))
        sc = sc_by.get(t)
        mc = mc_by.get(t)
        rk = rk_by.get(t)

        w_up = None
        w_px = None
        if sc:
            try:
                w_up = float(sc["weighted_upside"])
                w_px = float(sc["weighted_price"])
            except (KeyError, ValueError):
                pass

        med_up = median_up_pct(mc) if mc else None
        p50 = None
        p30 = None
        if mc:
            try:
                p50 = float(mc["prob_50pct_up"])
                p30 = float(mc["prob_30pct_down"])
            except (KeyError, ValueError):
                pass

        sharpe_s = "—"
        dd_s = "—"
        sharpe_v: float | None = None
        dd_frac: float | None = None
        if rk:
            try:
                sharpe_v = float(rk["sharpe"])
                sharpe_s = f"{sharpe_v:.2f}"
                dd_frac = float(rk["max_drawdown"])
                dd = dd_frac * 100.0
                dd_s = f"{dd:.0f}%"
            except (KeyError, ValueError):
                pass

        it = items_by.get(t, {})
        verdict_text = format_verdict_summary(rub, sc, mc, rk, it)
        if len(verdict_text) > 420:
            verdict_text = verdict_text[:417] + "…"
        verdict = html.escape(verdict_text)
        vcls = verdict_cell_class(tot, sharpe_v, dd_frac)

        t_link = (
            f'<a href="#monitor" class="dd-jump" data-ticker="{html.escape(t)}">'
            f"<strong>{html.escape(t)}</strong></a>"
        )
        lines.append(
            "            <tr>\n"
            f"              <td>{t_link}</td>\n"
            f"              <td>{th}</td>\n"
            f"              <td{rcls}>{html.escape(tot_s)}</td>\n"
            f"              <td>{html.escape(fmt_pct_signed(w_up))}</td>\n"
            f"              <td>{html.escape(fmt_price_cell(w_px))}</td>\n"
            f"              <td>{html.escape(fmt_pct_signed(med_up))}</td>\n"
            f"              <td>{html.escape(f'{p50:.1f}%' if p50 is not None else '—')}</td>\n"
            f"              <td>{html.escape(f'{p30:.1f}%' if p30 is not None else '—')}</td>\n"
            f"              <td>{html.escape(sharpe_s)}</td>\n"
            f"              <td>{html.escape(dd_s)}</td>\n"
            f"              <td{vcls}>{verdict}</td>\n"
            "            </tr>"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    if not CORE.is_file():
        print(f"Missing {CORE}", file=sys.stderr)
        return 2
    tickers = load_core()
    if not tickers:
        print("Empty core ticker list", file=sys.stderr)
        return 2

    rub_by = load_rubric()
    theme_by = load_manifest_short_theme()
    sc_by = load_csv_index(SC_RES, "ticker")
    mc_by = load_csv_index(MC_RES, "ticker")
    rk_by = load_csv_index(RISK, "ticker")

    items_by = load_shortlist_items()
    tbody = build_tbody(tickers, rub_by, theme_by, sc_by, mc_by, rk_by, items_by)

    text = HTML.read_text(encoding="utf-8")
    pat = re.compile(
        r'(<table class="decide-matrix print-table-rubric">\s*<thead>[\s\S]*?</thead>\s*<tbody>\s*\n)'
        r"[\s\S]*?"
        r"(\s*</tbody>\s*\n\s*</table>)",
        re.MULTILINE,
    )
    m = pat.search(text)
    if not m:
        print("Could not find decide-matrix table tbody", file=sys.stderr)
        return 2

    new_text = pat.sub(r"\1" + tbody + r"\2", text, count=1)
    if new_text == text:
        print("No substitution made", file=sys.stderr)
        return 1

    HTML.write_text(new_text, encoding="utf-8")
    print(f"Patched Decide matrix ({len(tickers)} rows) → {HTML}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
