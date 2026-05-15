#!/usr/bin/env python3
"""
DEPRECATED — retail social sentiment scanner (not used by refresh_watchlists.sh).

The watchlist pipeline now uses ``fi_finnhub_context.py`` for free-tier Finnhub
market context (analyst recommendations, insider MSPR, headline count, earnings).
Finnhub ``/stock/social-sentiment`` returns HTTP 403 on the free tier.

This script remains for manual spikes and legacy ``reddit_x`` experiments only.

Not investment advice. Sentiment is noisy, lagging, and often wrong.

Usage (legacy):
  python fi_sentiment.py --tickers-file research/watchlists/report_core_tickers.txt \\
    --csv research/watchlists/sentiment_results.csv \\
    --html research/watchlists/sentiment_fragment.html
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOOKBACK_DAYS = 7
SUBREDDITS = ["wallstreetbets", "investing", "stocks"]

BULL_WORDS = re.compile(
    r"\b("
    r"bull|bullish|calls|moon|mooning|undervalued|buy|long|breakout|rocket|"
    r"upside|squeeze|dip|buying|accumulate|green|rip|gamma|tendies|yolo"
    r")\b",
    re.IGNORECASE,
)
BEAR_WORDS = re.compile(
    r"\b("
    r"bear|bearish|puts|overvalued|sell|short|dump|crash|bubble|"
    r"downside|fade|red|rug|baghold|bagholder|tank|tanking|drill"
    r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Ticker loading helpers (mirror other fi_* scripts)
# ---------------------------------------------------------------------------

def _normalize_tickers(raw: str) -> list[str]:
    out = []
    for t in raw.split(","):
        t = t.strip().upper()
        if t:
            out.append(t)
    return out


def _tickers_from_file(path: Path) -> list[str]:
    """One ticker per line (e.g. report_core_tickers.txt); skip blanks and # comments."""
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s.upper())
    return out


def _tickers_from_assumptions(path: Path) -> list[str]:
    out: list[str] = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            t = (row.get("ticker") or "").strip().upper()
            if t:
                out.append(t)
    return out


def _dedup(tickers: list[str]) -> list[str]:
    seen: set[str] = set()
    return [t for t in tickers if not (t in seen or seen.add(t))]  # type: ignore[func-returns-value]


# ---------------------------------------------------------------------------
# Finnhub social sentiment (default v1 provider)
# ---------------------------------------------------------------------------

def _finnhub_api_key() -> str:
    return (os.environ.get("FINNHUB_API_KEY") or "").strip()


def _finnhub_available() -> bool:
    return bool(_finnhub_api_key())


def _finnhub_symbol(ticker: str) -> str:
    """Strip exchange suffix for Finnhub US-oriented symbol lookup."""
    t = ticker.strip().upper()
    for sep in (".", "-"):
        if sep in t:
            t = t.split(sep)[0]
    return t


def _signal_from_pos_neg(pos: float, neg: float) -> str:
    total = pos + neg
    if total <= 0:
        return "mixed"
    bull_pct = pos / total * 100
    bear_pct = neg / total * 100
    if bull_pct >= 60:
        return "bull"
    if bear_pct >= 60:
        return "bear"
    return "mixed"


def _latest_series_point(series: Any) -> dict[str, Any] | None:
    if not series:
        return None
    if isinstance(series, list):
        if not series:
            return None
        last = series[-1]
        return last if isinstance(last, dict) else None
    if isinstance(series, dict):
        return series
    return None


def _point_metrics(point: dict[str, Any] | None) -> dict[str, Any]:
    if not point:
        return {
            "mentions": 0,
            "bull_pct": 0,
            "bear_pct": 0,
            "signal": "no data",
        }
    mention = int(point.get("mention") or 0)
    pos = float(point.get("positiveScore") or 0)
    neg = float(point.get("negativeScore") or 0)
    total = pos + neg
    bull_pct = round(pos / total * 100) if total > 0 else 0
    bear_pct = round(neg / total * 100) if total > 0 else 0
    if mention == 0 and total == 0:
        sig = "no data"
    else:
        sig = _signal_from_pos_neg(pos, neg)
    return {
        "mentions": mention,
        "bull_pct": bull_pct,
        "bear_pct": bear_pct,
        "signal": sig,
    }


def _fetch_finnhub_body(symbol: str) -> dict[str, Any]:
    q = urllib.parse.urlencode({"symbol": symbol, "token": _finnhub_api_key()})
    url = f"https://finnhub.io/api/v1/stock/social-sentiment?{q}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode())


def _finnhub_sentiment(ticker: str) -> dict[str, Any]:
    sym = _finnhub_symbol(ticker)
    try:
        body = _fetch_finnhub_body(sym)
    except urllib.error.HTTPError as e:
        print(f"  ⚠ Finnhub HTTP {e.code} for {ticker} ({sym})", file=sys.stderr)
        na = "N/A"
        return {
            "finnhub_symbol": sym,
            "reddit_mentions_7d": na,
            "reddit_bull_pct": na,
            "reddit_bear_pct": na,
            "reddit_signal": na,
            "x_mentions_7d": na,
            "x_signal": na,
            "combined_signal": na,
        }
    except Exception as e:
        print(f"  ⚠ Finnhub error for {ticker}: {e}", file=sys.stderr)
        na = "N/A"
        return {
            "finnhub_symbol": sym,
            "reddit_mentions_7d": na,
            "reddit_bull_pct": na,
            "reddit_bear_pct": na,
            "reddit_signal": na,
            "x_mentions_7d": na,
            "x_signal": na,
            "combined_signal": na,
        }

    rd = _point_metrics(_latest_series_point(body.get("reddit")))
    xd = _point_metrics(_latest_series_point(body.get("twitter")))
    combined = _combined_signal(rd["signal"], xd["signal"])
    return {
        "finnhub_symbol": sym,
        "reddit_mentions_7d": rd["mentions"],
        "reddit_bull_pct": rd["bull_pct"],
        "reddit_bear_pct": rd["bear_pct"],
        "reddit_signal": rd["signal"],
        "x_mentions_7d": xd["mentions"],
        "x_signal": xd["signal"],
        "combined_signal": combined,
    }


# ---------------------------------------------------------------------------
# Reddit via PRAW (legacy provider)
# ---------------------------------------------------------------------------

def _env_nonempty(key: str) -> bool:
    return bool((os.environ.get(key) or "").strip())


def _reddit_oauth_available() -> bool:
    try:
        import praw  # noqa: F401
    except ImportError:
        return False
    needed = ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT")
    return all(_env_nonempty(k) for k in needed)


def _classify(text: str) -> tuple[int, int]:
    """Return (bull_hits, bear_hits) from keyword matching."""
    bulls = len(BULL_WORDS.findall(text))
    bears = len(BEAR_WORDS.findall(text))
    return bulls, bears


def _ticker_in_post_text(ticker: str, text: str) -> bool:
    """Match cashtag, word boundary, or common r/WSB path forms."""
    if not text:
        return False
    t = re.escape(ticker)
    patterns = [
        rf"\${t}\b",
        rf"\b{t}\b",
        rf"/{t}\b",
        rf"\({t}\)",
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _reddit_signal_from_counts(mentions: int, total_bull: int, total_bear: int) -> str:
    if mentions == 0:
        return "no data"
    total_signals = total_bull + total_bear
    if total_signals == 0:
        return "mixed"
    bull_pct = round(total_bull / total_signals * 100)
    bear_pct = round(total_bear / total_signals * 100)
    if bull_pct >= 60:
        return "bull"
    if bear_pct >= 60:
        return "bear"
    return "mixed"


def _reddit_sentiment_praw(ticker: str) -> dict[str, Any]:
    """Search Reddit via PRAW: cashtag + symbol queries (Reddit search is weak on bare symbols)."""
    import praw
    from datetime import timedelta

    reddit = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"].strip(),
        client_secret=os.environ["REDDIT_CLIENT_SECRET"].strip(),
        user_agent=os.environ["REDDIT_USER_AGENT"].strip(),
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    mentions = 0
    total_bull = 0
    total_bear = 0
    seen: set[str] = set()
    queries = [f"${ticker}", ticker]

    for sub_name in SUBREDDITS:
        try:
            sub = reddit.subreddit(sub_name)
            for q in queries:
                for post in sub.search(q, sort="new", time_filter="month", limit=75):
                    pid = getattr(post, "id", None) or ""
                    if pid and pid in seen:
                        continue
                    created = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
                    if created < cutoff:
                        continue
                    text = f"{post.title} {post.selftext or ''}"
                    if not _ticker_in_post_text(ticker, text):
                        continue
                    if pid:
                        seen.add(pid)
                    mentions += 1
                    b, br = _classify(text)
                    total_bull += b
                    total_bear += br
        except Exception as e:
            print(f"  ⚠ Reddit PRAW r/{sub_name} error for {ticker}: {e}", file=sys.stderr)
        time.sleep(0.4)

    total_signals = total_bull + total_bear
    bull_pct = round(total_bull / total_signals * 100) if total_signals > 0 else 0
    bear_pct = round(total_bear / total_signals * 100) if total_signals > 0 else 0
    sig = _reddit_signal_from_counts(mentions, total_bull, total_bear)

    return {
        "mentions": mentions,
        "bull_pct": bull_pct,
        "bear_pct": bear_pct,
        "signal": sig,
    }


def _reddit_sentiment_public(ticker: str) -> dict[str, Any]:
    """Unauthenticated subreddit search (JSON). Opt-in via --public-reddit; Reddit often returns 429."""
    import json as json_lib
    import urllib.error
    import urllib.parse
    import urllib.request
    from datetime import timedelta

    ua = (
        (os.environ.get("REDDIT_USER_AGENT") or "").strip()
        or "FutureInvestmentSentiment/1.0 (public JSON; research dashboard)"
    )
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    mentions = 0
    total_bull = 0
    total_bear = 0
    seen: set[str] = set()
    queries = [f"${ticker}"]

    for sub_name in ("wallstreetbets", "stocks"):
        for q in queries:
            params = urllib.parse.urlencode(
                {
                    "q": q,
                    "restrict_sr": "true",
                    "include_over_18": "true",
                    "sort": "new",
                    "t": "week",
                    "limit": "100",
                }
            )
            url = f"https://www.reddit.com/r/{sub_name}/search.json?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            data = None
            for attempt in range(4):
                try:
                    with urllib.request.urlopen(req, timeout=25) as resp:
                        data = json_lib.loads(resp.read().decode())
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 429 and attempt < 3:
                        wait = 2.0 * (2**attempt)
                        print(f"  ℹ Reddit 429 for r/{sub_name}; sleeping {wait:.0f}s…", file=sys.stderr)
                        time.sleep(wait)
                        continue
                    print(f"  ⚠ Reddit public r/{sub_name} q={q!r}: {e}", file=sys.stderr)
                    break
                except (urllib.error.URLError, TimeoutError, ValueError) as e:
                    print(f"  ⚠ Reddit public r/{sub_name} q={q!r}: {e}", file=sys.stderr)
                    break
            if data is None:
                time.sleep(1.1)
                continue
            for child in data.get("data", {}).get("children", []):
                post = child.get("data") or {}
                pid = post.get("name") or post.get("id") or ""
                if pid and pid in seen:
                    continue
                created = datetime.fromtimestamp(post.get("created_utc", 0), tz=timezone.utc)
                if created < cutoff:
                    continue
                text = f"{post.get('title', '')} {post.get('selftext', '')}"
                if not _ticker_in_post_text(ticker, text):
                    continue
                if pid:
                    seen.add(pid)
                mentions += 1
                b, br = _classify(text)
                total_bull += b
                total_bear += br
            time.sleep(2.0)

    total_signals = total_bull + total_bear
    bull_pct = round(total_bull / total_signals * 100) if total_signals > 0 else 0
    bear_pct = round(total_bear / total_signals * 100) if total_signals > 0 else 0
    sig = _reddit_signal_from_counts(mentions, total_bull, total_bear)
    return {
        "mentions": mentions,
        "bull_pct": bull_pct,
        "bear_pct": bear_pct,
        "signal": sig,
    }


def _reddit_sentiment_combined(ticker: str, *, allow_public_reddit: bool) -> dict[str, Any]:
    """Reddit: OAuth + PRAW is the supported path. Optional public JSON is best-effort and often 429s."""
    if _reddit_oauth_available():
        return _reddit_sentiment_praw(ticker)
    if allow_public_reddit:
        return _reddit_sentiment_public(ticker)
    return _reddit_na()


def _reddit_na() -> dict[str, Any]:
    return {"mentions": "N/A", "bull_pct": "N/A", "bear_pct": "N/A", "signal": "N/A"}


# ---------------------------------------------------------------------------
# X/Twitter via tweepy
# ---------------------------------------------------------------------------

def _tweepy_available() -> bool:
    try:
        import tweepy  # noqa: F401
    except ImportError:
        return False
    return _env_nonempty("TWITTER_BEARER_TOKEN")


def _x_query(ticker: str) -> str:
    """Cashtag-first; add bare symbol only for longer tickers (short symbols are too noisy on X)."""
    if len(ticker) <= 3:
        return f"${ticker} -is:retweet lang:en"
    return f"({ticker} OR ${ticker}) -is:retweet lang:en"


def _x_sentiment(ticker: str) -> dict[str, Any]:
    import tweepy

    client = tweepy.Client(bearer_token=os.environ["TWITTER_BEARER_TOKEN"].strip())
    query = _x_query(ticker)

    mentions = 0
    total_bull = 0
    total_bear = 0

    try:
        resp = client.search_recent_tweets(query=query, max_results=100)
        if resp.data:
            for tweet in resp.data:
                mentions += 1
                b, br = _classify(tweet.text)
                total_bull += b
                total_bear += br
    except Exception as e:
        print(f"  ⚠ X/Twitter error for {ticker}: {e}", file=sys.stderr)

    total_signals = total_bull + total_bear
    if mentions == 0:
        signal = "no data"
    elif total_signals == 0:
        signal = "mixed"
    elif (total_bull / total_signals) >= 0.6:
        signal = "bull"
    elif (total_bear / total_signals) >= 0.6:
        signal = "bear"
    else:
        signal = "mixed"

    return {"mentions": mentions, "signal": signal}


def _x_na() -> dict[str, Any]:
    return {"mentions": "N/A", "signal": "N/A"}


# ---------------------------------------------------------------------------
# Combined signal
# ---------------------------------------------------------------------------

def _combined_signal(reddit_sig: str, x_sig: str) -> str:
    """Combine sources; ignore N/A (API off) and no_data (no hits) when the other source has a real label."""
    parts: list[str] = []
    for s in (reddit_sig, x_sig):
        if s == "N/A":
            continue
        if s == "no data":
            continue
        parts.append(s)
    if not parts:
        if reddit_sig == "N/A" and x_sig == "N/A":
            return "N/A"
        return "no data"
    if all(s == "bull" for s in parts):
        return "bull"
    if all(s == "bear" for s in parts):
        return "bear"
    return "mixed"


# ---------------------------------------------------------------------------
# Output: CSV
# ---------------------------------------------------------------------------

_CSV_FIELDS = [
    "ticker",
    "source",
    "finnhub_symbol",
    "reddit_mentions_7d",
    "reddit_bull_pct",
    "reddit_bear_pct",
    "reddit_signal",
    "x_mentions_7d",
    "x_signal",
    "combined_signal",
    "last_updated",
]


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"  ✓ Wrote {path} ({len(rows)} rows)", file=sys.stderr)


# ---------------------------------------------------------------------------
# Output: HTML fragment
# ---------------------------------------------------------------------------

_STYLE_BLOCK = """\
<style>
.sentiment-badges { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0.75rem 0; }
.sentiment-row { display: flex; align-items: center; gap: 0.35rem; flex-wrap: wrap; }
.pill { font-size: 0.8rem; font-weight: 600; padding: 0.1rem 0.4rem; border-radius: 3px;
        background: var(--bg-alt, #f0f0f0); }
.sentiment-badge { font-size: 0.75rem; padding: 0.15rem 0.4rem; border-radius: 4px; }
.sentiment-badge.bull { background: color-mix(in srgb, var(--accent) 15%, transparent);
                        color: var(--accent); }
.sentiment-badge.bear { background: color-mix(in srgb, var(--warn) 15%, transparent);
                        color: var(--warn); }
.sentiment-badge.mixed { background: color-mix(in srgb, var(--muted) 10%, transparent);
                         color: var(--muted); }
</style>"""


def _badge_class(signal: str) -> str:
    if signal == "bull":
        return "bull"
    if signal == "bear":
        return "bear"
    return "mixed"


def _reddit_badge_text(r: dict[str, Any]) -> str:
    m = r["reddit_mentions_7d"]
    bp = r["reddit_bull_pct"]
    if m == "N/A":
        return "Reddit: N/A"
    return f"Reddit: {m} mentions, {bp}% bull"


def _x_badge_text(r: dict[str, Any]) -> str:
    m = r["x_mentions_7d"]
    if m == "N/A":
        return "X: N/A"
    return f"X: {m} mentions"


def _build_html(
    rows: list[dict[str, Any]], ts: str, has_any_api: bool, provider: str
) -> str:
    if not has_any_api:
        return (
            '<section id="sentiment">\n'
            "  <h2>Social sentiment</h2>\n"
            '  <p class="muted">Sentiment data pending &mdash; set '
            "<code>FINNHUB_API_KEY</code> in <code>.env</code> (recommended) and run "
            "<code>python scripts/fi_sentiment.py</code>, or fill "
            "<code>sentiment_results.csv</code> manually.</p>\n"
            '  <p class="muted" style="font-size:0.8rem;">Not investment advice.</p>\n'
            "</section>\n"
        )

    if provider == "finnhub":
        purpose = (
            '<p class="section-purpose"><strong>What is this?</strong> Aggregated '
            "Reddit and Twitter/X mention scores from "
            '<a href="https://finnhub.io/docs/api/social-sentiment">Finnhub social sentiment</a> '
            "(freemium API; <code>FINNHUB_API_KEY</code> in <code>.env</code>). "
            "Bull/bear labels use Finnhub positive/negative mention scores — not a predictive model.</p>"
        )
        title = "Social sentiment (Finnhub)"
    else:
        purpose = (
            '<p class="section-purpose"><strong>What is this?</strong> Legacy path: '
            "keyword-based bull/bear from Reddit (PRAW) and optional X. "
            "Prefer <code>--provider auto</code> with Finnhub for daily refresh.</p>"
        )
        title = "Social sentiment (7-day)"

    lines = [
        _STYLE_BLOCK,
        '<section id="sentiment">',
        f"  <h2>{title}</h2>",
        purpose,
        f'  <p class="muted">Generated {ts}. Not investment advice.</p>',
        '  <div class="sentiment-badges">',
    ]

    for r in rows:
        r_cls = _badge_class(r["reddit_signal"])
        x_cls = _badge_class(r["x_signal"])
        lines.append(
            f'    <div class="sentiment-row">\n'
            f'      <span class="pill">{r["ticker"]}</span>\n'
            f'      <span class="sentiment-badge {r_cls}">{_reddit_badge_text(r)}</span>\n'
            f'      <span class="sentiment-badge {x_cls}">{_x_badge_text(r)}</span>\n'
            f"    </div>"
        )

    lines += ["  </div>", "</section>", ""]
    return "\n".join(lines)


def _write_html(html: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    print(f"  ✓ Wrote {path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _load_repo_dotenv() -> None:
    """Load `FutureInvestment/.env` so refresh runs pick up API keys without manual export."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env", override=False)


def main() -> None:
    _load_repo_dotenv()

    ap = argparse.ArgumentParser(
        description="Social sentiment scanner for proposed tickers.",
    )
    ap.add_argument("--tickers", help="Comma-separated symbols, e.g. NVDA,AMD")
    ap.add_argument(
        "--assumptions",
        type=Path,
        help="Path to scenario_assumptions.csv (reads ticker column)",
    )
    ap.add_argument(
        "--tickers-file",
        type=Path,
        help="Text file with one ticker per line (e.g. report_core_tickers.txt)",
    )
    ap.add_argument("--csv", help="Output CSV path")
    ap.add_argument("--html", help="Output HTML fragment path")
    ap.add_argument(
        "--public-reddit",
        action="store_true",
        help="Legacy reddit_x only: public subreddit JSON if OAuth missing (often 429).",
    )
    ap.add_argument(
        "--provider",
        choices=("auto", "finnhub", "reddit_x"),
        default="auto",
        help="auto=Finnhub if FINNHUB_API_KEY else legacy reddit_x (default).",
    )
    ap.add_argument(
        "--use-x",
        action="store_true",
        help="Legacy reddit_x only: call X API when TWITTER_BEARER_TOKEN is set (may incur charges).",
    )
    args = ap.parse_args()

    if not args.csv and not args.html:
        ap.error("Provide at least one of --csv or --html")

    tickers: list[str] = []
    if args.assumptions:
        tickers.extend(_tickers_from_assumptions(args.assumptions.resolve()))
    if args.tickers_file:
        tickers.extend(_tickers_from_file(args.tickers_file.resolve()))
    if args.tickers:
        tickers.extend(_normalize_tickers(args.tickers))
    tickers = _dedup(tickers)
    if not tickers:
        print("No tickers: use --assumptions and/or --tickers.", file=sys.stderr)
        sys.exit(2)

    provider = args.provider
    if provider == "auto":
        provider = "finnhub" if _finnhub_available() else "reddit_x"

    has_finnhub = provider == "finnhub" and _finnhub_available()
    has_reddit_oauth = _reddit_oauth_available()
    has_x = args.use_x and _tweepy_available()
    has_any_api = has_finnhub or (
        provider == "reddit_x"
        and (has_reddit_oauth or has_x or args.public_reddit)
    )

    if provider == "finnhub" and not _finnhub_available():
        print(
            "  ℹ Finnhub: set FINNHUB_API_KEY in `.env` (free registration at https://finnhub.io/register).",
            file=sys.stderr,
        )
        has_any_api = False
    elif provider == "reddit_x":
        if not has_reddit_oauth and not args.public_reddit:
            print(
                "  ℹ Reddit legacy: set REDDIT_* in `.env` or pass --public-reddit.",
                file=sys.stderr,
            )
        if not args.use_x:
            print(
                "  ℹ X/Twitter skipped (default). Pass --use-x only if you accept API charges.",
                file=sys.stderr,
            )
        elif not _tweepy_available():
            print("  ℹ X: install tweepy and set TWITTER_BEARER_TOKEN for --use-x.", file=sys.stderr)

    print(f"  Provider: {provider}", file=sys.stderr)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows: list[dict[str, Any]] = []

    for ticker in tickers:
        print(f"  Scanning {ticker}…", file=sys.stderr)

        if provider == "finnhub":
            fd = _finnhub_sentiment(ticker)
            rows.append({
                "ticker": ticker,
                "source": "finnhub",
                "finnhub_symbol": fd["finnhub_symbol"],
                "reddit_mentions_7d": fd["reddit_mentions_7d"],
                "reddit_bull_pct": fd["reddit_bull_pct"],
                "reddit_bear_pct": fd["reddit_bear_pct"],
                "reddit_signal": fd["reddit_signal"],
                "x_mentions_7d": fd["x_mentions_7d"],
                "x_signal": fd["x_signal"],
                "combined_signal": fd["combined_signal"],
                "last_updated": ts,
            })
            time.sleep(0.35)
            continue

        rd = _reddit_sentiment_combined(ticker, allow_public_reddit=args.public_reddit)
        if has_x:
            xd = _x_sentiment(ticker)
        else:
            xd = _x_na()

        rows.append({
            "ticker": ticker,
            "source": "reddit_x",
            "finnhub_symbol": "",
            "reddit_mentions_7d": rd["mentions"],
            "reddit_bull_pct": rd["bull_pct"],
            "reddit_bear_pct": rd["bear_pct"],
            "reddit_signal": rd["signal"],
            "x_mentions_7d": xd["mentions"],
            "x_signal": xd["signal"],
            "combined_signal": _combined_signal(rd["signal"], xd["signal"]),
            "last_updated": ts,
        })

    if args.csv:
        _write_csv(rows, Path(args.csv))
    if args.html:
        html = _build_html(rows, ts, has_any_api, provider)
        _write_html(html, Path(args.html))

    for r in rows:
        print(
            f"  {r['ticker']}: [{r.get('source', '?')}] reddit={r['reddit_signal']} "
            f"x={r['x_signal']} → {r['combined_signal']}"
        )


if __name__ == "__main__":
    main()
