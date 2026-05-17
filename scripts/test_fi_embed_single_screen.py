#!/usr/bin/env python3
"""Tests for dynamic count labels in fi_embed_single_screen."""
from __future__ import annotations

import unittest

from fi_embed_single_screen import (
    build_theme_filter_options,
    load_manifest_stats,
    sync_count_labels,
)


class TestFiEmbedSingleScreen(unittest.TestCase):
    def test_build_theme_filter_includes_fintech(self):
        by = {"ai": 10, "fintech": 5, "quantum": 3}
        opts = build_theme_filter_options(by, 18)
        self.assertIn("All themes (18)", opts)
        self.assertIn('value="fintech"', opts)
        self.assertIn("Fintech (5)", opts)

    def test_sync_count_labels(self):
        stats = {"uni_n": 481, "model_n": 350, "n_themes": 7, "by_slug": {}}
        out = sync_count_labels(
            "<strong>316 companies</strong> across 6 themes. The <strong>26</strong> core names.",
            stats,
            25,
        )
        self.assertIn("481 companies", out)
        self.assertIn("7 themes", out)
        self.assertIn("<strong>25</strong> core", out)
        self.assertNotIn("316 companies", out)


if __name__ == "__main__":
    unittest.main()
