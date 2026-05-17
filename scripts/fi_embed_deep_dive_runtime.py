#!/usr/bin/env python3
"""
Monitor runtime JS: core-shortlist picker, NARRATIVE sections, charts, deep links.

Patches SINGLE_SCREEN_REPORT.html after fi_embed_value_js.py.
Not investment advice.
"""
from __future__ import annotations

import html as html_module
import json
import re
import sys

from fi_embed_core import HTML, load_core_tickers_display_order, load_manifest_map
from fi_embed_shortlist_proposed import load_short_names

MARK_S = "  /* FI_DEEP_DIVE_RUNTIME_START */"
MARK_E = "  /* FI_DEEP_DIVE_RUNTIME_END */"

HELPERS = r"""
  function esc(s) {
    if (!s) return "";
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }
  function paras(text) {
    if (!text || text === "—") return '<p class="muted">—</p>';
    var parts = String(text).split(" · ");
    if (parts.length <= 1) return "<p>" + esc(text) + "</p>";
    return parts.map(function (p) { return "<p>" + esc(p.trim()) + "</p>"; }).join("");
  }
  function signalList(items, cls) {
    if (!items || !items.length) return '<p class="muted">None flagged.</p>';
    return "<ul class=\"" + cls + "\">" + items.map(function (it) {
      return "<li><strong>" + esc(it.label) + "</strong> — " + esc(it.detail) + "</li>";
    }).join("") + "</ul>";
  }
  function renderMonitorStub(ticker, el) {
    el.innerHTML = '<p class="muted"><strong>' + esc(ticker) + '</strong> is outside the core shortlist — pick a core name for the full brief.</p>';
  }
  window.openDeepDive = function (ticker) {
    var ddSel = document.getElementById("dd-ticker");
    if (!ddSel) return;
    ddSel.value = ticker;
    ddSel.dispatchEvent(new Event("change"));
    var sec = document.getElementById("monitor");
    if (sec) sec.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a.dd-jump");
    if (!a) return;
    e.preventDefault();
    var t = a.getAttribute("data-ticker");
    if (t) openDeepDive(t);
  });
  window.loadDdChart = function () {
    var container = document.getElementById("dd-tv-chart-container");
    var ddSel = document.getElementById("dd-ticker");
    if (!container || !ddSel || !ddSel.value) return;
    var sym = (typeof TV_MAP !== "undefined" && TV_MAP[ddSel.value]) || ("NASDAQ:" + ddSel.value);
    container.innerHTML = "";
    var isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    var widgetDiv = document.createElement("div");
    widgetDiv.className = "tradingview-widget-container";
    widgetDiv.style.cssText = "height:100%;width:100%";
    var innerDiv = document.createElement("motion");
    innerDiv.className = "tradingview-widget-container__widget";
    innerDiv.style.cssText = "height:100%;width:100%";
    widgetDiv.appendChild(innerDiv);
    var script = document.createElement("script");
    script.type = "text/javascript";
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.async = true;
    script.textContent = JSON.stringify({
      autosize: true, symbol: sym, interval: "D", timezone: "Europe/London",
      theme: isDark ? "dark" : "light", style: "1", locale: "en",
      hide_top_toolbar: false, hide_legend: false, allow_symbol_change: false,
      save_image: false, calendar: false, support_host: "https://www.tradingview.com"
    });
    widgetDiv.appendChild(script);
    container.appendChild(widgetDiv);
  };
""".replace('createElement("motion")', 'createElement("div")')

NARRATIVE_TAIL = r"""
    html += '<div class="dd-narrative">';
    html += '<div class="dd-narrative-head"><h3 class="dd-section-title">Executive report</h3>';
    html += '<button type="button" class="dd-print-btn screen-only-dd-print" onclick="document.body.classList.add(\'dd-print-one-ticker\');window.print();document.body.classList.remove(\'dd-print-one-ticker\');">Print this brief</button></div>';
    var sections = [
      ["Executive summary", nar.executive_summary],
      ["What this company is", nar.what_company],
      ["Key products & revenue drivers", nar.key_products],
      ["Key strategic plays", nar.strategic_plays],
      ["How it links to the theme", nar.theme_linkage],
      ["Demand outlook", nar.demand_outlook],
      ["Largest holders & ownership", nar.holders],
      ["Market context", nar.market_context],
      ["Bull case", nar.bull_case],
      ["Bear case", nar.bear_case],
      ["Signals this refresh", null],
      ["What to watch", nar.watch],
      ["Key risks & kill criteria", nar.kill],
      ["Model reference zones (not advice)", nar.model_zones],
      ["Links & filings", nar.links]
    ];
    sections.forEach(function (pair) {
      var title = pair[0], body = pair[1];
      html += '<div class="dd-narrative-section"><h4>' + esc(title) + '</h4>';
      if (title.indexOf("Signals") >= 0) {
        html += '<p class="dd-signals-intro">' + esc(nar.signals_intro || "") + '</p>';
        html += '<h5 class="dd-signals-sub">Improving this refresh</h5>' + signalList(sig.bullish, "dd-signals-bull");
        html += '<h5 class="dd-signals-sub">Worsening this refresh</h5>' + signalList(sig.bearish, "dd-signals-bear");
      } else {
        html += paras(body);
      }
      html += '</div>';
    });
    html += '</div>';
    if (typeof PEERS_BY_THEME !== "undefined" && m.theme_slug && PEERS_BY_THEME[m.theme_slug]) {
      html += '<div class="dd-section-title">Peers on this shortlist</div>';
      html += '<table class="dd-peer-table print-table-rubric"><thead><tr><th>Ticker</th><th>Rubric</th><th>Wtd upside</th><th>Deep dive</th></tr></thead><tbody>';
      PEERS_BY_THEME[m.theme_slug].forEach(function (row) {
        var hl = row.ticker === ticker ? ' class="dd-peer-current"' : "";
        html += "<tr" + hl + "><td><strong>" + esc(row.ticker) + "</strong></td><td>" + esc(row.rubric) + "</td><td>" + esc(row.wt) + "</td><td>";
        if (row.ticker !== ticker) html += '<a href="#" class="dd-jump" data-ticker="' + esc(row.ticker) + '">Open</a>';
        else html += "—";
        html += "</td></tr>";
      });
      html += "</tbody></table>";
    }
    var fh = (typeof FINNHUB_BY_TICKER !== "undefined" && FINNHUB_BY_TICKER[ticker]) ? FINNHUB_BY_TICKER[ticker] : null;
    if (fh) {
      html += '<div class="dd-section-title">Finnhub context</div>';
      html += '<p class="dd-finnhub-line">' + esc(fh.context_line || "") + '</p>';
      html += '<p class="dd-finnhub-meta muted">Analyst skew: ' + esc(fh.analyst_skew) + ' · Insider MSPR: ' + esc(fh.insider_mspr) + ' · News (7d): ' + esc(fh.news_7d) + ' · Next earnings: ' + esc(fh.next_earnings) + '</p>';
      if (fh.articles && fh.articles.length) {
        html += '<div class="dd-news-table-wrap"><table class="dd-news-table"><thead><tr><th>Date</th><th>Headline</th><th>Source</th></tr></thead><tbody>';
        fh.articles.slice(0, 8).forEach(function (a) {
          var dt = (a.datetime || a.published || "").slice(0, 10);
          var head = a.headline || a.title || "—";
          var src = a.source || "—";
          var url = a.url || a.link || "";
          html += "<tr><td>" + esc(dt) + "</td><td>";
          if (url) html += '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(head) + "</a>";
          else html += esc(head);
          html += "</td><td>" + esc(src) + "</td></tr>";
        });
        html += "</tbody></table></div>";
      }
    }
    html += '<div class="dd-section-title">Adversarial summary</div>';
    html += '<div class="adv-cards">';
    html += '<div class="adv-card"><div class="adv-title" style="color:#34d399;">Bull case</div><div class="adv-body">' + esc(adv.bull) + '</div></div>';
    html += '<div class="adv-card"><div class="adv-title" style="color:#f87171;">Bear case</div><motion class="adv-body">' + esc(adv.bear) + '</div></div>';
    html += '<div class="adv-card"><div class="adv-title" style="color:var(--warn);">Kill criteria</div><div class="adv-body">' + esc(adv.kill) + '</div></div>';
    html += '</motion>';
""".replace("<motion", "<div").replace("</motion>", "</div>")


def display_names_for(tickers: list[str], man: dict[str, dict[str, str]]) -> dict[str, str]:
    short = load_short_names()
    names: dict[str, str] = {}
    for t in tickers:
        row = man.get(t, {})
        label = (
            short.get(t)
            or row.get("name")
            or (row.get("linkage_one_liner") or "").split("—")[0].strip()
            or t
        )
        names[t] = str(label).strip()[:48]
    return names


def patch_dd_select_html(doc: str, tickers: list[str], names: dict[str, str]) -> str:
    """Server-rendered options so the dropdown matches the shortlist before JS runs."""
    lines = ['          <option value="">Select a stock…</option>\n']
    for t in tickers:
        nm = html_module.escape(names.get(t, t))
        lines.append(
            f'          <option value="{html_module.escape(t)}">'
            f"{html_module.escape(t)} — {nm}</option>\n"
        )
    inner = "".join(lines)
    pat = re.compile(
        r'(<select id="dd-ticker">\s*\n)([\s\S]*?)(\n\s*</select>)',
        re.IGNORECASE,
    )
    m = pat.search(doc)
    if not m:
        return doc
    return doc[: m.start()] + m.group(1) + inner + m.group(3) + doc[m.end() :]


def core_ticker_order_js(tickers: list[str]) -> str:
    inner = ",".join(json.dumps(t) for t in tickers)
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
    : [];
  if (!tickerList.length && typeof CORE_TICKERS !== "undefined" && CORE_TICKERS.size) {
    tickerList = Array.from(CORE_TICKERS).sort();
  }
  if (typeof CORE_TICKERS !== "undefined" && CORE_TICKERS.size) {
    tickerList = tickerList.filter(function (t) { return CORE_TICKERS.has(t); });
  }
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


def patch_render(render: str) -> str:
    render = render.replace(
        "adv = ADV[ticker], rub = RUBRIC[ticker];",
        "adv = ADV[ticker], rub = RUBRIC[ticker];\n"
        "    var nar = (typeof NARRATIVE !== \"undefined\" && NARRATIVE[ticker]) ? NARRATIVE[ticker] : {};\n"
        "    var sig = (typeof REFRESH_SIGNALS !== \"undefined\" && REFRESH_SIGNALS[ticker]) "
        "? REFRESH_SIGNALS[ticker] : { bullish: [], bearish: [] };\n"
        "    var fresh = (typeof FRESHNESS !== \"undefined\" && FRESHNESS[ticker]) ? FRESHNESS[ticker] : {};",
    )
    render = render.replace("rub[6] + '/30'", "rub[6] + '/24'")
    render = render.replace(
        "    html += '<span class=\"dd-ticker\">' + ticker + '</span>';",
        "    html += '<span class=\"dd-ticker\">' + esc(ticker) + '</span>';",
    )
    render = render.replace(
        "    html += '<span class=\"dd-name\">' + m.name + '</span>';",
        "    html += '<span class=\"dd-name\">' + esc(m.name) + '</span>';",
    )
    render = render.replace(
        "    html += '<span class=\"dd-theme\">' + m.theme + '</span>';",
        "    html += '<span class=\"dd-theme\">' + esc(m.theme) + '</span>';",
    )
    insert_after_price = (
        "    if (m.research_status) {\n"
        "      var rsCls = m.research_status === 'complete' ? 'dd-rs-ok' : 'dd-rs-warn';\n"
        "      html += '<span class=\"dd-research-status ' + rsCls + '\">' + esc(m.research_label || m.research_status) + '</span>';\n"
        "    }\n"
        "    html += '</div>';\n"
        "    html += '<div class=\"dd-meta-banner\">';\n"
        "    html += '<span class=\"dd-pill\">Models: ' + esc(fresh.models_as_of || '—') + '</span>';\n"
        "    html += '<span class=\"dd-pill' + (fresh.finnhub_ok ? '' : ' dd-pill-warn') + '\">Finnhub: ' + esc(fresh.finnhub || '—') + '</span>';\n"
        "    html += '<span class=\"dd-pill\">Earnings: ' + esc(fresh.earnings || '—') + '</span>';\n"
        "    html += '<span class=\"dd-pill' + (fresh.profile_ok ? '' : ' dd-pill-warn') + '\">Profile: ' + esc(fresh.profile || '—') + '</span>';\n"
        "    html += '</div>';\n"
        "    html += '<div class=\"dd-chart-block screen-only-dd-chart\">';\n"
        "    html += '<motion class=\"dd-section-title\">Price chart</div>';\n"
        "    html += '<div id=\"dd-tv-chart-container\" style=\"height:400px;border:1px solid var(--line);border-radius:8px;overflow:hidden;\"></div>';\n"
        "    html += '</div>';"
    ).replace("<motion", "<motion").replace("</motion>", "</motion>").replace("<motion", "<motion").replace("</motion>", "</motion>").replace("<motion", "<div").replace("</motion>", "</motion>").replace("</motion>", "</div>")
    render = render.replace(
        "    html += '<span class=\"dd-price\">$' + fmt(s.price) + '</span>';\n"
        "    html += '</div>';",
        "    html += '<span class=\"dd-price\">$' + fmt(s.price) + '</span>';\n" + insert_after_price,
    )
    render = render.replace(
        "    html += '<div class=\"dd-synth\">' + sw.text + '</div></motion>';",
        "    html += '<div class=\"dd-synth\">' + esc(sw.text) + '</div></div>';",
    )
    render = render.replace(
        "    html += '<div class=\"dd-synth\">' + sw.text + '</div></div>';",
        "    html += '<div class=\"dd-synth\">' + esc(sw.text) + '</div></div>';",
    )
    adv_pat = re.compile(
        r"    /\* 7\. Adversarial summary \*/\n.*?    html \+= '</div>';\n\n",
        re.DOTALL,
    )
    if not adv_pat.search(render):
        adv_pat = re.compile(
            r"    /\* 7\. Adversarial summary \*/\n.*?    html \+= '</motion>';\n",
            re.DOTALL,
        )
    render = adv_pat.sub(NARRATIVE_TAIL + "\n", render, count=1)
    render = render.replace(
        "    el.innerHTML = html;\n  }",
        "    el.innerHTML = html;\n"
        "    if (typeof window.loadDdChart === 'function') window.loadDdChart();\n"
        "  }",
    )
    return render


FMT_HELPERS_PAT = re.compile(
    r"  /\* ── Helper: format number[\s\S]*?"
    r"  function dcfColor\(u\) \{[\s\S]*?  \}\n",
    re.MULTILINE,
)

RENDER_PAT = re.compile(
    r"  function renderDeepDive\(ticker, el\) \{[\s\S]*?"
    r"(?:    el\.innerHTML = html;\n"
    r"    if \(typeof window\.loadDdChart === 'function'\) window\.loadDdChart\(\);\n)?"
    r"  \}\n",
    re.MULTILINE,
)
MARKED_PAT = re.compile(re.escape(MARK_S) + r"[\s\S]*?" + re.escape(MARK_E))
LEGACY_PAT = re.compile(
    r"(  /\* ── Populate ticker dropdown[\s\S]*?"
    r"  function renderDeepDive\(ticker, el\) \{[\s\S]*?    el\.innerHTML = html;\n  \}\n)"
    r"(\}\)\(\);\s*</script>)",
    re.DOTALL,
)
RUNTIME_BLOCK_PAT = re.compile(
    r"  /\* ── Populate ticker dropdown[\s\S]*?"
    r"  function renderDeepDive\(ticker, el\) \{[\s\S]*?    el\.innerHTML = html;\n  \}\n",
    re.MULTILINE,
)
MIN_RENDER_LEN = 800


def _extract_render_and_fmt(block: str) -> tuple[str | None, str]:
    render_m = RENDER_PAT.search(block)
    if not render_m or len(render_m.group(0)) < MIN_RENDER_LEN:
        return None, ""
    fmt_m = FMT_HELPERS_PAT.search(block[: render_m.start()])
    return render_m.group(0), (fmt_m.group(0) if fmt_m else "")


def _strip_legacy_picker(block: str) -> str:
    return re.sub(
        r"  /\* ── Populate ticker dropdown[\s\S]*?ddSel\.addEventListener\(\"change\"[\s\S]*?\}\);\n\n?",
        "\n",
        block,
        count=1,
    )


def main() -> None:
    tickers = load_core_tickers_display_order()
    if not tickers:
        print("No core tickers for Monitor dropdown", file=sys.stderr)
        sys.exit(2)
    man = load_manifest_map()
    names = display_names_for(tickers, man)

    doc = HTML.read_text(encoding="utf-8")
    marked_m = MARKED_PAT.search(doc)
    legacy_m = LEGACY_PAT.search(doc)

    render_src: str | None = None
    fmt_helpers = ""
    replace_marked = False
    replace_legacy = False
    legacy_tail = ""

    if marked_m:
        render_src, fmt_helpers = _extract_render_and_fmt(marked_m.group(0))
        if render_src:
            replace_marked = True

    if not render_src and legacy_m:
        block = _strip_legacy_picker(legacy_m.group(1))
        legacy_tail = legacy_m.group(2)
        render_src, fmt_helpers = _extract_render_and_fmt(block)
        if render_src:
            replace_legacy = True

    if not render_src and marked_m:
        stripped = MARKED_PAT.sub("", doc, count=1)
        leg2 = LEGACY_PAT.search(stripped)
        if leg2:
            block = _strip_legacy_picker(leg2.group(1))
            legacy_tail = leg2.group(2)
            render_src, fmt_helpers = _extract_render_and_fmt(block)
            if render_src:
                doc = stripped
                replace_legacy = True
                marked_m = None
                legacy_m = leg2
        else:
            rt2 = RUNTIME_BLOCK_PAT.search(stripped)
            if rt2:
                render_src, fmt_helpers = _extract_render_and_fmt(rt2.group(0))
                if render_src:
                    doc = stripped
                    replace_legacy = True
                    marked_m = None
                    legacy_m = rt2
                    legacy_tail = ""

    if not render_src:
        print("Could not find Monitor runtime block (picker + renderDeepDive)", file=sys.stderr)
        sys.exit(2)

    patched = patch_render(render_src)
    init = (
        "  if (ddSel.options.length > 1 && !ddSel.value) {\n"
        "    ddSel.selectedIndex = 1;\n"
        "    ddSel.dispatchEvent(new Event('change'));\n"
        "  }\n"
    )
    new_block = (
        f"{MARK_S}\n"
        f"{core_ticker_order_js(tickers)}"
        f"{PICKER}\n"
        f"{HELPERS}\n"
        f"{fmt_helpers}\n"
        f"{patched}"
        f"{init}"
        f"{MARK_E}\n"
    )

    if replace_marked and marked_m:
        doc = doc[: marked_m.start()] + new_block + doc[marked_m.end() :]
    elif replace_legacy and legacy_m:
        end = legacy_m.end() if hasattr(legacy_m, "end") else legacy_m.end
        if legacy_tail:
            doc = doc[: legacy_m.start()] + new_block + legacy_tail + doc[end:]
        else:
            doc = doc[: legacy_m.start()] + new_block + doc[end:]
    else:
        print("Could not apply Monitor runtime patch", file=sys.stderr)
        sys.exit(2)

    doc = patch_dd_select_html(doc, tickers, names)
    HTML.write_text(doc, encoding="utf-8")
    print(f"Patched Monitor dropdown ({len(tickers)} core tickers) + runtime JS")


if __name__ == "__main__":
    main()
