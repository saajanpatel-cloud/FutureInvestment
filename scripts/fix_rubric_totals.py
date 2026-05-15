#!/usr/bin/env python3
"""
Recalculate rubric totals using: G + M + BS + D + V − T
where T = tail risks (higher is worse — subtracted from the sum).

Also applies s-high class for total >= 18, s-low for total <= 8.
"""
import re
from pathlib import Path

HTML_PATH = Path(__file__).resolve().parent.parent / "research" / "watchlists" / "SINGLE_SCREEN_REPORT.html"

ROW_RE = re.compile(
    r'(<tr data-theme="[^"]+">)'
    r'(<td>[^<]*</td>)'     # theme
    r'(<td>[^<]*</td>)'     # ticker
    r'<td>(\d+)</td>'       # growth
    r'<td>(\d+)</td>'       # margins
    r'<td>(\d+)</td>'       # balance sheet
    r'<td>(\d+)</td>'       # durability
    r'<td>(\d+)</td>'       # tail risks
    r'<td>(\d+)</td>'       # valuation
    r'<td[^>]*>[^<]*</td>'  # old total (with possible class)
    r'(<td>[^<]*</td>)'     # note
    r'</tr>'
)

def fix_row(m):
    tr_open = m.group(1)
    theme_td = m.group(2)
    ticker_td = m.group(3)
    g = int(m.group(4))
    margins = int(m.group(5))
    bs = int(m.group(6))
    dur = int(m.group(7))
    tail = int(m.group(8))
    val = int(m.group(9))
    note_td = m.group(10)

    total = g + margins + bs + dur + val - tail

    if total >= 18:
        total_td = f'<td class="s-high">{total}</td>'
    elif total <= 8:
        total_td = f'<td class="s-low">{total}</td>'
    else:
        total_td = f'<td>{total}</td>'

    return (f'{tr_open}{theme_td}{ticker_td}'
            f'<td>{g}</td><td>{margins}</td><td>{bs}</td>'
            f'<td>{dur}</td><td>{tail}</td><td>{val}</td>'
            f'{total_td}{note_td}</tr>')

def main():
    html = HTML_PATH.read_text()
    new_html, count = ROW_RE.subn(fix_row, html)
    print(f"Updated {count} rubric rows")

    old_totals = [int(x) for x in re.findall(r'<td[^>]*>(\d+)</td><td>[^<]*</td></tr>', html)]
    new_totals = [int(x) for x in re.findall(r'<td[^>]*>(\d+)</td><td>[^<]*</td></tr>', new_html)]

    if old_totals and new_totals:
        changes = sum(1 for a, b in zip(old_totals, new_totals) if a != b)
        print(f"  {changes} totals changed")
        for i, (old, new) in enumerate(zip(old_totals, new_totals)):
            if old != new:
                print(f"    Row {i+1}: {old} → {new}")

    HTML_PATH.write_text(new_html)
    print("Done.")

if __name__ == "__main__":
    main()
