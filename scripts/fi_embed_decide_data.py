#!/usr/bin/env python3
"""Shared Decide matrix row builders. Not investment advice."""
from __future__ import annotations

import csv
import html
from pathlib import Path

from fi_embed_core import fmt_pct

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
RUB = W / "rubric_scores.csv"
MAN = W / "universe_manifest.csv"


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
            lbl = lbl.replace("&amp;", "&")
            out[t] = lbl[:42] + ("…" if len(lbl) > 42 else "")
    return out


def load_csv_index(path: Path, key: str) -> dict[str, dict[str, str]]:
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


def rubric_class(tot: int | None) -> str:
    if tot is None:
        return ""
    if tot >= 18:
        return ' class="s-high"'
    if tot <= 8:
        return ' class="s-low"'
    return ""


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


def median_up_pct(mc: dict[str, str]) -> float | None:
    try:
        cur = float(mc["current_price"])
        med = float(mc["median_price"])
        if cur <= 0:
            return None
        return (med / cur - 1.0) * 100.0
    except (KeyError, ValueError, ZeroDivisionError):
        return None


def _num(rk: dict[str, str] | None, key: str) -> float | None:
    if not rk:
        return None
    try:
        return float(rk[key])
    except (KeyError, ValueError):
        return None


def build_separator_row(cols: int, n_extra: int) -> str:
    label = (
        f"Personal holdings (outside composite shortlist) — {n_extra} name"
        f"{'' if n_extra == 1 else 's'}"
    )
    return (
        f'            <tr class="decide-portfolio-separator">\n'
        f'              <td colspan="{cols}"><strong>{html.escape(label)}</strong></td>\n'
        f"            </tr>\n"
    )


def build_data_row(
    t: str,
    rub_by: dict[str, dict[str, str]],
    theme_by: dict[str, str],
    sc_by: dict[str, dict[str, str]],
    mc_by: dict[str, dict[str, str]],
    rk_by: dict[str, dict[str, str]],
) -> str:
    rub = rub_by.get(t, {})
    tot = rubric_total(rub)
    tot_s = str(tot) if tot is not None else "—"
    rcls = rubric_class(tot)
    th = html.escape(theme_by.get(t, "—"))
    sc = sc_by.get(t)
    mc = mc_by.get(t)
    rk = rk_by.get(t)

    w_up = w_px = None
    if sc:
        try:
            w_up = float(sc["weighted_upside"])
            w_px = float(sc["weighted_price"])
        except (KeyError, ValueError):
            pass

    med_up = median_up_pct(mc) if mc else None
    p50 = p30 = None
    if mc:
        try:
            p50 = float(mc["prob_50pct_up"])
            p30 = float(mc["prob_30pct_down"])
        except (KeyError, ValueError):
            pass

    beta = _num(rk, "beta")
    vol = _num(rk, "volatility")
    ret1y = _num(rk, "return_1y")
    sharpe = _num(rk, "sharpe")
    dd_frac = _num(rk, "max_drawdown")
    spy = _num(rk, "spy_correlation")

    beta_s = f"{beta:.2f}" if beta is not None else "—"
    vol_s = fmt_pct(vol * 100) if vol is not None else "—"
    ret_s = fmt_pct(ret1y * 100) if ret1y is not None else "—"
    sharpe_s = f"{sharpe:.2f}" if sharpe is not None else "—"
    dd_s = fmt_pct(dd_frac * 100) if dd_frac is not None else "—"
    spy_s = f"{spy:.2f}" if spy is not None else "—"

    beta_cls = ' class="s-low"' if beta is not None and beta > 1.5 else ""
    dd_cls = ' class="s-low"' if dd_frac is not None and dd_frac < -0.40 else ""
    sharpe_cls = ' class="s-high"' if sharpe is not None and sharpe > 1.0 else ""

    t_link = (
        f'<a href="#monitor" class="dd-jump" data-ticker="{html.escape(t)}">'
        f"<strong>{html.escape(t)}</strong></a>"
    )
    return (
        "            <tr>\n"
        f"              <td>{t_link}</td>\n"
        f"              <td>{th}</td>\n"
        f"              <td{rcls}>{html.escape(tot_s)}</td>\n"
        f"              <td>{html.escape(fmt_pct_signed(w_up))}</td>\n"
        f"              <td>{html.escape(fmt_price_cell(w_px))}</td>\n"
        f"              <td>{html.escape(fmt_pct_signed(med_up))}</td>\n"
        f"              <td>{html.escape(f'{p50:.1f}%' if p50 is not None else '—')}</td>\n"
        f"              <td>{html.escape(f'{p30:.1f}%' if p30 is not None else '—')}</td>\n"
        f"              <td{beta_cls}>{html.escape(beta_s)}</td>\n"
        f"              <td>{html.escape(vol_s)}</td>\n"
        f"              <td>{html.escape(ret_s)}</td>\n"
        f"              <td{sharpe_cls}>{html.escape(sharpe_s)}</td>\n"
        f"              <td{dd_cls}>{html.escape(dd_s)}</td>\n"
        f"              <td>{html.escape(spy_s)}</td>\n"
        "            </tr>"
    )
