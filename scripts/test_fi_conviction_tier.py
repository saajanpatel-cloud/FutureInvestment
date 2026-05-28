#!/usr/bin/env python3
from __future__ import annotations

import unittest

from fi_conviction_tier import assign_conviction_tiers, conviction_tier_from_position


class TestConvictionTier(unittest.TestCase):
    def test_quartile_positions_25(self):
        n = 25
        tiers = [conviction_tier_from_position(i, n) for i in range(n)]
        self.assertEqual(tiers[0], 1)
        self.assertEqual(tiers[6], 1)
        self.assertEqual(tiers[7], 2)
        self.assertEqual(tiers[13], 3)
        self.assertEqual(tiers[19], 4)
        self.assertEqual(tiers[24], 4)

    def test_assign_ranks(self):
        composite = {
            "A": {"composite_rank": "10", "composite_score": "80"},
            "B": {"composite_rank": "5", "composite_score": "90"},
            "C": {"composite_rank": "20", "composite_score": "70"},
            "D": {"composite_rank": "1", "composite_score": "95"},
        }
        meta = assign_conviction_tiers(["A", "B", "C", "D"], composite)
        self.assertEqual(meta["D"]["conviction_tier"], 1)
        self.assertEqual(meta["B"]["conviction_tier"], 2)
        self.assertEqual(meta["A"]["conviction_tier"], 3)
        self.assertEqual(meta["C"]["conviction_tier"], 4)


if __name__ == "__main__":
    unittest.main()
