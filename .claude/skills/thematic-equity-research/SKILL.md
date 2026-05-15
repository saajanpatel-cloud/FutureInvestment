---
name: thematic-equity-research
description: Multi-sector latent-demand equity research workflow (tech, healthcare, energy, space), optional Finnhub market context, mandatory adversarial bear-case pass before top-pick labels. Education and research only, not personalized investment advice.
---

# Thematic equity research (FutureInvestment)

## Legal and epistemic disclaimer

- **Not personalized investment advice.** No guarantee of returns. No promise to find the "next" multi-bagger.
- Outputs are **research and education** for **your** due diligence. You are responsible for verification, jurisdiction, and decisions.
- Models can **hallucinate** citations. Treat every forward-looking factual claim as **unverified** until you confirm primary sources.

When this skill applies, **state the disclaimer once** at the start of substantive outputs.

### Communication style

All outputs from this skill — memos, one-pagers, adversarial packs, watchlists, and chat replies — must follow these rules:

- **Keep it short.** Say what matters; cut padding and filler.
- **Use simple language.** Plain words over finance jargon. When a technical term is unavoidable, define it in context on first use.
- **Build up progressively.** Lead with the core idea in plain terms, then layer in data points, nuance, and edge cases. Never front-load dense jargon or acronym chains.
- **Tables and bullets over paragraphs** when presenting data or comparisons.

### UK residents (execution checklist, not advice)

Before acting on any ticker list, confirm **your** constraints with a qualified professional if needed:

- [ ] **FCA-regulated broker** (or equivalent) actually offers the **ticker, venue, and wrapper** (ISA, SIPP, GIA) you intend.
- [ ] **US-listed names:** W-8BEN / withholding and **FX** costs understood; some products (certain non-UCITS funds) are awkward for UK retail.
- [ ] **Liquidity and stamp** considerations for UK listings where applicable.

The skill does **not** verify broker availability per row.

---

## When to use this skill

Use when the user wants to:

- Scan **multi-sector** themes (technology, healthcare, energy, space, cross-cutting materials).
- Stress-test **latent demand**: real-world needs **before** full commercial inflection.
- Map themes to **public** equities including **picks-and-shovels** (components, services, tooling).
- Layer **optional** forum/social context (never primary).
- Produce **ranked candidates** only after a mandatory **expert adversarial** pass.

---

## Operating principles

1. **Order matters:** latent-demand memo for the theme **then** company linkage **then** fundamentals snapshot **then** optional market context **then** adversarial pack. Never label **top pick** without the adversarial pack.
2. **Separate growth from valuation:** High growth can pair with fatal valuation or dilution; score them independently.
3. **Evidence ladder:** Tag sources **hard** vs **soft**; label unknowns explicitly.
4. **Sentiment is secondary:** Use for anomalies and jargon; pair with **counter-thesis** when extreme.
5. **Kill criteria:** Every serious candidate needs observable **kill** triggers and dates where possible.

---

## Future Impact baseline (optional)

When the user references **Future Impact** or the personalised UK satellite sleeve:

1. Read **`research/sources/future-impact/BASELINE.md`** first for: **£7,500 max**, **drip** deployment, **theme weights** (no standalone climate/water or fintech row; cyber and automation at **10%** each; AI infra **32.5%**; energy/grid **27.5%**; Health Tech **10%**; quantum **10%**), **seed-ticker philosophy** (PDF lists and quantum names are starting points only—full analysis and modelling before conviction; widen search if suboptimal).
2. PDFs in the same folder are **archival**—cite or pull specific claims; do not paste entire PDFs into chat each session.
3. Keep Workflow order: **A → linkage → snapshot → optional D → E** before any **top pick** label.
4. For **implementation** asks, include **trade log** fields and **quarterly** mapping to **INVEST / HOLD / REDUCE / SELL** as in `BASELINE.md` / implementation PDF.

### Concise delivery default

Write **full** memos, one-pagers, and adversarial packs to **`research/memoes/`** and **`research/watchlists/`**. In chat, default to an **executive summary**, **file paths**, and **next actions** unless the user explicitly asks for the full text in the message.

Suggested outputs live under project paths (create if missing):

- `research/memoes/` for pillar or theme memos
- `research/watchlists/` for dated shortlists and change logs
- `scripts/` Phase 2 helpers: indicative fundamentals CSV/Markdown (`fi_snapshot.py` with `--manifest research/watchlists/universe_manifest.csv` for the 70-name sleeve list, includes **CIK / SEC EDGAR URL** when available), HTML row generators and **`refresh_watchlists.sh`** (runs the full sleeve → core → enrich → embed pipeline and **`fi_verify_watchlist_refresh.py`** at the end). Do **not** tell the user to run these manually when they ask for a watchlist/dashboard update—the agent runs `./scripts/refresh_watchlists.sh` from repo root and reports verifier output. **Dashboard tone, DCF patch order, shortlist anchors, and scope limits** live in project `.claude/CLAUDE.md` → *Dashboard & document playbook*. Optional paste-based mention counts (`fi_mentions.py --manifest …`), full run Markdown scaffold (`fi_report_scaffold.py --manifest …`); same file for full command list.
- `watchlist-ui/` static dashboard: load/export `watchlist.json` for ranked names, notes, and secondary `market_context` fields.

---

## Pillar taxonomy (maintain parallel trees)

For each pillar, maintain sub-themes with the same rubric: **bottlenecks**, **who captures margin**, **regulatory sensitivity**, **typical failure modes**.

| Pillar | Examples of sub-themes |
|--------|------------------------|
| **Technology / frontier compute** | AI infrastructure; quantum (hardware, control, cryogenics, materials, error-correction software); novel compute (photonics, neuromorphic where relevant); advanced packaging/interconnect; precision manufacturing/test; robotics/autonomy; climate hardware overlapping industry |
| **Health Tech** | Robotic surgery; AI diagnostics; biotech pipelines (GLP-1, gene therapy, oncology); structural heart devices; **payer and regulatory pathway** as first-class risks |
| **Energy / power / transition** | Grid and interconnect; storage; nuclear fuel cycle where investable locally; LNG/molecules; field services and equipment; **utility/regulator** dynamics |
| **Space / aerospace (defense-adjacent)** | Launch and ground; buses/payloads; components/materials; EO and connectivity models; prime concentration and geopolitics |
| **Cross-cutting materials and logistics** | Specialty chemicals, gases, advanced materials; tag **multi-sector overlap** |

**Picks-and-shovels (all pillars):** Map **components, services, tooling** one to two tiers from the headline product (cryogenics, magnets, sensors, single-use bioprocess, purification, transformers/HVDC, rad-hard parts and test, etc.).

---

## Workflow A: Pillar latent-demand memo

Produce one memo per active theme **before** ticker mapping.

### Prompt checklist (answer every item)

1. **Problem statement:** Who hurts today? Why do substitutes fail (cost, safety, density, latency, carbon, reliability, scale)?
2. **Evidence ladder:** List bullets tagged **[hard]** or **[soft]** with **full citation**: title, publisher, date, URL if public.
3. **Why now / why not yet:** What changed vs what still blocks wallets opening?
4. **Inflection triggers:** Positive observables that mean demand is kicking in; **negative** triggers (policy repeal, substitute breakthrough).
5. **Second-best outcomes:** If the headline tech/product fails, what satisfies the **same underlying need**?
6. **Unknowns / not found:** Explicit gaps (no speculation disguised as fact).

---

## Workflow B: Optional research allocation worksheet (not advice)

Discipline research **time** or **watchlist slots** across pillars to avoid accidental single-sector obsession.

```
Pillar                          Target slots or hours (research only)
Technology                     ___
Healthcare                     ___
Energy                         ___
Space                          ___
Cross-cutting                  ___
Notes                          ___
```

---

## Workflow C: Company one-pager (per ticker)

Fill **before** adversarial pass.

### Identity

- **Ticker / listing / currency**
- **Pillar(s)** and **multi-sector overlap** tags

### Exposure

- **Pure play vs conglomerate segment**; approximate **attributable revenue** if inferrable from segments (cite filing/KPI source).

### Thesis

- **One paragraph bull thesis** tied to **specific latent inflection** from Workflow A.

### Linkage

- **Mechanism:** Why **this** company captures value for **this** need (SKU, segment, customer type, BOM attachment). If linkage is weak: flag **theme-only / watch**.

### Falsifiers (2 to 3)

- Observable statements that would invalidate the thesis.

### Metrics snapshot (indicative)

Fill what you have; cite source and date:

| Field | Value | Source date |
|-------|-------|-------------|
| Revenue growth (TTM YoY or trend) | | |
| Gross margin trend | | |
| R&D as % revenue | | |
| Net leverage / liquidity proxy | | |
| Dilution / SBC note | | |
| Geographic / customer concentration | | |

### Growth vs valuation

- **Narrative growth drivers** vs **valuation concern** (separate bullets; no automatic "cheap good / expensive bad").

### Scoring rubric (transparent, qualitative)

Score each dimension **1 to 5** (or label **L / M / H**) with **one evidence bullet** per cell. **Do not** multiply into a single hype score unless you freeze the methodology in writing.

| Dimension | Question | Score | Evidence (dated, citable) |
|-----------|----------|-------|---------------------------|
| **Growth momentum** | Is revenue (or relevant KPI) inflecting or durable vs one-offs? | | |
| **Margin and cash quality** | Gross margin path, operating leverage, FCF conversion caveats | | |
| **Balance sheet** | Leverage, liquidity, refinancing, covenant risk | | |
| **Competitive durability** | Moat vs commodity risk; customer lock-in; switching costs | | |
| **Tail risks** | Regulation, concentration, geo, technology obsolescence | | |
| **Valuation vs growth** | Separated: expensive can be fine; cheap can be a trap | | |

**Composite:** Narrative summary only (no hidden weighting). **Top pick** still requires **Workflow E** regardless of scores.

---

## Source hygiene checklist (forward research)

Before treating a claim as fact:

- [ ] **Primary or authoritative source** (filing, docket, standards body, government statistical release) preferred over blogs.
- [ ] **Citation complete:** title, publisher, **date**, URL when public.
- [ ] **Unknowns / not found** section written where evidence is missing.
- [ ] **Model output** cross-checked for plausible-but-fake citations.
- [ ] **Geography** explicit (US vs EU vs global) when law, payers, or export controls matter.

---

## Workflow D: Market context (optional)

**Default (automated):** Run **`./scripts/refresh_watchlists.sh`** or **`python scripts/fi_finnhub_context.py`** with **`FINNHUB_API_KEY`** in repo-root `.env`. Free-tier Finnhub: analyst recommendation mix, insider MSPR label, recent headline count, earnings timing (`finnhub_context.csv` → `market_context` on core shortlist). **Not retail social sentiment**; not predictive — secondary to fundamentals and adversarial pass.

**Tier 0 (paste):** `fi_mentions.py` on forum text (counts `$TICKER` and bare symbols); manual read for stance.

**Deprecated:** `fi_sentiment.py` (Finnhub `/stock/social-sentiment` is premium; legacy `reddit_x` blocked by Reddit policy / X pay-per-use).

**When market context is used:**

- Append **context appendix:** source (Finnhub), analyst skew, insider MSPR, news volume proxy, next/last earnings hint.
- Add **one paragraph: why context might mislead** (stale insider filings, thin analyst coverage on ADRs/EU listings, headline noise vs fundamentals).

---

## Workflow E: Adversarial thesis review (mandatory for "top pick")

Use **sector personas**: technologist/PM (tech); clinician or payer skeptic (healthcare); utility planner or commodity skeptic (energy); program/integration skeptic (space); regulator; competitor PM as needed.

### Outputs (required)

1. **Steel-manned bear case:** Minimum **4** bullets; each a **concrete** failure mode. **At least one** bullet attacks **timing** (need real, wallets late or never). **At least two** bullets must be **non-obvious** to casual retail readers.
2. **Pre-mortem:** Single sentence: if this is a poor outcome in five years, the **most likely** reason is...
3. **Rebuttal map:** Table mapping **each** bear bullet to (a) **specific rebuttal + evidence type**, or (b) **accepted risk** + mitigation/sizing note. **No** vague "great management."
4. **Kill criteria:** Observable events forcing downgrade/removal from top tier; **date or quarter** where sensible.

### Ranking rule

- **Top pick:** Only if **no unaddressed existential** bear bullets after rebuttal map, and kill criteria are **written**.
- If facts cannot be verified: output **needs primary research**, not **high conviction**.

---

## Workflow F: Portfolio outputs

Deliver:

1. **Ranked watchlist** with **why flagged**.
2. **Disqualified log** with **why rejected** (as important as buys).
3. **Change log** vs prior run when dates apply.

---

## Red flags checklist (manual vigilance)

Use before promoting any name:

- [ ] Liquidity too thin / promotion spikes without fundamentals?
- [ ] Revenue linkage to theme **unprovable** from public disclosures?
- [ ] Customer concentration or geopolitical/export tail risks unaddressed?
- [ ] Accounting or governance smoke signals (non-exhaustive; escalate to specialist)?
- [ ] Thesis rests only on **[soft]** narrative with no **[hard]** hooks?
- [ ] Narrative/hype-driven entry with no expert bear-case completion?

---

## Related skills (optional cross-links)

- OSINT-style **structured** monitoring (not hype trading): `~/.claude/skills/social-media-intelligence/SKILL.md`
- API shortlisting for Phase 2 automation: `~/.claude/skills/free-apis-catalog/SKILL.md`
- Minimal stance file: `~/.claude/skills/investment-advisor/SKILL.md`

---

## Copy-paste: master run prompt

```
Run thematic-equity-research for FutureInvestment.

Pillars to cover this session: [list]
Optional: forum paste for fi_mentions: [none / attach]
Universe constraints: [e.g. US listed, min market cap, ADRs yes/no]

For each pillar:
1) Produce latent-demand memo per Workflow A (citations + unknowns).
2) List 5 to 15 candidate tickers with picks-and-shovels coverage; explain linkages.
3) For each shortlist ticker, complete Workflow C.
4) Optional: Workflow D (Finnhub context or forum paste).
5) For names proposed as "top pick", complete Workflow E in full.

End with watchlist + disqualified log + change notes. Include disclaimer once.
```
