#!/usr/bin/env python3
"""
Generate HTML fragments for Wave 2 international tickers:
  1. Rubric table <tr> rows
  2. Theme card <span class="pill"> elements
  3. <option> elements for chart-ticker picker
  4. JavaScript META object entries
"""
import csv
from pathlib import Path

WATCHLIST_DIR = Path(__file__).resolve().parent.parent / "research" / "watchlists"
RUBRIC_PATH = WATCHLIST_DIR / "rubric_scores.csv"
MANIFEST_PATH = WATCHLIST_DIR / "universe_manifest.csv"

WAVE1_INTL = {"RR.L","NGG","SSE.L","ENR.DE","SU.PA","SIE.DE","ABB","NVO","AZN","GSK"}

THEME_MAP = {
    "ai": "AI infra",
    "energy": "Energy",
    "cyber": "Cyber",
    "auto": "Automation",
    "health": "Health Tech",
    "quantum": "Quantum",
}

THEME_TO_DATA = {
    "ai": "ai",
    "energy": "energy",
    "cyber": "cyber",
    "auto": "auto",
    "health": "health",
    "quantum": "quantum",
}

def load_manifest():
    rows = []
    with open(MANIFEST_PATH) as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) >= 4:
                rows.append({"ticker": row[0], "theme_slug": row[1], "theme_label": row[2], "desc": row[3]})
    return rows

def load_rubric():
    scores = {}
    with open(RUBRIC_PATH) as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) >= 7:
                scores[row[0]] = {
                    "growth": int(row[1]),
                    "margins": int(row[2]),
                    "bs": int(row[3]),
                    "durability": int(row[4]),
                    "tail": int(row[5]),
                    "valuation": int(row[6]),
                }
    return scores

def name_from_desc(desc):
    parts = desc.split(";")[0].split("—")[0].split("–")[0]
    parts = parts.split(" — ")[0].split(" – ")[0]
    for suffix in [" (Xetra)", " (Amsterdam)", " (Brussels)", " (Euronext Paris)",
                   " (Swiss)", " (Oslo)", " (Copenhagen)", " (Madrid)", " (Milan)",
                   " (Lisbon)", " (Helsinki)", " (Stockholm)", " (LSE)", " (NYSE)",
                   " (NYSE ADR)", " (NASDAQ ADR)"]:
        parts = parts.replace(suffix, "")
    return parts.strip()[:50]

def main():
    manifest = load_manifest()
    rubric = load_rubric()

    wave2 = [m for m in manifest if m["ticker"] not in WAVE1_INTL
             and m["ticker"] in rubric
             and any(c in m["ticker"] for c in [".DE",".AS",".PA",".SW",".OL",".BR",
                                                  ".CO",".MC",".MI",".LS",".HE",".ST",".L"])
             or m["ticker"] == "STM"]
    wave2_tickers = {m["ticker"] for m in wave2}
    wave2 = [m for m in manifest if m["ticker"] in wave2_tickers]

    print(f"=== Wave 2 tickers: {len(wave2)} ===\n")

    by_theme = {}
    for m in wave2:
        by_theme.setdefault(m["theme_slug"], []).append(m)

    # 1. Rubric table rows
    print("<!-- ========== RUBRIC TABLE ROWS ========== -->")
    for theme_slug in ["ai","energy","cyber","auto","health","quantum"]:
        tickers = by_theme.get(theme_slug, [])
        if not tickers:
            continue
        print(f"\n<!-- {THEME_MAP.get(theme_slug, theme_slug)} -->")
        for m in tickers:
            t = m["ticker"]
            s = rubric.get(t, {})
            if not s:
                continue
            total = (s["growth"] + s["margins"] + s["bs"] + s["durability"] + s["tail"] + s["valuation"]) / 6
            name = name_from_desc(m["desc"])
            data_theme = THEME_TO_DATA[theme_slug]
            print(f'            <tr data-theme="{data_theme}"><td>{t}</td><td>{name}</td>'
                  f'<td>{s["growth"]}</td><td>{s["margins"]}</td><td>{s["bs"]}</td>'
                  f'<td>{s["durability"]}</td><td>{s["tail"]}</td><td>{s["valuation"]}</td>'
                  f'<td>{total:.1f}</td></tr>')

    # 2. Theme card pills
    print("\n\n<!-- ========== THEME CARD PILLS ========== -->")
    for theme_slug in ["ai","energy","cyber","auto","health","quantum"]:
        tickers = by_theme.get(theme_slug, [])
        if not tickers:
            continue
        print(f"\n<!-- {THEME_MAP.get(theme_slug, theme_slug)} pills -->")
        pills = " ".join(f'<span class="pill">{m["ticker"]}</span>' for m in tickers)
        print(pills)

    # 3. Chart ticker options
    print("\n\n<!-- ========== CHART TICKER OPTIONS ========== -->")
    for m in sorted(wave2, key=lambda x: x["ticker"]):
        name = name_from_desc(m["desc"])
        print(f'              <option value="{m["ticker"]}">{m["ticker"]} – {name}</option>')

    # 4. JS META entries
    print("\n\n// ========== JS META ENTRIES ==========")
    for m in sorted(wave2, key=lambda x: x["ticker"]):
        name = name_from_desc(m["desc"])
        theme = THEME_MAP.get(m["theme_slug"], m["theme_slug"])
        print(f'  "{m["ticker"]}": {{name:"{name}",theme:"{theme}"}},')

    # 5. Summary
    print(f"\n// Total wave 2: {len(wave2)} tickers")
    for ts in ["ai","energy","cyber","auto","health","quantum"]:
        count = len(by_theme.get(ts, []))
        print(f"//   {THEME_MAP.get(ts, ts)}: {count}")

if __name__ == "__main__":
    main()
