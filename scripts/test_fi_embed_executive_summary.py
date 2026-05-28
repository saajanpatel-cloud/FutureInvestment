#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fi_embed_executive_summary import build_inner, by_tier_from_items, conviction_tier_for_item


class TestExecutiveSummary(unittest.TestCase):
    def test_conviction_tier_from_item(self):
        self.assertEqual(conviction_tier_for_item({"conviction_tier": 1}), 1)
        self.assertEqual(conviction_tier_for_item({"conviction_tier": 4}), 4)
        self.assertEqual(conviction_tier_for_item({}), 2)

    def test_by_tier_four_buckets(self):
        items = {
            "A": {"conviction_tier": 1, "composite_rank": "1"},
            "B": {"conviction_tier": 2, "composite_rank": "8"},
            "C": {"conviction_tier": 4, "composite_rank": "20"},
        }
        by = by_tier_from_items(["A", "B", "C"], items)
        self.assertEqual(by[1], ["A"])
        self.assertEqual(by[4], ["C"])

    def test_baseline_in_lead(self):
        doc = {
            "as_of": "2026-05-17",
            "shortlist_n": 1,
            "items": [{"ticker": "NVDA", "theme": "ai", "conviction_tier": 1, "composite_rank": "3", "why_this_name": "AI GPUs"}],
            "selection_memo": {
                "method": "Test.",
                "shortlist_delta": {"baseline_established": True},
            },
        }
        stats = {"uni_n": 100, "n_themes": 7, "model_n": 80, "by_slug": {}}
        inner = build_inner(doc, stats)
        self.assertIn("first saved baseline", inner.lower())

    def test_build_inner_four_tier_table(self):
        doc = {
            "as_of": "2026-05-17",
            "shortlist_n": 2,
            "items": [
                {"ticker": "NVDA", "theme": "ai", "conviction_tier": 1, "composite_rank": "2", "why_this_name": "AI GPUs"},
                {"ticker": "MU", "theme": "ai", "conviction_tier": 4, "composite_rank": "50", "why_this_name": "Memory"},
            ],
            "selection_memo": {
                "method": "Test composite.",
                "conviction_tier_note": "Quartile test.",
                "shortlist_delta": {
                    "baseline_established": False,
                    "prior_as_of": "2026-05-10",
                    "added": [],
                    "dropped": [],
                    "unchanged_count": 2,
                },
            },
        }
        stats = {"uni_n": 100, "n_themes": 7, "model_n": 80, "by_slug": {}}
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rub = root / "rubric_scores.csv"
            rub.write_text(
                "ticker,growth,margins,balance_sheet,durability,tail_risks,valuation\n"
                "NVDA,5,5,4,4,3,3\nMU,5,5,4,4,3,3\n",
                encoding="utf-8",
            )
            scen = root / "scenario_results.csv"
            scen.write_text(
                "ticker,weighted_upside,price\nNVDA,50,100\nMU,100,50\n",
                encoding="utf-8",
            )
            ern = root / "earnings_data.csv"
            ern.write_text("ticker,rev_yoy_pct\nNVDA,70\nMU,190\n", encoding="utf-8")
            with patch("fi_embed_executive_summary.RUB", rub), patch(
                "fi_embed_executive_summary.SCEN", scen
            ), patch("fi_embed_executive_summary.ERN", ern), patch(
                "fi_embed_executive_summary.RISK", root / "missing.csv"
            ):
                inner = build_inner(doc, stats)
        self.assertIn("Tier 4", inner)
        self.assertIn("composite rank #2", inner)
        self.assertIn("Tier 4 (lowest composite quartile", inner)
        self.assertIn("top quartile on five-signal composite", inner)


if __name__ == "__main__":
    unittest.main()
