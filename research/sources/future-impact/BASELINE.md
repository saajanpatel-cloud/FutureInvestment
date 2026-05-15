# Future Impact baseline (personalised sleeve)

**Not personalized investment advice.** Education and research only. Verify all facts in filings and primary sources. You are responsible for broker access, ISA/SIPP/GIA eligibility, FX, and tax.

## Canonical sources (this folder)

| File | Role |
|------|------|
| `future-impact-themes-2026.pdf` | Theme framework, real-economy lens, second/third-order beneficiary bias |
| `future-impact-portfolio-implementation-2026-2035.pdf` | Original implementation ideas (trade log, quarterly actions); weights below **override** the PDF where noted |
| `BASELINE.md` (this file) | Machine-readable defaults for agents—read this first on Future Impact runs |

## Sleeve rules (your preferences)

- **Maximum capital:** **£7,500** total into this thematic satellite sleeve (hard cap).
- **Deployment:** **Drip**—many small purchases over time up to the cap (not a single lump deploy).
- **Audience:** UK-based, very high risk tolerance; satellite sleeve, not core capital.
- **Process (from implementation PDF):** trade log per position; **quarterly** review with actions **INVEST / HOLD / REDUCE / SELL**; check theme weights vs table below.

## Theme weights (personalised vs PDF defaults)

- **Omitted:** standalone **climate / water** sleeve bucket (not used as a separate theme line).
- **Omitted:** **Fintech & digital money** — removed; upside judged insufficient vs other themes.
- **Reduced vs PDF:** **Cyber** and **industrial automation & robotics** each **−5 pp** (15% → **10%**).
- **Reallocation:** freed weight redistributed to **AI infrastructure & compute**, **energy transition & grids**, and **quantum / frontier compute**.

| Theme | In simple words | Target % | Approx £ at full £7.5k cap |
|-------|-----------------|----------|----------------------------|
| AI infrastructure & compute | Chips, servers, data centres, and gear that run AI | 32.5% | ~£2,438 |
| Energy transition & grids | Power plants, grids, and kit that keep the lights on as demand rises | 27.5% | ~£2,062 |
| Cybersecurity & digital trust | Software and services that stop hacks and protect data | 10% | ~£750 |
| Industrial automation & robotics | Factories and robots getting more automated | 10% | ~£750 |
| Health Tech | Tech-driven healthcare: robotic surgery, AI diagnostics, biotech pipelines, structural devices | 10% | ~£750 |
| Quantum / frontier compute | Early-stage quantum and "next" compute bets | 10% | ~£750 |
| **Total** | | **100%** | **£7,500 max** |

Position-count band (from PDF spirit): roughly **10–14** names at full deployment, typical lots **£300–£800** in core themes when at cap—adjust as you drip.

## Theme guide (learning — descriptive)

Educational framing only. Use filings and primary sources before acting on any claim.

### 1. AI infrastructure and compute

Large AI workloads need specialised **chips**, **high-bandwidth memory**, **networking inside data centres**, **cooling**, and reliable **power**. Spending plans from big cloud customers create a **multi-year demand signal** for the supply chain—not only the famous platform stocks. Learn to read **segment revenue** and **customer concentration** so you can see how much of a company's sales truly come from AI-related capex versus legacy lines.

### 2. Energy transition and grids

This theme is about **keeping the grid reliable** while demand rises (including from AI data centres): generation (gas, nuclear, renewables), **storage**, **transmission and distribution** equipment, and regulated utilities. A common learning mistake is to confuse **long-run load growth** with **short-run power prices**, which can move for commodity and policy reasons unrelated to your thesis.

### 3. Cybersecurity and digital trust

More cloud and AI means a wider **attack surface** and stricter expectations from boards and regulators. Revenue is often **subscription-based**; compare **net retention**, module adoption, and cash conversion across peers rather than treating "cyber" as one trade.

### 4. Industrial automation and robotics

Factories adopt **robots**, **sensors**, **motion systems**, and **industrial software** for quality, speed, and labour shortages. Orders can be **cyclical**—verify how much revenue is recurring services versus one-time equipment. Overlaps with AI when machine vision and adaptive control use ML at the edge.

### 5. Health Tech

Technology-driven healthcare companies with high growth potential: **robotic surgery** systems, **biotech pipelines** (GLP-1, gene therapy, next-gen oncology), **AI-assisted diagnostics**, and **structural heart devices**. Focus on names where technology creates a step-change in outcomes or efficiency, not steady-state legacy devices or managed care. **Payers and labels** still matter—who pays and under what rules determines economic value alongside clinical efficacy.

### 6. Quantum and frontier compute

**Quantum** remains early for most commercial models; stocks may be **dilution-heavy** with revenue far below narrative. The sleeve's weight reflects **long-dated optionality**. Read runway, revenue quality, and risk factors. Adjacent "frontier" can include control electronics, cryogenics, or software stacks—each with different risk profiles.

### Cross-cutting: space and defence

Not a separate line in your personalised weight table, but often researched alongside automation and geopolitics. **Backlog, dilution, programme delays**, and **customer concentration** are the usual learning checkpoints. Names like **RKLB** sit here.

## Ticker philosophy

- **PDF example tickers** = **seeds / illustration only**. Same for any list in research outputs.
- **Full analysis** required before conviction: fundamentals, linkage to theme, valuation vs peers, risks, optional modelling.
- If current names are **not optimal** after analysis, **expand the search** (screeners, supply chain, adversarial pass)—do not anchor on the first list.

## Quantum / frontier — screen candidates only (not picks)

Treat as **watchlist seeds** for research; verify listing, liquidity, UK access, and thesis in primary sources: **IONQ**, **RGTI**, **QBTS**, **QUBT**, **LAES**, **ARQQ**, **HOLO**.

## Token-efficient runs (session defaults)

- Prefer **this file + file paths** in prompts; do **not** re-ingest full PDFs each session unless you need a specific passage.
- **One pillar or theme per session** when possible; follow-ups = diffs / single-ticker updates.
- Put long memos and Workflow C/E packs under `research/memoes/` and `research/watchlists/`; keep chat to **summary + paths**.
- Use `scripts/fi_snapshot.py` for tables (CSV/MD) instead of regenerating large tables in prose.

## Outputs in repo

- Combined HTML dashboard: `research/watchlists/SINGLE_SCREEN_REPORT.html`
- Markdown scaffolds: `python scripts/fi_report_scaffold.py` (see `.claude/CLAUDE.md`)
