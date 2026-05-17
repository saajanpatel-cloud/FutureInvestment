#!/usr/bin/env python3
"""Tests for fi_adversarial pack logic."""
from __future__ import annotations

import unittest

from fi_adversarial import (
    QUANTUM_COMPUTE_PURE,
    filter_pool_rejects,
    heuristic_pack,
    is_seat_blocked,
    normalize_pack,
    pack_complete,
    shortlist_gate,
)


class TestFiAdversarial(unittest.TestCase):
    def test_klic_reject_seat(self):
        rub = {
            "growth": "4",
            "margins": "5",
            "balance_sheet": "4",
            "durability": "4",
            "tail_risks": "3",
            "valuation": "3",
        }
        man = {"theme_slug": "quantum", "linkage_one_liner": "Wire bond packaging equipment"}
        pack = heuristic_pack("KLIC", rub, man, {})
        self.assertEqual(pack["shortlist_gate"], "reject_seat")
        self.assertFalse(pack["quantum_pure"])

    def test_ionq_pure_pass(self):
        rub = {
            "growth": "5",
            "margins": "1",
            "balance_sheet": "4",
            "durability": "3",
            "tail_risks": "1",
            "valuation": "1",
        }
        man = {"theme_slug": "quantum", "linkage_one_liner": "Trapped-ion quantum hardware"}
        pack = heuristic_pack("IONQ", rub, man, {})
        self.assertIn(pack["shortlist_gate"], ("pass", "watch"))
        self.assertTrue(pack["quantum_pure"])
        self.assertIn("IONQ", QUANTUM_COMPUTE_PURE)

    def test_filter_pool_rejects(self):
        packs = {
            "BAD": {"workflow_e_complete": True, "shortlist_gate": "reject"},
            "GOOD": {"workflow_e_complete": True, "shortlist_gate": "pass"},
        }
        kept, dropped = filter_pool_rejects(["GOOD", "BAD", "NONE"], packs)
        self.assertEqual(kept, ["GOOD", "NONE"])
        self.assertEqual(dropped, ["BAD"])

    def test_normalize_pack(self):
        raw = {
            "shortlist_gate": "pass",
            "verdict": "pass",
            "bear_bullets": ["a", "b", "c", "d"],
            "premortem": "test",
            "kill_criteria": ["k1"],
        }
        p = normalize_pack(raw, "NVDA")
        self.assertTrue(pack_complete(p))
        self.assertEqual(shortlist_gate({"NVDA": p}, "NVDA"), "pass")

    def test_seat_blocked(self):
        packs = {"X": {"workflow_e_complete": True, "shortlist_gate": "reject_seat"}}
        self.assertTrue(is_seat_blocked(packs, "X"))


if __name__ == "__main__":
    unittest.main()
