#!/usr/bin/env python3
"""
Expand universe_manifest to TARGET_SCREEN rows with model_tier (full | screen_only).

- First MODEL_CAP rows in manifest order: model_tier=full (universe valuation pass)
- Remainder: screen_only (snapshot + earnings + rubric only)
- Merges curated additions from fi_double_universe, fi_add_defense_space_wave, and WAVE_500

Run once before refresh: python3 scripts/fi_setup_universe_tiers.py

Not investment advice.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAN = ROOT / "research" / "watchlists" / "universe_manifest.csv"
RUB = ROOT / "research" / "watchlists" / "rubric_scores.csv"
CAND = ROOT / "research" / "watchlists" / "candidates.csv"

TARGET_SCREEN = 500
MODEL_CAP = 350
NOTE = "Placeholder rubric — refresh after earnings pull on next watchlist refresh."

from fi_double_universe import ADDITIONS as WAVE1  # noqa: E402
from fi_add_defense_space_wave import ADDITIONS as WAVE2  # noqa: E402

# Extra screen names to reach ~500 when waves are mostly absorbed
WAVE_500: list[tuple[str, str, str, str]] = [
    ("INTC", "ai", "AI infra & compute", "CPU and foundry turnaround — AI PC and custom silicon option"),
    ("IBM", "ai", "AI infra & compute", "Enterprise AI and hybrid cloud — watsonx platform"),
    ("ORCL", "ai", "AI infra & compute", "OCI GPU cloud and database AI workloads"),
    ("CRM", "ai", "AI infra & compute", "Enterprise AI agents on CRM data cloud"),
    ("NOW", "cyber", "Cybersecurity & digital trust", "Workflow automation with security and AI modules"),
    ("ADBE", "ai", "AI infra & compute", "Creative and document AI — Firefly monetisation"),
    ("INTU", "fintech", "Fintech & digital money", "SMB tax and accounting AI assistants"),
    ("PYPL", "fintech", "Fintech & digital money", "Payments scale — margin and take-rate recovery"),
    ("SQ", "fintech", "Fintech & digital money", "Block — seller ecosystem and bitcoin optionality"),
    ("COIN", "fintech", "Fintech & digital money", "Crypto exchange — regulatory and volume cyclicality"),
    ("HOOD", "fintech", "Fintech & digital money", "Retail brokerage and crypto trading"),
    ("AFRM", "fintech", "Fintech & digital money", "BNPL — credit loss and funding cost sensitivity"),
    ("SOFI", "fintech", "Fintech & digital money", "Digital bank — member growth and NIM"),
    ("NU", "fintech", "Fintech & digital money", "LatAm neobank — Brazil and Mexico expansion"),
    ("MELI", "fintech", "Fintech & digital money", "MercadoLibre — commerce and fintech flywheel"),
    ("CPNG", "fintech", "Fintech & digital money", "Korea e-commerce — logistics and margin path"),
    ("SE", "fintech", "Fintech & digital money", "Sea Limited — gaming and Shopee fintech"),
    ("BABA", "ai", "AI infra & compute", "China cloud and commerce — regulatory overhang"),
    ("PDD", "ai", "AI infra & compute", "Temur — cross-border commerce growth"),
    ("JD", "fintech", "Fintech & digital money", "China retail logistics and health spin"),
    ("NFLX", "ai", "AI infra & compute", "Streaming — content ROI and ad tier"),
    ("DIS", "ai", "AI infra & compute", "Media parks and streaming — ESPN option"),
    ("CMCSA", "cyber", "Cybersecurity & digital trust", "Cable broadband — capital return focus"),
    ("T", "cyber", "Cybersecurity & digital trust", "Telco — fibre and wireless cash flow"),
    ("VZ", "cyber", "Cybersecurity & digital trust", "Wireless duopoly — dividend yield play"),
    ("TMUS", "cyber", "Cybersecurity & digital trust", "US wireless share gains — integration synergies"),
    ("DE", "auto", "Industrial automation & robotics", "Agricultural equipment cycle and precision ag"),
    ("CAT", "auto", "Industrial automation & robotics", "Construction and mining equipment — infra cycle"),
    ("EMR", "auto", "Industrial automation & robotics", "Automation and climate technologies portfolio"),
    ("ROK", "auto", "Industrial automation & robotics", "Factory automation — Logix and software mix"),
    ("ITW", "auto", "Industrial automation & robotics", "Industrial conglomerate — auto and welding niches"),
    ("ETN", "energy", "Energy transition & grids", "Electrical equipment — data centre power chain"),
    ("HON", "auto", "Industrial automation & robotics", "Aerospace and building automation"),
    ("MMM", "auto", "Industrial automation & robotics", "Industrial materials — litigation and spin focus"),
    ("PH", "auto", "Industrial automation & robotics", "Motion and control — aerospace and industrial"),
    ("CARR", "energy", "Energy transition & grids", "HVAC and refrigeration — heat pump tailwind"),
    ("JCI", "energy", "Energy transition & grids", "Building controls and fire — services mix"),
    ("TT", "energy", "Energy transition & grids", "Trane — commercial HVAC and data centre cooling"),
    ("LMT", "auto", "Industrial automation & robotics", "Defense prime — backlog and F-35"),
    ("RTX", "auto", "Industrial automation & robotics", "Aerospace engines and defense"),
    ("NOC", "auto", "Industrial automation & robotics", "Defense systems and space"),
    ("GD", "auto", "Industrial automation & robotics", "Submarines and Gulfstream — defense steady state"),
    ("ISRG", "health", "Healthcare innovation & AI in medicine", "da Vinci robotic surgery installed base"),
    ("MDT", "health", "Healthcare innovation & AI in medicine", "Medtech diversified — GLP-1 device adjacency"),
    ("ABT", "health", "Healthcare innovation & AI in medicine", "Diagnostics and devices — Libre growth"),
    ("BSX", "health", "Healthcare innovation & AI in medicine", "Cardiovascular devices — Watchman and EP"),
    ("ELV", "health", "Healthcare innovation & AI in medicine", "Managed care — Medicare Advantage utilisation"),
    ("UNH", "health", "Healthcare innovation & AI in medicine", "Optum services scale — regulatory risk"),
    ("CI", "health", "Healthcare innovation & AI in medicine", "Cigna — pharmacy and commercial mix"),
    ("HUM", "health", "Healthcare innovation & AI in medicine", "Medicare Advantage — star ratings and MLR"),
    ("PFE", "health", "Healthcare innovation & AI in medicine", "Pharma — patent cliff and pipeline refill"),
    ("LLY", "health", "Healthcare innovation & AI in medicine", "GLP-1 franchise — supply and oral follow-on"),
    ("NVO", "health", "Healthcare innovation & AI in medicine", "Ozempic/Wegovy — obesity TAM"),
    ("AZN", "health", "Healthcare innovation & AI in medicine", "Oncology and rare disease — ADC pipeline"),
    ("SNY", "health", "Healthcare innovation & AI in medicine", "Vaccines and immunology — Dupixent partner"),
    ("NVS", "health", "Healthcare innovation & AI in medicine", "Radioligand and neuroscience pipeline"),
    ("BMY", "health", "Healthcare innovation & AI in medicine", "Oncology IO — patent cliffs and M&A"),
    ("GILD", "health", "Healthcare innovation & AI in medicine", "HIV and liver — cell therapy option"),
    ("BIIB", "health", "Healthcare innovation & AI in medicine", "Neuro — Alzheimer's and MS portfolio"),
    ("VRTX", "health", "Healthcare innovation & AI in medicine", "CF franchise — pain and kidney pipeline"),
    ("ILMN", "health", "Healthcare innovation & AI in medicine", "Genomics tools — clinical and research demand"),
    ("A", "health", "Healthcare innovation & AI in medicine", "Agilent — lab instruments and diagnostics"),
    ("TMO", "health", "Healthcare innovation & AI in medicine", "Life science tools — bioprocessing and CRO"),
    ("DHR", "health", "Healthcare innovation & AI in medicine", "Diagnostics and life sciences — spin and M&A"),
    ("WAT", "health", "Healthcare innovation & AI in medicine", "Waters — biologics QA and LC-MS"),
    ("BRK-B", "fintech", "Fintech & digital money", "Conglomerate — insurance float and industrials"),
    ("JPM", "fintech", "Fintech & digital money", "Money centre bank — NII and investment banking"),
    ("BAC", "fintech", "Fintech & digital money", "Consumer and commercial bank — rate sensitivity"),
    ("WFC", "fintech", "Fintech & digital money", "Retail bank turnaround — expense and asset cap"),
    ("GS", "fintech", "Fintech & digital money", "Investment bank — trading and advisory cycle"),
    ("MS", "fintech", "Fintech & digital money", "Wealth management — AUM and banking"),
    ("BLK", "fintech", "Fintech & digital money", "Asset management — ETF and aladdin platform"),
    ("SCHW", "fintech", "Fintech & digital money", "Retail brokerage — rate on cash balances"),
    ("ICE", "fintech", "Fintech & digital money", "Exchanges and data — mortgage tech"),
    ("CME", "fintech", "Fintech & digital money", "Derivatives clearing — vol and rates volume"),
    ("SPGI", "fintech", "Fintech & digital money", "Ratings and market data — Mobility spin"),
    ("MCO", "fintech", "Fintech & digital money", "Moody's — ratings cycle and KYC analytics"),
    ("MSCI", "fintech", "Fintech & digital money", "Indexes and ESG analytics — subscription model"),
    ("FIS", "fintech", "Fintech & digital money", "Banking and capital markets technology"),
    ("FI", "fintech", "Fintech & digital money", "Fiserv — merchant acquiring and issuer processing"),
    ("GPN", "fintech", "Fintech & digital money", "Global Payments — Genius and B2B software"),
    ("ADYEN", "fintech", "Fintech & digital money", "Adyen — unified commerce payments EU"),
    ("WISE", "fintech", "Fintech & digital money", "Wise — cross-border transfers and hold"),
    ("DASH", "fintech", "Fintech & digital money", "DoorDash — delivery take-rate and ads"),
    ("UBER", "fintech", "Fintech & digital money", "Mobility and delivery — profitability and autonomy"),
    ("ABNB", "fintech", "Fintech & digital money", "Travel marketplace — supply and regulation"),
    ("BKNG", "fintech", "Fintech & digital money", "Online travel — take rate and alternative accommodation"),
    ("EXPE", "fintech", "Fintech & digital money", "OTA — B2B and loyalty recovery"),
    ("MAR", "fintech", "Fintech & digital money", "Hotel franchisor — net rooms growth"),
    ("HLT", "fintech", "Fintech & digital money", "Premium hotels — fee stream and pipeline"),
    ("RCL", "fintech", "Fintech & digital money", "Cruise — pricing power post-pandemic"),
    ("CCL", "fintech", "Fintech & digital money", "Cruise recovery — leverage and yields"),
    ("DAL", "fintech", "Fintech & digital money", "Airline — corporate travel and fleet"),
    ("UAL", "fintech", "Fintech & digital money", "Airline — transatlantic and Pacific mix"),
    ("LUV", "fintech", "Fintech & digital money", "Domestic leisure airline — cost advantage"),
    ("UPS", "auto", "Industrial automation & robotics", "Parcel logistics — yield and union contract"),
    ("FDX", "auto", "Industrial automation & robotics", "Express and freight — DRIVE cost program"),
    ("UNP", "auto", "Industrial automation & robotics", "Western US rail — pricing and efficiency"),
    ("CSX", "auto", "Industrial automation & robotics", "Eastern rail — industrial and intermodal"),
    ("NSC", "auto", "Industrial automation & robotics", "East coast rail — service recovery"),
    ("CP", "auto", "Industrial automation & robotics", "Canadian Pacific Kansas City merger synergies"),
    ("CNI", "auto", "Industrial automation & robotics", "Canadian National — precision railroading"),
    ("WM", "energy", "Energy transition & grids", "Waste — landfill gas and recycling"),
    ("RSG", "energy", "Energy transition & grids", "Waste collection pricing — route density"),
    ("AWK", "energy", "Energy transition & grids", "Regulated water utility — rate base growth"),
    ("WTRG", "energy", "Energy transition & grids", "Essential utilities — water and gas"),
    ("AEP", "energy", "Energy transition & grids", "Regulated utility — transmission investment"),
    ("D", "energy", "Energy transition & grids", "Dominion — Virginia data centre load"),
    ("EXC", "energy", "Energy transition & grids", "Nuclear-heavy utility — PJM capacity"),
    ("ED", "energy", "Energy transition & grids", "NYC utility — underground grid"),
    ("ES", "energy", "Energy transition & grids", "New England utility — offshore wind stakes"),
    ("FE", "energy", "Energy transition & grids", "Midwest utility — data centre interconnection"),
    ("PPL", "energy", "Energy transition & grids", "Kentucky and Pennsylvania wires"),
    ("EIX", "energy", "Energy transition & grids", "California utility — wildfire mitigation"),
    ("PCG", "energy", "Energy transition & grids", "PG&E — California load and safety"),
    ("SRE", "energy", "Energy transition & grids", "Sempra — LNG and California utilities"),
    ("WMB", "energy", "Energy transition & grids", "Gas pipelines — data centre power gas"),
    ("KMI", "energy", "Energy transition & grids", "Midstream — fee-based cash flows"),
    ("OKE", "energy", "Energy transition & grids", "NGL gathering — Permian volumes"),
    ("WES", "energy", "Energy transition & grids", "Western Midstream — Permian G&P"),
    ("MPLX", "energy", "Energy transition & grids", "Marathon midstream — dropdown MLP"),
    ("EPD", "energy", "Energy transition & grids", "MLP — NGL exports and storage"),
    ("SLB", "energy", "Energy transition & grids", "Oilfield services — international and digital"),
    ("HAL", "energy", "Energy transition & grids", "North America fracturing cycle"),
    ("BKR", "energy", "Energy transition & grids", "LNG equipment and OFS diversification"),
    ("OXY", "energy", "Energy transition & grids", "Permian E&P — Berkshire stake and CCUS"),
    ("DVN", "energy", "Energy transition & grids", "Shale E&P — dividend and buybacks"),
    ("HES", "energy", "Energy transition & grids", "Guyana growth — Chevron merger"),
    ("COP", "energy", "Energy transition & grids", "Lower 48 and LNG — capital discipline"),
    ("BP", "energy", "Energy transition & grids", "Integrated oil — transition spend and yield"),
    ("SHEL", "energy", "Energy transition & grids", "LNG and chemicals — capital framework"),
    ("TTE", "energy", "Energy transition & grids", "European major — LNG and renewables"),
    ("EQNR", "energy", "Energy transition & grids", "Norway state oil — dividend policy"),
    ("SU", "energy", "Energy transition & grids", "Canadian integrated — oil sands and refining"),
    ("IMO", "energy", "Energy transition & grids", "Canadian refining and upstream"),
    ("ENB", "energy", "Energy transition & grids", "Canadian midstream — Mainline tolls"),
    ("TRP", "energy", "Energy transition & grids", "Gas pipelines and power — Bruce Power"),
    ("FTI", "energy", "Energy transition & grids", "Subsea — offshore wind and oil"),
    ("NOV", "energy", "Energy transition & grids", "Offshore rig equipment — cycle leverage"),
    ("RIG", "energy", "Energy transition & grids", "Offshore drilling — day rates"),
    ("VAL", "energy", "Energy transition & grids", "Offshore drilling — fleet quality"),
    ("BE", "energy", "Energy transition & grids", "Bloom Energy — fuel cells for data centres"),
    ("PLUG", "energy", "Energy transition & grids", "Hydrogen — cash burn and green H2"),
    ("FCEL", "energy", "Energy transition & grids", "Fuel cells — stationary power niche"),
    ("RUN", "energy", "Energy transition & grids", "Residential solar — loan and attach"),
    ("SEDG", "energy", "Energy transition & grids", "Solar inverters — inventory and competition"),
    ("STEM", "energy", "Energy transition & grids", "Battery storage software — project finance"),
    ("QS", "quantum", "Quantum / frontier compute", "Solid-state battery — technical milestone risk"),
    ("SLDP", "quantum", "Quantum / frontier compute", "Solid-state battery developer"),
    ("DNA", "quantum", "Quantum / frontier compute", "Ginkgo — synthetic biology platform"),
    ("TWST", "quantum", "Quantum / frontier compute", "Twist Bioscience — DNA synthesis"),
    ("PACB", "quantum", "Quantum / frontier compute", "Long-read sequencing — competitive pressure"),
    ("NTLA", "quantum", "Quantum / frontier compute", "CRISPR gene editing — in vivo programs"),
    ("CRSP", "quantum", "Quantum / frontier compute", "CRISPR — sickle cell and oncology"),
    ("BEAM", "quantum", "Quantum / frontier compute", "Base editing — delivery and pipeline"),
    ("EDIT", "quantum", "Quantum / frontier compute", "Gene editing — ocular and liver"),
    ("VERV", "quantum", "Quantum / frontier compute", "Cardiovascular gene editing"),
    ("RXRX", "quantum", "Quantum / frontier compute", "Recursion — AI drug discovery platform"),
    ("SDGR", "quantum", "Quantum / frontier compute", "Schrodinger — physics-based drug design"),
    ("SAP", "cyber", "Cybersecurity & digital trust", "Enterprise ERP and cloud — European software"),
    ("SHOP", "fintech", "Fintech & digital money", "Commerce platform — merchant solutions"),
    ("SNOW", "ai", "AI infra & compute", "Data cloud — consumption growth"),
    ("DDOG", "cyber", "Cybersecurity & digital trust", "Observability — cloud monitoring"),
    ("MDB", "ai", "AI infra & compute", "MongoDB — document database for apps"),
    ("TEAM", "cyber", "Cybersecurity & digital trust", "Atlassian — dev collaboration software"),
    ("WDAY", "cyber", "Cybersecurity & digital trust", "HR and finance cloud"),
    ("VEEV", "health", "Healthcare innovation & AI in medicine", "Life sciences cloud — vault CRM"),
    ("ZS", "cyber", "Cybersecurity & digital trust", "Zero trust access — already in sleeve check"),
    ("HUBS", "cyber", "Cybersecurity & digital trust", "HubSpot — SMB CRM and marketing"),
    ("TTD", "ai", "AI infra & compute", "Programmatic ads — CTV growth"),
    ("APP", "ai", "AI infra & compute", "AppLovin — mobile ad tech and AI"),
    ("U", "ai", "AI infra & compute", "Unity — game engine and ads"),
    ("RBLX", "ai", "AI infra & compute", "Roblox — UGC platform engagement"),
    ("EA", "ai", "AI infra & compute", "Video games — live services"),
    ("TTWO", "ai", "AI infra & compute", "Take-Two — GTA pipeline"),
    ("SONY", "ai", "AI infra & compute", "Sony — gaming and sensors"),
    ("6758.T", "ai", "AI infra & compute", "Sony Japan listing — verify local ticker"),
    ("005930.KS", "ai", "AI infra & compute", "Samsung — memory and foundry"),
    ("ASML", "ai", "AI infra & compute", "EUV lithography monopoly"),
    ("STM", "ai", "AI infra & compute", "European semiconductor diversified"),
    ("IFX.DE", "ai", "AI infra & compute", "Infineon — auto and power semis"),
    ("ENR.DE", "energy", "Energy transition & grids", "Siemens Energy — grid and gas turbines"),
    ("RWE.DE", "energy", "Energy transition & grids", "German utility — renewables pipeline"),
    ("IBE.MC", "energy", "Energy transition & grids", "Iberdrola — renewables utility"),
    ("ORSTED.CO", "energy", "Energy transition & grids", "Offshore wind developer"),
    ("VWS.CO", "energy", "Energy transition & grids", "Vestas — wind turbines"),
    ("NGG", "energy", "Energy transition & grids", "National Grid — UK/US wires"),
    ("SSE.L", "energy", "Energy transition & grids", "UK utility — renewables build"),
    ("CNA.L", "energy", "Energy transition & grids", "Centrica — UK energy services"),
    ("RR.L", "energy", "Energy transition & grids", "Rolls-Royce SMR and aerospace"),
    ("BA.L", "auto", "Industrial automation & robotics", "BAE Systems — defense UK"),
    ("LDO.MI", "auto", "Industrial automation & robotics", "Leonardo — defense aerospace EU"),
]


def pool_additions() -> list[tuple[str, str, str, str]]:
    seen: set[str] = set()
    out: list[tuple[str, str, str, str]] = []
    for batch in (WAVE1, WAVE2, WAVE_500):
        for row in batch:
            t = row[0].strip().upper()
            if t in seen:
                continue
            seen.add(t)
            out.append((t, row[1], row[2], row[3]))
    return out


def main() -> int:
    if not MAN.is_file():
        print(f"Missing {MAN}", file=sys.stderr)
        return 2

    rows: list[dict[str, str]] = []
    with MAN.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        for r in reader:
            rows.append(dict(r))

    if "model_tier" not in fields:
        fields.append("model_tier")

    existing = {r["ticker"].strip().upper() for r in rows}
    pool = pool_additions()
    added = 0
    for t, slug, label, link in pool:
        if len(rows) >= TARGET_SCREEN:
            break
        if t in existing:
            continue
        rows.append(
            {
                "ticker": t,
                "theme_slug": slug,
                "theme_label": label,
                "linkage_one_liner": link,
                "model_tier": "screen_only",
            }
        )
        existing.add(t)
        added += 1

    for i, r in enumerate(rows):
        tier = "full" if i < MODEL_CAP else "screen_only"
        r["model_tier"] = tier
        for k in ("ticker", "theme_slug", "theme_label", "linkage_one_liner"):
            r.setdefault(k, r.get(k, ""))
        r["ticker"] = r["ticker"].strip().upper()

    with MAN.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    rub_rows: dict[str, dict[str, str]] = {}
    rub_fields = [
        "ticker",
        "growth",
        "margins",
        "balance_sheet",
        "durability",
        "tail_risks",
        "valuation",
        "note",
    ]
    if RUB.is_file():
        with RUB.open(encoding="utf-8", newline="") as f:
            rub_fields = list(csv.DictReader(f).fieldnames or rub_fields)
            f.seek(0)
            for r in csv.DictReader(f):
                rub_rows[r["ticker"].strip().upper()] = r

    for r in rows:
        t = r["ticker"]
        if t not in rub_rows:
            rub_rows[t] = {
                "ticker": t,
                "growth": "3",
                "margins": "3",
                "balance_sheet": "3",
                "durability": "3",
                "tail_risks": "3",
                "valuation": "3",
                "note": NOTE,
            }

    with RUB.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rub_fields, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            t = r["ticker"]
            row = rub_rows.get(t, {})
            row["ticker"] = t
            w.writerow({k: row.get(k, "") for k in rub_fields})

    if not CAND.is_file():
        CAND.parent.mkdir(parents=True, exist_ok=True)
        with CAND.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(
                ["ticker", "theme_slug", "linkage_one_liner", "source", "added_date", "status"]
            )
            w.writerow(
                [
                    "EXAMPLE",
                    "ai",
                    "Illustration row — delete or replace",
                    "manual",
                    "2026-05-17",
                    "watch",
                ]
            )

    n_full = sum(1 for r in rows if (r.get("model_tier") or "") == "full")
    print(
        f"Manifest: {len(rows)} screen ({n_full} full / {len(rows) - n_full} screen_only); "
        f"added {added} tickers → {MAN}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
