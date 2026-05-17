#!/usr/bin/env python3
"""Tests for fi_refresh_signals rule triggers."""
from __future__ import annotations

import unittest

from fi_refresh_signals import compute_refresh_signals


class TestFiRefreshSignals(unittest.TestCase):
    def test_baseline_empty(self):
        out = compute_refresh_signals(
            "NVDA",
            prior={},
            rub={},
            fh={},
            scen={},
            mc={},
            earn={},
            comp={},
            delta={},
            baseline=True,
        )
        self.assertEqual(out["bullish"], [])
        self.assertEqual(out["bearish"], [])

    def test_analyst_skew_improved(self):
        out = compute_refresh_signals(
            "X",
            prior={"analyst_skew": "sell-heavy"},
            rub={},
            fh={"analyst_skew": "buy-heavy"},
            scen={},
            mc={},
            earn={},
            comp={},
            delta={},
            baseline=False,
        )
        labels = [x["label"] for x in out["bullish"]]
        self.assertTrue(any("Analyst" in lb for lb in labels))

    def test_rubric_weakened(self):
        out = compute_refresh_signals(
            "X",
            prior={"rubric_total": "18"},
            rub={"growth": "3", "margins": "3", "balance_sheet": "3", "durability": "3", "valuation": "3", "tail_risks": "2"},
            fh={},
            scen={},
            mc={},
            earn={},
            comp={},
            delta={},
            baseline=False,
        )
        self.assertTrue(any("Scorecard" in x["label"] for x in out["bearish"]))


if __name__ == "__main__":
    unittest.main()
