#!/usr/bin/env python3
"""Rewrite Discover → Target theme weights table tbody from theme_target_weights.json."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from fi_theme_targets import load_theme_weights

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "research" / "watchlists" / "SINGLE_SCREEN_REPORT.html"

MARK_S = "<!-- FI_DISCOVER_WEIGHTS_START -->"
MARK_E = "<!-- FI_DISCOVER_WEIGHTS_END -->"

# Order and copy match Discover section (In simple words column).
ROWS: list[tuple[str, str, str]] = [
    ("ai", "AI infrastructure &amp; compute", "Chips, servers, data centres, and gear that run AI"),
    (
        "energy",
        "Energy transition &amp; grids",
        "Power, grids, and equipment as electricity demand grows",
    ),
    (
        "health",
        "Health Tech",
        "Tech-driven healthcare: robotic surgery, AI diagnostics, biotech pipelines",
    ),
    (
        "auto",
        "Industrial automation &amp; robotics",
        "Factories and robots doing more of the work",
    ),
    ("cyber", "Cybersecurity &amp; digital trust", "Blocking hacks and keeping data and systems safe"),
    (
        "quantum",
        "Quantum / frontier compute",
        'Very early "next" computers—not yet a big business for most names',
    ),
]


def build_tbody(w: dict[str, float]) -> str:
    lines: list[str] = []
    for slug, theme_html, simple in ROWS:
        pct = int(round(w[slug] * 100))
        lines.append(
            f"            <tr><td>{theme_html}</td><td>{simple}</td><td>{pct}%</td></tr>"
        )
    lines.append('            <tr><td><strong>Total</strong></td><td></td><td><strong>100%</strong></td></tr>')
    return "\n".join(lines)


def main() -> int:
    weights = load_theme_weights()
    tbody = build_tbody(weights)
    doc = HTML.read_text(encoding="utf-8")
    if MARK_S not in doc or MARK_E not in doc:
        print("Discover weights markers missing in HTML", file=sys.stderr)
        return 2
    inner = f"{MARK_S}\n{tbody}\n          {MARK_E}"
    pat = re.compile(re.escape(MARK_S) + r"[\s\S]*?" + re.escape(MARK_E), re.MULTILINE)
    doc_new, n = pat.subn(inner, doc, count=1)
    if n != 1:
        print("Could not patch discover weights", file=sys.stderr)
        return 2
    HTML.write_text(doc_new, encoding="utf-8")
    print("Patched Discover target theme weights tbody", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
