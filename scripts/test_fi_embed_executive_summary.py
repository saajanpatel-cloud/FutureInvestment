#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fi_embed_executive_summary import build_inner, tier_from_total


class TestExecutiveSummary(unittest.TestCase):
    def test_tier_from_total(self):
        self.assertEqual(tier_from_total(18), 1)
        self.assertEqual(tier_from_total(15), 2)
        self.assertEqual(tier_from_total(10), 3)

    def test_baseline_in_lead(self):
        doc = {
            "as_of": "2026-05-17",
            "shortlist_n": 1,
            "items": [{"ticker": "NVDA", "theme": "ai", "why_this_name": "AI GPUs"}],
            "selection_memo": {
                "method": "Test.",
                "shortlist_delta": {"baseline_established": True},
            },
        }
        stats = {"uni_n": 100, "n_themes": 7, "model_n": 80, "by_slug": {}}
        inner = build_inner(doc, stats)
        self.assertIn("first saved baseline", inner.lower())

    def test_build_inner_has_delta(self):
        doc = {
            "as_of": "2026-05-17",
            "shortlist_n": 2,
            "items": [
                {"ticker": "NVDA", "theme": "ai", "why_this_name": "AI GPUs"},
                {"ticker": "MU", "theme": "ai", "why_this_name": "Memory"},
            ],
            "selection_memo": {
                "method": "Test composite.",
                "shortlist_delta": {
                    "baseline_established": False,
                    "prior_as_of": "2026-05-10",
                    "added": [{"ticker": "MU", "theme": "ai", "composite_rank": "1", "rubric_total": 20, "reason_label": "Pick"}],
                    "dropped": [],
                    "unchanged_count": 1,
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
        self.assertIn("added", inner.lower())
        self.assertIn("MU", inner)
        self.assertIn("NVDA", inner)
        self.assertIn("100", inner)


if __name__ == "__main__":
    unittest.main()
