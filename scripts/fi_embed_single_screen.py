#!/usr/bin/env python3
"""
Patch research/watchlists/SINGLE_SCREEN_REPORT.html with generated row fragments:
  _snapshot_table_rows.inc.html, _rubric_table_rows.inc.html, _universe_table_rows.inc.html

Run after scripts/refresh_watchlists.sh. Not investment advice.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
HTML = W / "SINGLE_SCREEN_REPORT.html"


def main() -> None:
    snap_rows = (W / "_snapshot_table_rows.inc.html").read_text(encoding="utf-8")
    rubric_rows = (W / "_rubric_table_rows.inc.html").read_text(encoding="utf-8")
    uni_rows = (W / "_universe_table_rows.inc.html").read_text(encoding="utf-8")
    md = (W / "rubric_universe.md").read_text(encoding="utf-8")
    m = re.search(r"Generated \(UTC\): `([^`]+)`", md)
    gen = m.group(1) if m else ""

    text = HTML.read_text(encoding="utf-8")

    text = re.sub(
        r"(<section id=\"snapshot\">[\s\S]*?<tbody>\s*)([\s\S]*?)(\s*</tbody>\s*\n\s*</table>)",
        r"\1" + snap_rows + r"\3",
        text,
        count=1,
    )

    text = re.sub(
        r'(<table[^>]*\bid="rubric-table"[^>]*>[\s\S]*?<tbody>\s*)([\s\S]*?)(\s*</tbody>\s*\n\s*</table>)',
        r"\1" + rubric_rows + r"\3",
        text,
        count=1,
    )

    text = text.replace(
        "A <strong>one-screen fact table</strong> for a handful of illustration tickers",
        "A <strong>one-screen fact table</strong> for all <strong>70</strong> sleeve illustration tickers from <code>universe_manifest.csv</code>",
    )
    if gen:
        text = re.sub(
            r"<p class=\"muted\">Generated [^<]+</p>\s*\n\s*<div class=\"scroll\">\s*\n\s*<table>\s*\n\s*<thead>\s*\n\s*<tr>\s*\n\s*<th>ticker</th>",
            f'<p class="muted">Generated {gen} (UTC). Same ticker set as <code>rubric_universe.csv</code>. Scroll horizontally on small screens.</p>\n      <div class="scroll">\n        <table>\n          <thead>\n            <tr>\n              <th>ticker</th>',
            text,
            count=1,
        )

    text = text.replace(
        "<p class=\"muted\">Machine-readable copies: <code>research/watchlists/_live_snapshot.csv</code> and <code>_live_snapshot.md</code>. Scaffold: <code>_live_scaffold.md</code>.</p>",
        '<p class="muted">Machine-readable copies: <code>research/watchlists/rubric_universe.csv</code> and <code>rubric_universe.md</code> (refresh with <code>scripts/refresh_watchlists.sh</code>). Legacy: <code>_live_snapshot.csv</code>. Scaffold: <code>_live_scaffold.md</code>.</p>',
    )

    universe_block = f"""    <section id="universe">
      <h2>Sleeve universe table (manifest order)</h2>
      <p class="section-purpose"><strong>What this tab is.</strong> The same <strong>70 tickers</strong> as the snapshot and rubric, with <strong>Future Impact sleeve theme</strong> and a one-line linkage from <code>universe_manifest.csv</code>. <strong>Purpose.</strong> Filter by theme while scanning fundamentals columns side by side.</p>
      <p class="rubric-controls muted">Show rows:
        <select id="universe-theme-filter" aria-label="Filter universe table by theme">
          <option value="all">All themes (70)</option>
          <option value="ai">AI infrastructure &amp; compute (10)</option>
          <option value="energy">Energy transition &amp; grids (10)</option>
          <option value="cyber">Cybersecurity &amp; digital trust (10)</option>
          <option value="auto">Industrial automation &amp; robotics (10)</option>
          <option value="health">Healthcare innovation &amp; AI in medicine (10)</option>
          <option value="fintech">Fintech &amp; digital money (10)</option>
          <option value="quantum">Quantum / frontier compute (10)</option>
        </select>
      </p>
      <p class="muted">Regenerate rows: <code>python scripts/fi_universe_html_rows.py --manifest research/watchlists/universe_manifest.csv --csv research/watchlists/rubric_universe.csv &gt; research/watchlists/_universe_table_rows.inc.html</code> then run <code>python scripts/fi_embed_single_screen.py</code>.</p>
      <div class="scroll">
        <table id="universe-table" class="universe">
          <thead>
            <tr>
              <th>Theme (sleeve)</th>
              <th>Ticker</th>
              <th>Name</th>
              <th>Linkage</th>
              <th>Exch</th>
              <th>Sector</th>
              <th>Mkt cap</th>
              <th>Trail P/E</th>
              <th>Fwd P/E</th>
              <th>Rev gr</th>
              <th>Last</th>
              <th>SEC</th>
            </tr>
          </thead>
          <tbody>
{uni_rows}
          </tbody>
        </table>
      </div>
    </section>

"""

    if '<section id="universe">' not in text:
        text = text.replace(
            '    </section>\n\n    <section id="map">',
            "    </section>\n\n" + universe_block + '    <section id="map">',
            1,
        )
        text = text.replace(
            '<a href="#snapshot"',
            '<a href="#snapshot"',
            1,
        )
        text = text.replace(
            '<a href="#snapshot" title="Indicative fundamentals table from yfinance">Snapshot</a>\n        <a href="#map"',
            '<a href="#snapshot" title="Indicative fundamentals table from yfinance">Snapshot</a>\n        <a href="#universe" title="70-name sleeve table with theme filter">Universe</a>\n        <a href="#map"',
            1,
        )

    text = text.replace(
        "<p class=\"muted\">Snapshot CSV for the same tickers: <code>research/watchlists/rubric_universe.csv</code> (regenerate with <code>fi_snapshot.py</code> using the project’s ticker list).</p>",
        "<p class=\"muted\">Rubric scores are edited in <code>research/watchlists/rubric_scores.csv</code>; HTML rows: <code>python scripts/fi_rubric_html_rows.py</code> then <code>python scripts/fi_embed_single_screen.py</code>. Market data: <code>fi_snapshot.py --manifest research/watchlists/universe_manifest.csv</code>.</p>",
    )

    # Extend bottom script for universe filter
    if "universe-theme-filter" not in text or "getElementById(\"universe-theme-filter\")" not in text:
        text = text.replace(
            "    })();\n  </script>\n</body>",
            """    })();
    (function () {
      var selU = document.getElementById("universe-theme-filter");
      var tableU = document.getElementById("universe-table");
      if (!selU || !tableU) return;
      selU.addEventListener("change", function () {
        var v = selU.value;
        tableU.querySelectorAll("tbody tr").forEach(function (tr) {
          if (v === "all" || tr.getAttribute("data-theme") === v) {
            tr.classList.remove("rubric-hidden");
          } else {
            tr.classList.add("rubric-hidden");
          }
        }        );
      });
    })();
  </script>
</body>""",
            1,
        )

    # Finnhub market context fragment (fi_finnhub_context.py for the current core list)
    sfrag_path = W / "finnhub_context_fragment.html"
    mark_s = "<!-- FI_MARKET_CONTEXT_EMBED_START -->"
    mark_e = "<!-- FI_MARKET_CONTEXT_EMBED_END -->"
    if sfrag_path.is_file():
        frag = sfrag_path.read_text(encoding="utf-8").strip()
        block = (
            f"{mark_s}\n"
            '<div class="pdf-screen-only monitor-sentiment-embed">\n'
            f"{frag}\n"
            f"</div>\n{mark_e}"
        )
        for legacy_s, legacy_e in (
            ("<!-- FI_SENTIMENT_EMBED_START -->", "<!-- FI_SENTIMENT_EMBED_END -->"),
        ):
            pat_legacy = re.compile(re.escape(legacy_s) + r"[\s\S]*?" + re.escape(legacy_e))
            if pat_legacy.search(text):
                text = pat_legacy.sub(block, text, count=1)
                break
        else:
            pat_s = re.compile(re.escape(mark_s) + r"[\s\S]*?" + re.escape(mark_e))
            if pat_s.search(text):
                text = pat_s.sub(block, text, count=1)
            else:
                needle = '<section id="monitor">\n      <h2>Monitor</h2>'
                if needle in text:
                    text = text.replace(needle, needle + "\n" + block + "\n", 1)

    HTML.write_text(text, encoding="utf-8")
    print(HTML.resolve())


if __name__ == "__main__":
    main()
