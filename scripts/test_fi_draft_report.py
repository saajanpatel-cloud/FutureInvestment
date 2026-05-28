#!/usr/bin/env python3
"""Tests for DRAFT Stock-Deep Dive helpers."""
from __future__ import annotations

import unittest

from fi_draft_common import load_draft_tickers
from fi_draft_price_zones import compute_price_zones
from fi_narrative import summarize_financial_history


class TestDraftPriceZones(unittest.TestCase):
    def test_nvda_zones_from_fixture(self):
        scen = {
            "price": "225.32",
            "bear_price": "192.85",
            "base_price": "353.28",
            "bull_price": "525.83",
        }
        mc = {"p10": "277.36", "p90": "408.00"}
        earn = {"analyst_target_low": "140.0", "analyst_target_high": "380.0"}
        z = compute_price_zones(scen=scen, mc=mc, earn=earn, dcf_rows=None)
        self.assertIsNotNone(z["buy_low"])
        self.assertIsNotNone(z["sell_high"])
        self.assertLessEqual(z["buy_low"], z["buy_high"])
        self.assertLessEqual(z["sell_low"], z["sell_high"])


class TestFinancialHistorySummary(unittest.TestCase):
    def test_summarize_empty(self):
        out = summarize_financial_history("NVDA", [])
        self.assertEqual(out["trend_label"], "unknown")

    def test_summarize_trend(self):
        rows = [
            {"ticker": "NVDA", "year": "2022", "revenue": "1e10", "net_income": "1e9", "roe_pct": "10"},
            {"ticker": "NVDA", "year": "2025", "revenue": "2e11", "net_income": "5e10", "roe_pct": "50"},
        ]
        out = summarize_financial_history("NVDA", rows)
        self.assertIn(out["trend_label"], ("strengthening", "weakening", "mixed"))


class TestDraftTickers(unittest.TestCase):
    def test_default_pilot(self):
        import os

        os.environ.pop("FI_DRAFT_TICKERS", None)
        self.assertEqual(load_draft_tickers(), ["NVDA"])


if __name__ == "__main__":
    unittest.main()
