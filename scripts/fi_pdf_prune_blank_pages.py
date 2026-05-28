#!/usr/bin/env python3
"""Prune truly blank pages from generated PDF."""
from __future__ import annotations

import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def content_len(page) -> int:
    c = page.get("/Contents")
    if not c:
        return 0
    try:
        if isinstance(c, list):
            return sum(len(x.get_data()) for x in c)
        return len(c.get_data())
    except Exception:
        return 999999


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: fi_pdf_prune_blank_pages.py <pdf>", file=sys.stderr)
        return 2
    pdf = Path(sys.argv[1])
    if not pdf.is_file():
        print(f"Missing PDF: {pdf}", file=sys.stderr)
        return 2

    src = PdfReader(str(pdf))
    out = PdfWriter()
    dropped: list[int] = []
    for i, page in enumerate(src.pages, 1):
        txt = (page.extract_text() or "").strip()
        clen = content_len(page)
        # Conservative: drop only pages with no text and tiny stream.
        if not txt and clen <= 300:
            dropped.append(i)
            continue
        out.add_page(page)

    if dropped:
        tmp = pdf.with_suffix(".tmp.pdf")
        with tmp.open("wb") as f:
            out.write(f)
        tmp.replace(pdf)
        print(f"Pruned blank pages {dropped} → {pdf}", file=sys.stderr)
    else:
        print(f"No blank pages pruned → {pdf}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
