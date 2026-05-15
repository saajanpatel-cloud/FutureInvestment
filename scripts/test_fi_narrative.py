#!/usr/bin/env python3
"""Tests for fi_narrative formatters."""
from __future__ import annotations

import unittest

from fi_narrative import (
    BULLET,
    format_kill,
    format_market_context,
    format_rubric_note,
    format_verdict_summary,
    format_why,
    join_bullets,
)


class TestFiNarrative(unittest.TestCase):
    def test_join_bullets(self):
        self.assertIn("·", join_bullets(["A", "B"]))

    def test_format_rubric_note_order(self):
        earn = {"rev_yoy_pct": "73", "gross_margin_pct": "75", "op_margin_pct": "65"}
        link = "AI accelerators and data-centre GPU exposure"
        out = format_rubric_note(earn, link)
        self.assertTrue(out.startswith(link) or link in out)
        self.assertIn("Revenue up 73%", out)
        self.assertNotIn("GM ", out)

    def test_format_why_nvda_style(self):
        earn = {"rev_yoy_pct": "73", "gross_margin_pct": "75", "op_margin_pct": "65"}
        rub = {
            "growth": "5",
            "margins": "5",
            "balance_sheet": "4",
            "durability": "5",
            "tail_risks": "2",
            "valuation": "2",
        }
        it = {"model_ranks_in_pool": {"growth": 4, "quality": 5}}
        out = format_why("GPU exposure", earn, rub, it)
        self.assertIn("scorecard", out.lower())
        self.assertIn(BULLET, out)

    def test_format_market_context_plain(self):
        out = format_market_context("buy-heavy", "bearish MSPR -100", 246, "last 2026-03-31")
        self.assertIn("analysts lean buy", out.lower())
        self.assertNotIn("MSPR", out)

    def test_format_kill_quantum(self):
        rub = {"growth": "2", "tail_risks": "4", "margins": "2", "balance_sheet": "3", "durability": "2", "valuation": "2"}
        out = format_kill(rub, "quantum")
        self.assertIn("2027", out)

    def test_format_verdict_has_tier_line(self):
        rub = {"growth": "5", "margins": "5", "balance_sheet": "4", "durability": "5", "tail_risks": "2", "valuation": "2"}
        sc = {"weighted_upside": "171"}
        mc = {"current_price": "100", "median_price": "249"}
        rk = {"sharpe": "1.72", "max_drawdown": "-0.37"}
        it = {"model_ranks_in_pool": {"growth": 4}}
        out = format_verdict_summary(rub, sc, mc, rk, it)
        self.assertIn("adversarial", out.lower())


if __name__ == "__main__":
    unittest.main()
