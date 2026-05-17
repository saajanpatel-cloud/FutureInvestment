#!/usr/bin/env python3
"""Unit tests for fi_yahoo (no network)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fi_yahoo import YahooPingResult, ping, safe_info_get


class TestFiYahoo(unittest.TestCase):
    def test_safe_info_get(self):
        self.assertEqual(safe_info_get(None, "x", 1), 1)
        self.assertEqual(safe_info_get({"a": 2}, "a"), 2)
        self.assertEqual(safe_info_get({"a": None}, "a", 9), 9)

    @patch("fi_yahoo.last_price", return_value=(100.5, "USD"))
    @patch("fi_yahoo.require_yfinance")
    def test_ping_ok(self, mock_req, _mock_price):
        mock_req.return_value = MagicMock(__version__="9.9.9")
        r = ping("SPY")
        self.assertTrue(r.ok)
        self.assertEqual(r.last_price, 100.5)

    @patch("fi_yahoo.last_price", return_value=(None, None))
    @patch("fi_yahoo.require_yfinance")
    def test_ping_fail(self, mock_req, _mock_price):
        mock_req.return_value = MagicMock(__version__="9.9.9")
        r = ping("BAD")
        self.assertFalse(r.ok)
        self.assertIsInstance(r, YahooPingResult)


if __name__ == "__main__":
    unittest.main()
