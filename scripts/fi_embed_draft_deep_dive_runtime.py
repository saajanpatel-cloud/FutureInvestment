#!/usr/bin/env python3
"""Embed DRAFT_REPORT and stock deep-dive renderDeepDive into SINGLE_SCREEN_REPORT.html."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from fi_embed_core import HTML, ROOT

CORE_JSON = ROOT / "watchlist-ui" / "core-shortlist.json"
MARK_JS_S = "  /* FI_DRAFT_JS_START */"
MARK_JS_E = "  /* FI_DRAFT_JS_END */"
MARK_RT_S = "  /* FI_DRAFT_RUNTIME_START */"
MARK_RT_E = "  /* FI_DRAFT_RUNTIME_END */"

STOCK_DEEP_DIVE_RENDER = r"""
  function draftFmtMoney(n) {
    if (n == null || isNaN(n)) return "—";
    return "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function draftFmtRange(lo, hi) {
    if (lo == null && hi == null) return "—";
    if (lo != null && hi != null) return draftFmtMoney(lo) + " – " + draftFmtMoney(hi);
    return draftFmtMoney(lo != null ? lo : hi);
  }
  function renderDraftPriceZones(z) {
    if (!z) return "";
    var html = '<div class="draft-price-zones">';
    html += '<div class="draft-zone-card"><strong>Potential buy range</strong><span class="draft-zone-range">' + draftFmtRange(z.buy_low, z.buy_high) + '</span></div>';
    html += '<div class="draft-zone-card"><strong>Potential sell / trim range</strong><span class="draft-zone-range">' + draftFmtRange(z.sell_low, z.sell_high) + '</span></div>';
    html += '<p class="draft-zone-method">' + esc(z.methodology || "") + '</p>';
    html += '</div>';
    return html;
  }
  function renderDeepDive(ticker, el) {
    var rep = (typeof DRAFT_REPORT !== "undefined") ? DRAFT_REPORT[ticker] : null;
    if (!rep || !rep.sections) {
      el.innerHTML = '<div class="draft-stub"><p><strong>' + esc(ticker) + '</strong> — No executive report yet. Re-run the watchlist pipeline with <code>FI_DRAFT_TICKERS=core</code>.</p></div>';
      return;
    }
    var sec = rep.sections;
    var m = (typeof META !== "undefined" && META[ticker]) ? META[ticker] : { name: ticker, theme: "" };
    var s = (typeof SCENARIOS !== "undefined") ? SCENARIOS[ticker] : null;
    var rub = (typeof RUBRIC !== "undefined") ? RUBRIC[ticker] : null;
    var sw = (typeof SOWHAT !== "undefined") ? SOWHAT[ticker] : { tier: "", color: "var(--fg)", text: "" };
    var nar = (typeof NARRATIVE !== "undefined" && NARRATIVE[ticker]) ? NARRATIVE[ticker] : {};
    var html = "";
    html += '<div class="dd-header-card">';
    html += '<span class="dd-ticker">' + esc(ticker) + '</span>';
    html += '<span class="dd-name">' + esc(m.name) + '</span>';
    html += '<span class="dd-theme">' + esc(m.theme) + '</span>';
    if (s) html += '<span class="dd-price">$' + fmt(s.price) + '</span>';
    if (rep.source === "heuristic") {
      html += '<span class="dd-pill draft-source-pill">Template narrative</span>';
    }
    html += '</div>';
    if (sw && sw.tier) {
      html += '<div class="dd-sowhat"><div class="dd-tier" style="background:' + sw.color + ';color:#fff;">' + esc(sw.tier);
      if (rub) html += ' · Rubric ' + rub[6] + '/24';
      html += '</div><div class="dd-synth">' + esc(sw.text) + '</div></div>';
    }
    html += '<article class="draft-report">';
    html += '<h3 class="draft-h3">At a glance</h3>';
    html += paras(sec.at_a_glance);
    html += '<h3 class="draft-h3">Investment thesis</h3>';
    html += paras(sec.investment_thesis);
    html += '<h3 class="draft-h3">Financial health</h3>';
    html += paras(sec.financial_health);
    if (nar.holders && nar.holders !== "—") {
      html += '<h4 class="draft-h4">Largest holders & ownership</h4>';
      html += paras(nar.holders);
    }
    html += '<h3 class="draft-h3">Competitive moat</h3>';
    html += paras(sec.competitive_moat + (sec.moat_score ? " (score " + sec.moat_score + "/10)" : ""));
    html += '<h3 class="draft-h3">Valuation</h3>';
    html += paras(sec.valuation);
    html += '<div class="draft-chart-block screen-only-draft-chart">';
    if (location.protocol === "file:") {
      html += '<p class="dd-file-protocol-note">Live candles need HTTP — run <code>scripts/serve_single_screen_report.sh</code> from the project root.</p>';
    }
    html += '<p class="draft-chart-print-note">Open the HTML dashboard for the live price chart.</p>';
    html += '<div id="dd-tv-chart-container" style="height:400px;border:1px solid var(--line);border-radius:8px;overflow:hidden;"></div>';
    html += '</div>';
    html += renderDraftPriceZones(rep.price_zones);
    if (typeof renderDdVizBlocks === "function") {
      html += renderDdVizBlocks(ticker, { parts: ["scenario", "dcf"] });
    }
    html += '<h3 class="draft-h3">Growth & outlook</h3>';
    html += paras(sec.growth_outlook);
    html += '<h3 class="draft-h3">Risks</h3>';
    if (typeof renderDdVizBlocks === "function") {
      html += renderDdVizBlocks(ticker, { parts: ["risk"] });
    }
    var risks = sec.risks_ranked || [];
    if (!risks.length) html += '<p class="muted">—</p>';
    else {
      html += '<ol class="draft-risks-list">';
      risks.forEach(function (r) {
        html += '<li><strong>' + esc(r.severity || "") + '</strong> — ' + esc(r.risk || "") + '</li>';
      });
      html += '</ol>';
    }
    html += '<h3 class="draft-h3">Bull vs bear debate</h3>';
    var d = sec.bull_bear_debate || {};
    html += '<div class="draft-debate draft-debate-bull"><strong>Bull</strong>' + paras(d.bull) + '</div>';
    html += '<div class="draft-debate draft-debate-bear"><strong>Bear</strong>' + paras(d.bear) + '</div>';
    html += '<p><strong>Conclusion</strong></p>' + paras(d.conclusion);
    html += '<h3 class="draft-h3">Latest earnings</h3>';
    html += paras(sec.latest_earnings);
    if (typeof renderDdVizBlocks === "function") {
      html += renderDdVizBlocks(ticker, { parts: ["refresh"] });
    }
    if (nar.watch && nar.watch !== "—") {
      html += '<h3 class="draft-h3">What to watch</h3>';
      html += paras(nar.watch);
    }
    if (typeof renderDdVizBlocks === "function") {
      html += renderDdVizBlocks(ticker, { parts: ["peers", "finnhub"], newsMaxArticles: 8, newsScrollHint: true });
    }
    html += '<h3 class="draft-h3">Should I buy today?</h3>';
    var v = sec.verdict || {};
    var cls = "draft-verdict-hold";
    if (v.rating === "Buy") cls = "draft-verdict-buy";
    if (v.rating === "Avoid") cls = "draft-verdict-avoid";
    html += '<span class="draft-verdict-rating ' + cls + '">' + esc(v.rating || "Hold") + '</span>';
    html += paras([v.short, v.medium, v.long].filter(Boolean).join("\n\n"));
    if (v.catalysts && v.catalysts.length) {
      html += '<p><strong>Catalysts</strong></p>';
      html += paras(v.catalysts.join(". "));
    }
    if (v.major_risks && v.major_risks.length) {
      html += '<p><strong>Major risks</strong></p>';
      html += paras(v.major_risks.join(". "));
    }
    html += '</article>';
    html += '<p class="muted draft-education">As of ' + esc(rep.as_of || "") + '. Education only — not personalized advice.</p>';
    el.innerHTML = html;
    scheduleDdChart(ticker);
  }
  window.openDraftDeepDive = function (ticker) {
    if (typeof openDeepDive === "function") openDeepDive(ticker);
  };
"""

def build_stock_deep_dive_render() -> str:
    return STOCK_DEEP_DIVE_RENDER.replace("<motion", "<div").replace("</motion>", "</div>")


def remove_legacy_draft_embed(doc: str) -> str:
    if MARK_RT_S in doc and MARK_RT_E in doc:
        doc = re.sub(
            re.escape(MARK_RT_S) + r"[\s\S]*?" + re.escape(MARK_RT_E) + r"\n?",
            "",
            doc,
            count=1,
        )
    return doc


def embed_draft_report_js(doc: str, draft_js: str) -> str:
    js_block = f"{MARK_JS_S}\n{draft_js}{MARK_JS_E}\n"
    anchor = "  /* FI_DEEP_DIVE_RUNTIME_START */"
    if MARK_JS_S in doc:
        doc = re.sub(
            re.escape(MARK_JS_S) + r"[\s\S]*?" + re.escape(MARK_JS_E),
            lambda _m: js_block.rstrip(),
            doc,
            count=1,
        )
    elif anchor in doc:
        doc = doc.replace(anchor, js_block + anchor, 1)
    else:
        print("Could not find anchor for DRAFT_REPORT", file=sys.stderr)
        sys.exit(2)
    return doc


def load_draft_js() -> str:
    if not CORE_JSON.is_file():
        return "  var DRAFT_REPORT = {};\n"
    doc = json.loads(CORE_JSON.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for it in doc.get("items") or []:
        dr = it.get("draft_report")
        t = (it.get("ticker") or "").strip().upper()
        if t and dr:
            payload = dict(dr)
            if not payload.get("source"):
                sc = payload.get("self_check") or {}
                notes = sc.get("corrections_applied") or []
                if any("Heuristic" in str(n) for n in notes):
                    payload["source"] = "heuristic"
                else:
                    payload["source"] = "llm"
            out[t] = payload
    inner = json.dumps(out, ensure_ascii=False, indent=2)
    inner = inner.replace("</", "<\\/")
    blob = f"  var DRAFT_REPORT = {inner};\n"
    validate_draft_js_blob(blob)
    return blob


def validate_draft_js_blob(blob: str) -> None:
    """Fail fast if embedded DRAFT_REPORT would break the page script (raw newlines in strings)."""
    if draft_js_has_raw_string_newlines(blob):
        print("DRAFT_REPORT embed has unescaped newlines inside strings", file=sys.stderr)
        sys.exit(2)
    stub = (
        "var esc=function(s){return String(s||'');};\n"
        "var paras=function(){};\nvar fmt=function(){};\n"
        "var renderDdVizBlocks=function(){};\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(stub + blob)
        path = Path(f.name)
    try:
        r = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
    finally:
        path.unlink(missing_ok=True)
    if r.returncode != 0:
        print(r.stderr or "node --check failed on DRAFT_REPORT", file=sys.stderr)
        sys.exit(2)


def draft_js_has_raw_string_newlines(js: str) -> bool:
    """Detect double-quoted strings that contain literal newlines (invalid JS)."""
    in_str = False
    esc = False
    for c in js:
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            elif c in "\n\r":
                return True
        elif c == '"':
            in_str = True
    return False


def extract_draft_js_from_html(doc: str) -> str:
    if MARK_JS_S not in doc or MARK_JS_E not in doc:
        return ""
    start = doc.index(MARK_JS_S) + len(MARK_JS_S)
    end = doc.index(MARK_JS_E)
    return doc[start:end].strip() + "\n"


def patch_doc(doc: str, draft_js: str) -> str:
    return embed_draft_report_js(doc, draft_js)


def main() -> int:
    if not HTML.is_file():
        print(f"Missing {HTML}", file=sys.stderr)
        return 2
    draft_js = load_draft_js()
    doc = HTML.read_text(encoding="utf-8")
    doc = patch_doc(doc, draft_js)
    doc = remove_legacy_draft_embed(doc)
    if draft_js_has_raw_string_newlines(extract_draft_js_from_html(doc)):
        print("HTML still has broken DRAFT_REPORT after patch", file=sys.stderr)
        sys.exit(2)
    HTML.write_text(doc, encoding="utf-8")
    n = draft_js.count('"sections"')
    print(f"Patched DRAFT_REPORT + runtime ({n} tickers) → {HTML}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
