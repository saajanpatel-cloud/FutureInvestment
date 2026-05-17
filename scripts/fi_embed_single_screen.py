#!/usr/bin/env python3
"""
Patch research/watchlists/SINGLE_SCREEN_REPORT.html with generated row fragments:
  _snapshot_table_rows.inc.html, _rubric_table_rows.inc.html, _universe_table_rows.inc.html

Run after scripts/refresh_watchlists.sh. Not investment advice.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "research" / "watchlists"
HTML = W / "SINGLE_SCREEN_REPORT.html"
MAN = W / "universe_manifest.csv"
CORE_TXT = W / "report_core_tickers.txt"

# Manifest filter order (matches rubric data-theme values)
THEME_SLUG_ORDER: tuple[str, ...] = (
    "ai",
    "energy",
    "cyber",
    "auto",
    "health",
    "fintech",
    "quantum",
)

# Short labels for <select> options (screen UI)
THEME_FILTER_SHORT: dict[str, str] = {
    "ai": "AI infra",
    "energy": "Energy / grids",
    "cyber": "Cyber",
    "auto": "Automation",
    "health": "Health Tech",
    "fintech": "Fintech",
    "quantum": "Quantum",
}


def load_manifest_stats(man_path: Path) -> dict:
    from collections import Counter

    by_slug: Counter[str] = Counter()
    n_model = 0
    if not man_path.is_file():
        return {
            "uni_n": 0,
            "model_n": 0,
            "by_slug": {},
            "n_themes": 0,
        }
    with man_path.open(encoding="utf-8", newline="") as mf:
        for row in csv.DictReader(mf):
            slug = (row.get("theme_slug") or "").strip()
            if slug:
                by_slug[slug] += 1
            if (row.get("model_tier") or "full").strip().lower() == "full":
                n_model += 1
    return {
        "uni_n": sum(by_slug.values()),
        "model_n": n_model,
        "by_slug": dict(by_slug),
        "n_themes": len(by_slug),
    }


def load_core_n(path: Path) -> int:
    if not path.is_file():
        return 0
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            n += 1
    return n


def build_theme_filter_options(by_slug: dict[str, int], total: int) -> str:
    import html as html_mod

    lines = [f'<option value="all">All themes ({total})</option>']
    for slug in THEME_SLUG_ORDER:
        cnt = by_slug.get(slug, 0)
        if cnt <= 0:
            continue
        lbl = html_mod.escape(THEME_FILTER_SHORT.get(slug, slug))
        lines.append(f'<option value="{slug}">{lbl} ({cnt})</option>')
    return "\n          ".join(lines)


def patch_theme_filter_select(text: str, select_id: str, options_inner: str) -> str:
    pat = re.compile(
        rf'(<select\s+id="{re.escape(select_id)}"[^>]*>)\s*[\s\S]*?\s*(</select>)',
        re.IGNORECASE,
    )
    m = pat.search(text)
    if not m:
        return text
    return text[: m.start()] + f"{m.group(1)}\n          {options_inner}\n        {m.group(2)}" + text[m.end() :]


def sync_count_labels(text: str, stats: dict, core_n: int) -> str:
    """Replace stale hard-coded universe / shortlist counts in report prose and controls."""
    u = str(stats["uni_n"])
    m = str(stats["model_n"])
    t = str(stats["n_themes"])
    c = str(core_n) if core_n else "core"

    text = re.sub(r"All themes \(\d+\)", f"All themes ({u})", text)
    text = re.sub(
        r"<strong>\d{2,3} companies</strong>",
        f"<strong>{u} companies</strong>",
        text,
    )
    text = re.sub(
        r"<strong>\d{2,3} names across \d+ themes</strong>",
        f"<strong>{u} names across {t} themes</strong>",
        text,
    )
    text = re.sub(
        r"<strong>\d{2,3}-name</strong>",
        f"<strong>{u}-name</strong>",
        text,
    )
    text = re.sub(r"across 6 themes", f"across {t} themes", text)
    text = re.sub(r"across six themes", f"across {t} themes", text, flags=re.IGNORECASE)
    text = re.sub(
        r"across six structural themes",
        f"across {t} structural themes",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"six structural themes", f"{t} structural themes", text, flags=re.IGNORECASE)
    text = re.sub(r"full six-theme universe", f"full {t}-theme universe", text, flags=re.IGNORECASE)
    text = re.sub(r"all six themes", f"all {t} themes", text, flags=re.IGNORECASE)
    text = re.sub(r"entire six-theme universe", f"entire {t}-theme universe", text, flags=re.IGNORECASE)
    text = re.sub(
        r"The <strong>\d{1,2}</strong> core names",
        f"The <strong>{c}</strong> core names",
        text,
    )
    text = re.sub(
        r"The <strong>\d{1,2}</strong> Decide names",
        f"The <strong>{c}</strong> Decide names",
        text,
    )
    text = re.sub(r"\(\d{1,2} names\)", f"({c} names)", text)
    text = re.sub(r"Same \d{1,2} names as", f"Same {c} names as", text)
    text = re.sub(
        r"<strong>\d{2,3}</strong> tickers",
        f"<strong>{u}</strong> tickers",
        text,
    )
    text = re.sub(
        r"<strong>\d{2,3} fully modelled</strong>",
        f"<strong>{m} fully modelled</strong>",
        text,
        count=1,
    )
    text = re.sub(r"\d{2,3} fully modelled", f"{m} fully modelled", text)
    text = re.sub(r"~\d{2,3} modelled", f"~{m} modelled", text)
    text = re.sub(r"~\d{2,3} screen", f"~{u} screen", text)
    return text


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

    stats = load_manifest_stats(MAN)
    core_n = load_core_n(CORE_TXT)
    uni_n = stats["uni_n"]
    model_n = stats["model_n"]
    uni_s = str(uni_n) if uni_n else "universe"
    model_s = str(model_n) if model_n else uni_s

    filter_opts = build_theme_filter_options(stats["by_slug"], uni_n)
    text = patch_theme_filter_select(text, "rubric-theme-filter", filter_opts)
    text = patch_theme_filter_select(text, "universe-theme-filter", filter_opts)

    text = sync_count_labels(text, stats, core_n)
    text = text.replace(
        "A <strong>one-screen fact table</strong> for a handful of illustration tickers",
        f"A <strong>one-screen fact table</strong> for all <strong>{uni_s}</strong> sleeve tickers from <code>universe_manifest.csv</code>",
    )
    if gen:
        text = re.sub(
            r"<p class=\"muted\">Generated [^<]+</p>\s*\n\s*<motion class=\"scroll\">".replace("motion", "div"),
            f'<p class="muted">Generated {gen} (UTC). Same ticker set as <code>rubric_universe.csv</code>. Scroll horizontally on small screens.</p>\n      <motion class="scroll">'.replace("motion", "motion"),
            text,
            count=1,
        )

    text = text.replace(
        "<p class=\"muted\">Machine-readable copies: <code>research/watchlists/_live_snapshot.csv</code> and <code>_live_snapshot.md</code>. Scaffold: <code>_live_scaffold.md</code>.</p>",
        '<p class="muted">Machine-readable copies: <code>research/watchlists/rubric_universe.csv</code> and <code>rubric_universe.md</code> (refresh with <code>scripts/refresh_watchlists.sh</code>). Legacy: <code>_live_snapshot.csv</code>. Scaffold: <code>_live_scaffold.md</code>.</p>',
    )

    universe_block = f"""    <section id="universe">
      <h2>Sleeve universe table (manifest order)</h2>
      <p class="section-purpose"><strong>What this tab is.</strong> The same <strong>{uni_s} tickers</strong> as the snapshot and rubric, with <strong>Future Impact sleeve theme</strong> and a one-line linkage from <code>universe_manifest.csv</code>. <strong>Purpose.</strong> Filter by theme while scanning fundamentals columns side by side.</p>
      <p class="rubric-controls muted">Show rows:
        <select id="universe-theme-filter" aria-label="Filter universe table by theme">
          {filter_opts}
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
      </motion>
    </section>

""".replace("<motion", "<div").replace("</motion>", "</div>")

    if '<section id="universe">' not in text:
        text = text.replace(
            '    </section>\n\n    <section id="map">',
            "    </section>\n\n" + universe_block + '    <section id="map">',
            1,
        )
        text = text.replace(
            '<a href="#snapshot" title="Indicative fundamentals table from yfinance">Snapshot</a>\n        <a href="#map"',
            '<a href="#snapshot" title="Indicative fundamentals table from yfinance">Snapshot</a>\n        <a href="#universe" title="Sleeve table with theme filter">Universe</a>\n        <a href="#map"',
            1,
        )

    text = text.replace(
        "<p class=\"muted\">Snapshot CSV for the same tickers: <code>research/watchlists/rubric_universe.csv</code> (regenerate with <code>fi_snapshot.py</code> using the project’s ticker list).</p>",
        "<p class=\"muted\">Rubric scores are edited in <code>research/watchlists/rubric_scores.csv</code>; HTML rows: <code>python scripts/fi_rubric_html_rows.py</code> then <code>python scripts/fi_embed_single_screen.py</code>. Market data: <code>fi_snapshot.py --manifest research/watchlists/universe_manifest.csv</code>.</p>",
    )

    extra_scripts = ""
    if "restoreManifestTableOrder" not in text:
        extra_scripts += """
    (function () {
      function restoreManifestTableOrder(tableId) {
        var table = document.getElementById(tableId);
        if (!table) return;
        var tbody = table.querySelector("tbody");
        if (!tbody) return;
        var rows = Array.from(tbody.querySelectorAll("tr"));
        rows.sort(function (a, b) {
          var ai = parseInt(a.getAttribute("data-sort-index") || "99999", 10);
          var bi = parseInt(b.getAttribute("data-sort-index") || "99999", 10);
          return ai - bi;
        });
        rows.forEach(function (row) { tbody.appendChild(row); });
      }
      restoreManifestTableOrder("rubric-table");
      restoreManifestTableOrder("universe-table");
    })();
"""
    if "universe-theme-filter" not in text or 'getElementById("universe-theme-filter")' not in text:
        extra_scripts += """
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
        });
      });
    })();
"""
    if extra_scripts:
        text = text.replace(
            "    })();\n  </script>\n</body>",
            "    })();" + extra_scripts + "\n  </script>\n</body>",
            1,
        )

    for mark_s, mark_e in (
        ("<!-- FI_MARKET_CONTEXT_EMBED_START -->", "<!-- FI_MARKET_CONTEXT_EMBED_END -->"),
        ("<!-- FI_SENTIMENT_EMBED_START -->", "<!-- FI_SENTIMENT_EMBED_END -->"),
    ):
        pat = re.compile(re.escape(mark_s) + r"[\s\S]*?" + re.escape(mark_e))
        text = pat.sub("", text, count=1)

    HTML.write_text(text, encoding="utf-8")
    print(
        f"Patched {HTML.name}: universe={uni_n} modelled={model_n} themes={stats['n_themes']} core={core_n}",
        file=sys.stderr,
    )
    print(HTML.resolve())


if __name__ == "__main__":
    main()
