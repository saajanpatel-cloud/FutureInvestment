#!/usr/bin/env python3
"""
Patch Stock Deep-Dive runtime JS: theme-sorted picker, openDeepDive, narrative UI.

Run after fi_embed_value_js.py (needs NARRATIVE, FRESHNESS, REFRESH_SIGNALS, TV_MAP).

Not investment advice.
"""
from __future__ import annotations

import re
import sys

from fi_embed_core import HTML

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
  window.openDeepDive = function (ticker) {
    var ddSel = document.getElementById("dd-ticker");
    if (!ddSel) return;
    ddSel.value = ticker;
    var container = document.getElementById("dd-content");
    if (container) renderDeepDive(ticker, container);
    var sec = document.getElementById("stock-deep-dive");
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
    var widgetDiv = document.createElement("motion");
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
    html += '<motion class="dd-narrative-head"><h3 class="dd-section-title">Executive report</h3>';
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
""".replace("<motion", "<div").replace("</motion>", "</div>")


def patch_render(render: str) -> str:
    render = render.replace(
        "adv = ADV[ticker], rub = RUBRIC[ticker];",
        "rub = RUBRIC[ticker];\n"
        "    var nar = (typeof NARRATIVE !== \"undefined\" && NARRATIVE[ticker]) ? NARRATIVE[ticker] : {};\n"
        "    var sig = (typeof REFRESH_SIGNALS !== \"undefined\" && REFRESH_SIGNALS[ticker]) "
        "? REFRESH_SIGNALS[ticker] : { bullish: [], bearish: [] };\n"
        "    var fresh = (typeof FRESHNESS !== \"undefined\" && FRESHNESS[ticker]) ? FRESHNESS[ticker] : {};",
    )
    render = render.replace("/30</div>", "/24</motion>")
    render = render.replace("</motion>", "</div>")
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
        "    html += '</motion>';\n"
        "    html += '<div class=\"dd-chart-block screen-only-dd-chart\">';\n"
        "    html += '<div class=\"dd-section-title\">Price chart</div>';\n"
        "    html += '<motion id=\"dd-tv-chart-container\" style=\"height:400px;border:1px solid var(--line);border-radius:8px;overflow:hidden;\"></div>';\n"
        "    html += '</div>';"
    ).replace("<motion", "<motion").replace("</motion>", "</motion>").replace("<motion", "<div").replace("</motion>", "</div>")
    render = render.replace(
        "    html += '<span class=\"dd-price\">$' + fmt(s.price) + '</span>';\n"
        "    html += '</div>';",
        "    html += '<span class=\"dd-price\">$' + fmt(s.price) + '</span>';\n" + insert_after_price,
    )
    render = render.replace(
        "    html += '<motion class=\"dd-synth\">' + sw.text + '</div></div>';",
        "    html += '<div class=\"dd-synth\">' + esc(sw.text) + '</div></div>';",
    )
    adv_pat = re.compile(
        r"    /\* 7\. Adversarial summary \*/\n.*?    html \+= '</div>';\n\n",
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


def main() -> None:
    doc = HTML.read_text(encoding="utf-8")
    if MARK_S in doc:
        doc = re.sub(
            re.escape(MARK_S) + r"[\s\S]*?" + re.escape(MARK_E) + r"\n?",
            "",
            doc,
            count=1,
        )

    pat = re.compile(
        r"(  /\* ── Populate ticker dropdown.*?"
        r"  function renderDeepDive\(ticker, el\) \{.*?    el\.innerHTML = html;\n  \}\n)"
        r"(\}\)\(\);\s*</script>)",
        re.DOTALL,
    )
    m = pat.search(doc)
    if not m:
        print("Could not find deep-dive runtime block", file=sys.stderr)
        sys.exit(2)

    block = m.group(1)
    tail = m.group(2)

    block = re.sub(
        r"  Object\.keys\(META\)\.forEach",
        "  Object.keys(META).sort(function (a, b) {\n"
        "    var ta = (META[a].theme || '').toLowerCase();\n"
        "    var tb = (META[b].theme || '').toLowerCase();\n"
        "    if (ta !== tb) return ta < tb ? -1 : 1;\n"
        "    return a < b ? -1 : a > b ? 1 : 0;\n"
        "  }).forEach",
        block,
        count=1,
    )
    block = re.sub(
        r"\n  ddSel\.addEventListener\(\"change\"[\s\S]*?renderDeepDive\(ticker, container\);\n  \}\);\n",
        "\n",
        block,
        count=1,
    )

    render_m = re.search(
        r"(  function renderDeepDive\(ticker, el\) \{.*?    el\.innerHTML = html;\n  \}\n)",
        block,
        re.DOTALL,
    )
    if not render_m:
        print("renderDeepDive not found", file=sys.stderr)
        sys.exit(2)
    render = patch_render(render_m.group(1))
    head = block[: render_m.start()]
    new_block = (
        f"{MARK_S}\n"
        f"{head}"
        f"{HELPERS}\n"
        f"{render}"
        f"  ddSel.addEventListener('change', function () {{\n"
        f"    var ticker = ddSel.value;\n"
        f"    var container = document.getElementById('dd-content');\n"
        f"    if (!ticker) {{ if (container) container.innerHTML = ''; return; }}\n"
        f"    renderDeepDive(ticker, container);\n"
        f"  }});\n"
        f"  if (ddSel.options.length) {{\n"
        f"    ddSel.selectedIndex = 0;\n"
        f"    renderDeepDive(ddSel.value, document.getElementById('dd-content'));\n"
        f"  }}\n"
        f"{MARK_E}\n"
    )
    doc = doc[: m.start()] + new_block + tail + doc[m.end() :]
    HTML.write_text(doc, encoding="utf-8")
    print("Patched deep-dive runtime JS")


if __name__ == "__main__":
    main()
