#!/usr/bin/env python3
"""Tests for fi_narrative formatters."""
from __future__ import annotations

import unittest

from fi_narrative import (
    BULLET,
    compute_research_status,
    format_deep_dive_sections,
    format_kill,
    format_market_context,
    format_rubric_note,
    format_verdict_summary,
    format_why,
    join_bullets,
    research_status_label,
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

    def test_research_status_quantum(self):
        rub = {"growth": "2", "tail_risks": "4", "margins": "2", "balance_sheet": "3", "durability": "2", "valuation": "2"}
        self.assertEqual(compute_research_status(rub, "quantum", ""), "theme_only")
        self.assertIn("theme only", research_status_label("theme_only").lower())

    def test_research_status_adversarial_complete(self):
        rub = {"growth": "5", "margins": "5", "balance_sheet": "4", "durability": "5", "tail_risks": "2", "valuation": "2"}
        pack = {"workflow_e_complete": True, "shortlist_gate": "pass"}
        self.assertEqual(
            compute_research_status(rub, "ai", "[Auto stub] x", pack=pack),
            "adversarial_complete",
        )
        self.assertIn("on file", research_status_label("adversarial_complete").lower())

    def test_deep_dive_sections_keys(self):
        rub = {"growth": "5", "margins": "4", "balance_sheet": "4", "durability": "4", "tail_risks": "2", "valuation": "3"}
        sections = format_deep_dive_sections(
            item={"qual_bull": "A", "qual_bear": "B", "qual_watch": "W", "key_risk_kill": "K", "market_context": "M"},
            rub=rub,
            man={"theme_slug": "ai", "theme_label": "AI", "linkage_one_liner": "GPU exposure"},
            profile={"business_summary": "Chip designer", "holders_top": "Vanguard"},
            earn={"rev_yoy_pct": "50"},
            scen={"price": "100", "weighted_upside": "30"},
            mc={"current_price": "100", "median_price": "130", "p10": "80", "p90": "160"},
            risk=None,
            alloc_pct="4.5%",
            prior_as_of="2026-01-01",
            baseline=False,
        )
        self.assertIn("executive_summary", sections)
        self.assertIn("2026-01-01", sections["signals_intro"])
        self.assertIn("GPU", sections["strategic_plays"])


if __name__ == "__main__":
    unittest.main()
