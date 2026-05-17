#!/usr/bin/env python3
from __future__ import annotations

import unittest

from fi_manifest import manifest_sort_key, sort_manifest_rows


class TestManifestSort(unittest.TestCase):
    def test_company_then_theme(self):
        rows = [
            {"ticker": "Z", "theme_label": "AI infra", "theme_slug": "ai"},
            {"ticker": "A", "theme_label": "Fintech & digital money", "theme_slug": "fintech"},
            {"ticker": "B", "theme_label": "AI infra", "theme_slug": "ai"},
        ]
        names = {"Z": "Acme Corp", "A": "Acme Corp", "B": "Beta Inc"}
        out = sort_manifest_rows(rows, name_by_ticker=names)
        self.assertEqual([r["ticker"] for r in out], ["Z", "A", "B"])
        keys = [manifest_sort_key(r, names) for r in out]
        self.assertEqual(keys, sorted(keys))


if __name__ == "__main__":
    unittest.main()
