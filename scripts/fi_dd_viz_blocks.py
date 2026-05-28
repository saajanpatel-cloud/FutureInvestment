"""Shared Monitor/DRAFT valuation widget JS (renderDdVizBlocks)."""

VIZ_BLOCKS = r"""
  function renderDdVizBlocks(ticker, opts) {
    opts = opts || {};
    var partList = opts.parts || ["scenario", "risk", "dcf", "refresh", "peers", "finnhub"];
    var want = {};
    partList.forEach(function (p) { want[p] = true; });
    var m = (typeof META !== "undefined" && META[ticker]) ? META[ticker] : {};
    var s = (typeof SCENARIOS !== "undefined") ? SCENARIOS[ticker] : null;
    var r = (typeof RISK !== "undefined") ? RISK[ticker] : null;
    var mc = (typeof MC !== "undefined") ? MC[ticker] : null;
    var dcf = (typeof DCF !== "undefined") ? DCF[ticker] : null;
    var nar = (typeof NARRATIVE !== "undefined" && NARRATIVE[ticker]) ? NARRATIVE[ticker] : {};
    var sig = (typeof REFRESH_SIGNALS !== "undefined" && REFRESH_SIGNALS[ticker])
      ? REFRESH_SIGNALS[ticker] : { bullish: [], bearish: [] };
    var html = "";
    if (want.scenario && s) {
      html += '<div class="dd-section-title">Scenario range</motion>';
      html += '<div class="sc-card">';
      var lo = s.bear.price, hi = s.bull.price, span = hi - lo || 1;
      var baseStart = ((s.bear.price - lo) / span) * 100;
      var baseEnd = ((s.base.price - lo) / span) * 100;
      var bearW = baseStart, baseW = baseEnd - baseStart, bullW = 100 - baseEnd;
      if (bearW < 1) bearW = 1;
      if (baseW < 1) baseW = 1;
      if (bullW < 1) bullW = 1;
      var total = bearW + baseW + bullW;
      bearW = (bearW / total) * 100;
      baseW = (baseW / total) * 100;
      bullW = (bullW / total) * 100;
      var curPct = clampPct(s.price, lo, hi);
      var wtPct = clampPct(s.wt.price, lo, hi);
      html += '<div class="sc-range">';
      html += '<div class="sc-seg bear" style="width:' + bearW + '%">Bear</div>';
      html += '<motion class="sc-seg base" style="width:' + baseW + '%">Base</motion>';
      html += '<div class="sc-seg bull" style="width:' + bullW + '%">Bull</motion>';
      html += '<div class="sc-marker" style="left:' + curPct + '%"><span class="sc-marker-label">Now $' + fmt(s.price) + '</span></motion>';
      html += '<div class="sc-diamond" style="left:' + wtPct + '%"></div>';
      html += '<div class="sc-diamond-label" style="left:' + wtPct + '%;position:absolute;">Wt $' + fmt(s.wt.price) + '</motion>';
      html += '</motion>';
      html += '<div class="sc-labels"><span>$' + fmt(lo) + '</span><span>$' + fmt(s.base.price) + '</span><span>$' + fmt(hi) + '</span></motion>';
      html += '<div class="sc-stats">';
      html += '<span>Bear: <span class="s-low">' + s.bear.upside + '</span> (p=' + s.bear.prob + ')</span>';
      html += '<span>Base: ' + s.base.upside + ' (p=' + s.base.prob + ')</span>';
      html += '<span>Bull: <span class="s-high">' + s.bull.upside + '</span> (p=' + s.bull.prob + ')</span>';
      html += '<span>Weighted: <span style="color:var(--accent);font-weight:700;">' + s.wt.upside + '</span></span>';
      html += '</motion></motion>';
    }
    if (want.risk && r) {
      html += '<div class="dd-section-title">Risk dashboard</motion>';
      html += '<div class="rg-grid">';
      var metrics = [
        { key:"beta", label:"Beta", val:r.beta, lo:0, hi:3, fmt:function(v){return v.toFixed(2);} },
        { key:"vol", label:"Ann. Volatility", val:r.vol, lo:0, hi:120, fmt:function(v){return v.toFixed(1)+"%";} },
        { key:"maxDD", label:"Max Drawdown", val:r.maxDD, lo:-70, hi:0, fmt:function(v){return v.toFixed(1)+"%";} },
        { key:"ret1y", label:"1Y Return", val:r.ret1y, lo:-50, hi:200, fmt:function(v){return (v>=0?"+":"")+v.toFixed(1)+"%";} },
        { key:"sharpe", label:"Sharpe Ratio", val:r.sharpe, lo:-1, hi:4, fmt:function(v){return v.toFixed(2);} },
        { key:"spyCorr", label:"SPY Correlation", val:r.spyCorr, lo:0, hi:1, fmt:function(v){return v.toFixed(2);} }
      ];
      metrics.forEach(function (met) {
        var pos = clampPct(met.val, met.lo, met.hi);
        var col = riskColor(met.key, met.val);
        html += '<div class="rg-card">';
        html += '<div class="rg-label">' + met.label + '</motion>';
        html += '<div class="rg-value" style="color:' + col + '">' + met.fmt(met.val) + '</motion>';
        html += '<div class="rg-bar-wrap"><div class="rg-bar-fill" style="width:' + pos + '%;background:' + col + ';opacity:0.3;"></motion>';
        html += '<div class="rg-bar-marker" style="left:' + pos + '%;background:' + col + ';"></motion></motion>';
        html += '<div class="rg-interp">' + riskInterp(met.key, met.val) + '</motion>';
        html += '</motion>';
      });
      html += '</motion>';
    }
    if (want.dcf && dcf && dcf.rows && dcf.rows.length) {
      html += '<motion class="dd-section-title">DCF sensitivity</motion>';
      html += '<div class="dcf-wrap"><div class="dcf-grid">';
      html += '<div class="dcf-corner">Growth \\ WACC</motion>';
      dcf.waccs.forEach(function (w) { html += '<div class="dcf-hdr">' + pct(w) + '</motion>'; });
      dcf.rows.forEach(function (row, ri) {
        html += '<div class="dcf-row-hdr">' + pct(dcf.growths[ri]) + '</motion>';
        row.forEach(function (cell) {
          html += '<div class="dcf-cell" style="background:' + dcfColor(cell.u) + '">';
          html += '<div class="dcf-price">$' + fmt(cell.p) + '</motion>';
          html += '<div class="dcf-pct">' + signPct(cell.u) + '</motion></motion>';
        });
      });
      html += '</motion></motion>';
    }
    if (want.refresh) {
      html += '<div class="dd-section-title">Signals this refresh</motion>';
      html += '<p class="dd-signals-intro">' + esc(nar.signals_intro || "") + '</p>';
      html += '<h5 class="dd-signals-sub">Improving this refresh</h5>' + signalList(sig.bullish, "dd-signals-bull");
      html += '<h5 class="dd-signals-sub">Worsening this refresh</h5>' + signalList(sig.bearish, "dd-signals-bear");
    }
    if (want.peers && typeof PEERS_BY_THEME !== "undefined" && m.theme_slug && PEERS_BY_THEME[m.theme_slug]) {
      html += '<div class="dd-section-title">Peers on this shortlist</motion>';
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
    if (want.finnhub) {
      var fh = (typeof FINNHUB_BY_TICKER !== "undefined" && FINNHUB_BY_TICKER[ticker]) ? FINNHUB_BY_TICKER[ticker] : null;
      if (fh) {
        html += '<div class="dd-section-title">Finnhub context</motion>';
        html += '<p class="dd-finnhub-line">' + esc(fh.context_line || "") + '</p>';
        html += '<p class="dd-finnhub-meta muted">Analyst skew: ' + esc(fh.analyst_skew) + ' · Insider MSPR: ' + esc(fh.insider_mspr) + ' · News (7d): ' + esc(fh.news_7d) + ' · Next earnings: ' + esc(fh.next_earnings) + '</p>';
        if (fh.articles && fh.articles.length) {
          var maxA = opts.newsMaxArticles || 8;
          if (opts.newsScrollHint && fh.articles.length > 3) {
            html += '<p class="dd-news-scroll-hint muted">Latest headlines — scroll for more.</p>';
          }
          html += '<div class="dd-news-table-wrap"><table class="dd-news-table"><thead><tr><th>Date</th><th>Headline</th><th>Source</th></tr></thead><tbody>';
          fh.articles.slice(0, maxA).forEach(function (a) {
            var dt = (a.datetime || a.published || "").slice(0, 10);
            var head = a.headline || a.title || "—";
            var src = a.source || "—";
            var url = a.url || a.link || "";
            html += "<tr><td>" + esc(dt) + "</td><td class=\"dd-news-headline\">";
            if (url) html += '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(head) + "</a>";
            else html += esc(head);
            html += "</td><td>" + esc(src) + "</td></tr>";
          });
          html += "</tbody></table></motion>";
        }
      }
    }
    return html;
  }
""".replace("<motion", "<div").replace("</motion>", "</div>")
