#!/usr/bin/env python3
"""
Monitor runtime JS: shortlist picker (CORE_TICKER_ORDER), deep links.

Patches FI_DEEP_DIVE_RUNTIME block in SINGLE_SCREEN_REPORT.html.
Run after fi_embed_value_js.py. Not investment advice.
"""
from __future__ import annotations

import json
import re
import sys

from fi_embed_core import HTML, load_core_tickers
from fi_embed_shortlist_proposed import sort_tickers_by_theme_then_symbol

MAN = __import__("pathlib").Path(__file__).resolve().parents[1] / "research" / "watchlists" / "universe_manifest.csv"

MARK_S = "  /* FI_DEEP_DIVE_RUNTIME_START */"
MARK_E = "  /* FI_DEEP_DIVE_RUNTIME_END */"


def load_manifest_map() -> dict[str, dict[str, str]]:
    import csv

    out: dict[str, dict[str, str]] = {}
    if not MAN.is_file():
        return out
    with MAN.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = (r.get("ticker") or "").strip().upper()
            if t:
                out[t] = r
    return out


def core_ticker_order_js() -> str:
    man = load_manifest_map()
    core = sort_tickers_by_theme_then_symbol(load_core_tickers(), man)
    inner = ",".join(json.dumps(t) for t in core)
    return f"  var CORE_TICKER_ORDER = [{inner}];\n\n"


PICKER = r"""
  var ddSel = document.getElementById("dd-ticker");
  var ddPrev = document.getElementById("dd-prev");
  var ddNext = document.getElementById("dd-next");
  if (!ddSel) return;
  ddSel.innerHTML = "";
  var ph = document.createElement("option");
  ph.value = "";
  ph.textContent = "Select a stock…";
  ddSel.appendChild(ph);
  var tickerList = (typeof CORE_TICKER_ORDER !== "undefined" && CORE_TICKER_ORDER.length)
    ? CORE_TICKER_ORDER.slice()
    : Object.keys(META || {}).sort();
  tickerList.forEach(function (t) {
    var meta = (META && META[t]) ? META[t] : null;
    if (!meta) return;
    var o = document.createElement("option");
    o.value = t;
    o.textContent = t + " — " + (meta.name || t);
    ddSel.appendChild(o);
  });
  function pickAt(i) {
    if (i < 0 || i >= tickerList.length) return;
    ddSel.value = tickerList[i];
    ddSel.dispatchEvent(new Event("change"));
  }
  if (ddPrev) ddPrev.addEventListener("click", function () {
    var i = tickerList.indexOf(ddSel.value);
    pickAt(i <= 0 ? tickerList.length - 1 : i - 1);
  });
  if (ddNext) ddNext.addEventListener("click", function () {
    var i = tickerList.indexOf(ddSel.value);
    pickAt(i < 0 || i >= tickerList.length - 1 ? 0 : i + 1);
  });
  function routeFromHash() {
    var h = (location.hash || "").replace(/^#/, "");
    if (h.indexOf("monitor-") === 0) openDeepDive(h.slice(8));
  }
  ddSel.addEventListener("change", function () {
    var ticker = ddSel.value;
    var container = document.getElementById("dd-content");
    if (!ticker) { if (container) container.innerHTML = ""; return; }
    if (typeof CORE_TICKERS !== "undefined" && CORE_TICKERS.size && !CORE_TICKERS.has(ticker))
      renderMonitorStub(ticker, container);
    else renderDeepDive(ticker, container);
    location.hash = "monitor-" + ticker;
  });
  window.addEventListener("hashchange", routeFromHash);
  routeFromHash();
"""

PICKER_END = re.compile(
    r"  routeFromHash\(\);\n",
    re.MULTILINE,
)


def main() -> None:
    doc = HTML.read_text(encoding="utf-8")
    if MARK_S not in doc or MARK_E not in doc:
        print("FI_DEEP_DIVE_RUNTIME markers missing", file=sys.stderr)
        sys.exit(2)

    i = doc.index(MARK_S)
    j = doc.index(MARK_E)
    block = doc[i + len(MARK_S) : j]

    # Drop old picker (ddSel through routeFromHash) and CORE_TICKER_ORDER if present
    block = re.sub(r"\n  var CORE_TICKER_ORDER = \[[\s\S]*?\];\n\n?", "\n", block, count=1)
    picker_end = block.find("  function esc(s)")
    if picker_end < 0:
        picker_end = block.find("  /* ── Helper: format number")
    if picker_end < 0:
        print("Could not find end of picker in runtime block", file=sys.stderr)
        sys.exit(2)
    tail = block[picker_end:]
    new_block = core_ticker_order_js() + PICKER + tail
    doc = doc[: i + len(MARK_S)] + "\n" + new_block + doc[j:]
    HTML.write_text(doc, encoding="utf-8")
    print("Patched Monitor picker → core shortlist order")


if __name__ == "__main__":
    main()
