#!/usr/bin/env python3
"""
Ensure stock deep-dive copy references the live core shortlist.

fi_embed_value_js.py rebuilds the dropdown; this script only patches intro copy if needed.

Not investment advice.
"""
from __future__ import annotations

from fi_embed_core import HTML, load_core_tickers


def main() -> None:
    n = len(load_core_tickers())
    doc = HTML.read_text(encoding="utf-8")
    needle = "report_core_tickers.txt</code>) — refreshed on each full watchlist refresh."
    if needle not in doc:
        doc = doc.replace(
            "cached illustration set</strong>",
            f"live Decide shortlist ({n} names)</strong>",
            1,
        )
    HTML.write_text(doc, encoding="utf-8")
    print(f"Deep-dive intro OK ({n} core tickers)")


if __name__ == "__main__":
    main()
