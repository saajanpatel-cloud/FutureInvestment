#!/usr/bin/env python3
"""
Append ~158 new tickers to universe_manifest.csv + rubric_scores.csv so the
evaluated sleeve reaches ~316 names (158 -> 316). Skips symbols already present.

Run from repo root:
  python3 scripts/fi_double_universe.py

Then: ./scripts/refresh_watchlists.sh

Not investment advice.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAN = ROOT / "research" / "watchlists" / "universe_manifest.csv"
SCR = ROOT / "research" / "watchlists" / "rubric_scores.csv"

# (ticker, theme_slug, theme_label, linkage_one_liner) — curated thematic adds.
ADDITIONS: list[tuple[str, str, str, str]] = [
    # +30 AI infra & compute
    ("TXN", "ai", "AI infra & compute", "Analog and embedded semis — broad industrial + auto exposure"),
    ("QCOM", "ai", "AI infra & compute", "Handset RF plus AI edge inference — licensing mix"),
    ("ADI", "ai", "AI infra & compute", "High-performance analog and mixed signal for data paths"),
    ("ON", "ai", "AI infra & compute", "Power discretes and SiC for electrification and DC systems"),
    ("SWKS", "ai", "AI infra & compute", "RF front-end modules — handset cyclicality vs content gains"),
    ("QRVO", "ai", "AI infra & compute", "RF connectivity and defense/aerospace semi exposure"),
    ("ENTG", "ai", "AI infra & compute", "Materials purity for wafer fabs and advanced packaging"),
    ("OLED", "ai", "AI infra & compute", "Universal display materials — OLED emitter chemistry"),
    ("LSCC", "ai", "AI infra & compute", "Low-power FPGAs for edge and industrial acceleration"),
    ("RMBS", "ai", "AI infra & compute", "Memory interface IP and chips — HBM ecosystem adjacency"),
    ("CRUS", "ai", "AI infra & compute", "Audio and high-precision mixed-signal for consumer and auto"),
    ("SLAB", "ai", "AI infra & compute", "IoT MCUs and mesh — industrial connectivity"),
    ("DIOD", "ai", "AI infra & compute", "Discrete and analog components — broad cyclical semi"),
    ("POWI", "ai", "AI infra & compute", "Power conversion ICs — efficiency regulation tailwind"),
    ("WOLF", "ai", "AI infra & compute", "SiC substrates and devices — EV and power switching"),
    ("INOD", "ai", "AI infra & compute", "Data engineering / AI data prep software microcap"),
    ("NVMI", "ai", "AI infra & compute", "Metrology for advanced packaging and CMP process control"),
    ("ICHR", "ai", "AI infra & compute", "Fluid delivery systems for semiconductor manufacturing"),
    ("PLAB", "ai", "AI infra & compute", "Photomasks — lithography consumables"),
    ("UEIC", "ai", "AI infra & compute", "Universal remotes and smart home control chips"),
    ("SITM", "ai", "AI infra & compute", "MEMS timing — precision clocks for comms and DC"),
    ("ACLS", "ai", "AI infra & compute", "Axcelis ion implant equipment for WFE"),
    ("AOSL", "ai", "AI infra & compute", "Power discretes and small-signal — diversified semi"),
    ("FLEX", "ai", "AI infra & compute", "EMS / JDM manufacturing for hyperscale and networking gear"),
    ("JBL", "ai", "AI infra & compute", "EMS diversified — AI server and appliance builds"),
    ("TTMI", "ai", "AI infra & compute", "PCB fabrication for networking and compute boards"),
    ("VSH", "ai", "AI infra & compute", "Diodes resistors inductors — passive components"),
    ("APH", "ai", "AI infra & compute", "Interconnect for harsh environments — data centre cabling"),
    ("PI", "ai", "AI infra & compute", "Wireless power and GaN — consumer and industrial"),
    ("MXL", "ai", "AI infra & compute", "Broadband and connectivity mixed-signal — DOCSIS and fiber"),
    # +35 Energy transition & grids
    ("CVX", "energy", "Energy transition & grids", "Integrated oil — cash returns and LNG optionality"),
    ("COP", "energy", "Energy transition & grids", "US shale plus Alaska — production growth discipline"),
    ("OXY", "energy", "Energy transition & grids", "Permian operator plus carbon capture narrative"),
    ("DVN", "energy", "Energy transition & grids", "Delaware Basin oil — variable dividend framework"),
    ("HAL", "energy", "Energy transition & grids", "Oilfield services pressure pumping — cycle leverage"),
    ("SLB", "energy", "Energy transition & grids", "OFSP digital drilling international mix"),
    ("MPC", "energy", "Energy transition & grids", "Refining and midstream logistics — crack spread exposure"),
    ("VLO", "energy", "Energy transition & grids", "Independent refiner — renewable diesel projects"),
    ("PSX", "energy", "Energy transition & grids", "Phillips 66 refining plus midstream CPChem"),
    ("FANG", "energy", "Energy transition & grids", "Permian pure-play — shareholder returns focus"),
    ("EOG", "energy", "Energy transition & grids", "Premier shale operator — returns over growth"),
    ("NRG", "energy", "Energy transition & grids", "Retail power plus generation — merchant spread"),
    ("EXC", "energy", "Energy transition & grids", "Nuclear-heavy utility — PJM exposure"),
    ("FE", "energy", "Energy transition & grids", "Transmission investment story — regulatory lag risk"),
    ("ED", "energy", "Energy transition & grids", "NYC-centric wires — dense load pocket"),
    ("AWK", "energy", "Energy transition & grids", "Regulated water utility — infrastructure replacement"),
    ("WTRG", "energy", "Energy transition & grids", "Essential utilities water gas electric bundle"),
    ("ATO", "energy", "Energy transition & grids", "Texas gas distribution — rate base growth"),
    ("LNG", "energy", "Energy transition & grids", "Cheniere LNG export tolling — long-term contracts"),
    ("KMI", "energy", "Energy transition & grids", "Natural gas pipelines — fee-based cash flows"),
    ("WMB", "energy", "Energy transition & grids", "Gas gathering and processing — Gulf exposure"),
    ("OKE", "energy", "Energy transition & grids", "NGL fractionation and midstream services"),
    ("TRGP", "energy", "Energy transition & grids", "Gathering and processing Permian Delaware"),
    ("SMR", "energy", "Energy transition & grids", "SMR developer — licensing and power purchase risk"),
    ("OKLO", "energy", "Energy transition & grids", "Advanced fission developer — milestone equity story"),
    ("BWXT", "energy", "Energy transition & grids", "Naval reactors and nuclear components — defense mix"),
    ("LEU", "energy", "Energy transition & grids", "Uranium conversion and HALEU — policy sensitive"),
    ("UEC", "energy", "Energy transition & grids", "US ISR uranium developer — spot price leverage"),
    ("UUUU", "energy", "Energy transition & grids", "ISR uranium plus rare earths optionality"),
    ("URG", "energy", "Energy transition & grids", "ISR uranium producer — small cap volatility"),
    ("DNN", "energy", "Energy transition & grids", "ISR uranium developer — pre-production"),
    ("BEP", "energy", "Energy transition & grids", "Brookfield Renewable yieldCo — hydro wind solar mix"),
    ("BE", "energy", "Energy transition & grids", "Fuel cells and electrolyzers — cash burn risk"),
    ("BIP", "energy", "Energy transition & grids", "Brookfield Infrastructure — toll roads utilities pipelines"),
    ("NEP", "energy", "Energy transition & grids", "NextEra Energy Partners renewables dropdown story"),
    # +14 Cybersecurity & digital trust
    ("CYBR", "cyber", "Cybersecurity & digital trust", "Privileged access management — identity security"),
    ("MNDY", "cyber", "Cybersecurity & digital trust", "Monday work OS — workflow automation with security posture"),
    ("DDOG", "cyber", "Cybersecurity & digital trust", "Observability and cloud security telemetry"),
    ("SNOW", "cyber", "Cybersecurity & digital trust", "Data cloud — governance and sharing workloads"),
    ("ESTC", "cyber", "Cybersecurity & digital trust", "Search analytics security SIEM competitor set"),
    ("MDB", "cyber", "Cybersecurity & digital trust", "Document database — developer-led adoption"),
    ("PATH", "cyber", "Cybersecurity & digital trust", "RPA plus process mining — enterprise automation"),
    ("CFLT", "cyber", "Cybersecurity & digital trust", "Streaming data platform — real-time pipelines"),
    ("FRSH", "cyber", "Cybersecurity & digital trust", "Freshservice / ITSM cloud — SMB upmarket"),
    ("DT", "cyber", "Cybersecurity & digital trust", "Dynatrace observability — enterprise APM"),
    ("PD", "cyber", "Cybersecurity & digital trust", "PagerDuty incident response — SRE tooling"),
    ("ZI", "cyber", "Cybersecurity & digital trust", "ZoomInfo go-to-market data — privacy/reg risk"),
    ("NOW", "cyber", "Cybersecurity & digital trust", "ServiceNow workflow and GRC digitization"),
    ("WDAY", "cyber", "Cybersecurity & digital trust", "Workday HCM and financials cloud ERP"),
    # +36 Industrial automation & robotics / space-defence tilt
    ("LMT", "auto", "Industrial automation & robotics", "Defense prime — missiles space and aero structures"),
    ("NOC", "auto", "Industrial automation & robotics", "Defense prime — bombers UAVs and space"),
    ("LHX", "auto", "Industrial automation & robotics", "Defense electronics post-L3Harris merger integration"),
    ("RTX", "auto", "Industrial automation & robotics", "Pratt engines plus Raytheon missiles mix"),
    ("GD", "auto", "Industrial automation & robotics", "Gulfstream plus combat systems shipbuilding"),
    ("HII", "auto", "Industrial automation & robotics", "US Navy shipbuilding — carrier submarine backlog"),
    ("TXT", "auto", "Industrial automation & robotics", "Bell aviation plus industrial and Textron Systems"),
    ("JCI", "auto", "Industrial automation & robotics", "Building controls and OpenBlue smart buildings"),
    ("NDSN", "auto", "Industrial automation & robotics", "Nordson precision dispensing and industrial coatings"),
    ("WSO", "auto", "Industrial automation & robotics", "HVAC distribution scale — North America residential mix"),
    ("ALLE", "auto", "Industrial automation & robotics", "Allegion security hardware — commercial doors"),
    ("PNR", "auto", "Industrial automation & robotics", "Pentair water treatment and pool equipment"),
    ("GGG", "auto", "Industrial automation & robotics", "Graco fluid handling pumps — industrial coatings"),
    ("IEX", "auto", "Industrial automation & robotics", "IDEX precision pumps and dispensing"),
    ("XYL", "auto", "Industrial automation & robotics", "Xylem water infrastructure — acquisition synergies"),
    ("ROP", "auto", "Industrial automation & robotics", "Roper software rollup — niche vertical SaaS"),
    ("FLS", "auto", "Industrial automation & robotics", "Flowserve pumps valves — energy capex cycle"),
    ("CMI", "auto", "Industrial automation & robotics", "Cummins engines plus Accelera hydrogen bet"),
    ("B", "auto", "Industrial automation & robotics", "Barnes aerospace and automation components"),
    ("FTV", "auto", "Industrial automation & robotics", "Fortive industrial instrumentation and healthcare diagnostics spin mix"),
    ("ITT", "auto", "Industrial automation & robotics", "Motion flow control — defense and industrial"),
    ("DHR", "auto", "Industrial automation & robotics", "Life sciences tools plus industrial diagnostics"),
    ("AOS", "auto", "Industrial automation & robotics", "Water heaters and boilers — residential cycle"),
    ("DOV", "auto", "Industrial automation & robotics", "Diversified industrial pumps and fueling"),
    ("FAST", "auto", "Industrial automation & robotics", "Fastenal vending and onsite inventory"),
    ("GNRC", "auto", "Industrial automation & robotics", "Backup generators — outage and grid fragility"),
    ("LECO", "auto", "Industrial automation & robotics", "Lincoln Electric welding automation"),
    ("SWK", "auto", "Industrial automation & robotics", "Stanley Black & Decker tools — margin reset"),
    ("WWD", "auto", "Industrial automation & robotics", "Woodward aircraft and industrial actuation controls"),
    ("TDY", "auto", "Industrial automation & robotics", "Teledyne imaging instruments and defense"),
    ("AME", "auto", "Industrial automation & robotics", "Ametek precision instruments and power"),
    ("ZBRA", "auto", "Industrial automation & robotics", "Zebra mobile computing and RFID tracking"),
    ("ZBH", "auto", "Industrial automation & robotics", "Zimmer Biomed — robotics knee mix"),
    ("OTIS", "auto", "Industrial automation & robotics", "Elevators service moat — China mix"),
    ("WAB", "auto", "Industrial automation & robotics", "Wabtec rail and freight electronics"),
    ("VMI", "auto", "Industrial automation & robotics", "Valmont infrastructure irrigation poles"),
    # +31 Health Tech
    ("JNJ", "health", "Health Tech", "Pharma medtech consumer diversified — patent cliffs matter"),
    ("PFE", "health", "Health Tech", "Post-COVID oncology pipeline rebuild — execution risk"),
    ("MRK", "health", "Health Tech", "Keytruda franchise duration — oncology concentration"),
    ("ABT", "health", "Health Tech", "Devices plus diagnostics — Libre and structural heart"),
    ("BAX", "health", "Health Tech", "MedSurg and pharmaceuticals hospital supply chain"),
    ("MDT", "health", "Health Tech", "Medtronic devices — GLP-1 overhang on obesity devices"),
    ("HOLX", "health", "Health Tech", "Diagnostics imaging and surgical women's health"),
    ("UNH", "health", "Health Tech", "UnitedHealthcare plus Optum vertical integration"),
    ("CVS", "health", "Health Tech", "Retail pharmacy plus Aetna — reimbursement pressure"),
    ("CI", "health", "Health Tech", "Cigna Evernorth pharmacy benefits mix"),
    ("HUM", "health", "Health Tech", "Medicare Advantage star ratings risk"),
    ("ELV", "health", "Health Tech", "Anthem rebrand — commercial and gov mix"),
    ("CNC", "health", "Health Tech", "Centene Medicaid exposure — state budget cycles"),
    ("MOH", "health", "Health Tech", "Molina Medicaid pure-play — regulatory cap"),
    ("XRAY", "health", "Health Tech", "Dentsply Sirona dental equipment — channel inventory"),
    ("ALGN", "health", "Health Tech", "Align Invisalign — consumer discretionary sensitivity"),
    ("TECH", "health", "Health Tech", "Bio-Techne reagents — biologics tools recurring"),
    ("DGX", "health", "Health Tech", "Quest Diagnostics lab volumes — pricing"),
    ("LH", "health", "Health Tech", "LabCorp diagnostics plus drug development"),
    ("A", "health", "Health Tech", "Agilent instruments and diagnostics services"),
    ("ILMN", "health", "Health Tech", "Sequencing installed base — consumable pull-through"),
    ("TDOC", "health", "Health Tech", "Teladoc virtual care — profitability path"),
    ("RMD", "health", "Health Tech", "ResMed sleep apnea devices — GLP-1 competitive readthrough"),
    ("BIIB", "health", "Health Tech", "Neuroscience and biosimilars — Leqembi and franchise resets"),
    ("BNTX", "health", "Health Tech", "BioNTech oncology plus Pfizer partnership economics"),
    ("SRPT", "health", "Health Tech", "Sarepta gene therapy — regulatory binary"),
    ("EXAS", "health", "Health Tech", "Exact Sciences CRC screening — guideline adoption"),
    ("NVAX", "health", "Health Tech", "Novavax vaccine platform — funding and execution"),
    ("SWTX", "health", "Health Tech", "SpringWorks oncology rare disease — trial readouts"),
    ("DNA", "health", "Health Tech", "Ginkgo cell engineering — revenue quality debate"),
    ("RXRX", "health", "Health Tech", "Recursion AI drug discovery — compute spend"),
    # +12 Quantum / frontier compute (semi adjacency + sensing)
    ("ACMR", "quantum", "Quantum / frontier compute", "ACM Research China WFE — geopolitical listing risk"),
    ("KLIC", "quantum", "Quantum / frontier compute", "Kulicke & Soffa wire bond packaging equipment"),
    ("ONTO", "quantum", "Quantum / frontier compute", "Onto metrology and inspection for advanced nodes"),
    ("BRKS", "quantum", "Quantum / frontier compute", "Brooks automation cryogenics and vacuum"),
    ("CAMT", "quantum", "Quantum / frontier compute", "Camtek inspection for advanced packaging"),
    ("COHU", "quantum", "Quantum / frontier compute", "Cohu handler and test interface equipment"),
    ("AEHR", "quantum", "Quantum / frontier compute", "Aehr wafer-level burn-in for SiC reliability"),
    ("VPG", "quantum", "Quantum / frontier compute", "Vishay precision foil resistors — metrology niche"),
    ("SMTC", "quantum", "Quantum / frontier compute", "Semtech LoRa plus signal integrity — mixed cycles"),
    ("INDI", "quantum", "Quantum / frontier compute", "indie Semiconductor auto edge — ADAS content"),
    ("LASR", "quantum", "Quantum / frontier compute", "Luminar lidar — auto OEM design-in path"),
    ("MVIS", "quantum", "Quantum / frontier compute", "MicroVision lidar MEMS — speculative liquidity"),
]

NOTE = "Placeholder rubric — one-liner to refresh after filing review."


def main() -> None:
    existing_m = {r["ticker"].strip().upper() for r in csv.DictReader(MAN.open(encoding="utf-8", newline=""))}
    if "TXN" in existing_m and len(existing_m) >= 300:
        print("Manifest already enlarged (TXN present, >=300 tickers); nothing to do.", file=sys.stderr)
        sys.exit(0)
    existing_s = {r["ticker"].strip().upper() for r in csv.DictReader(SCR.open(encoding="utf-8", newline=""))}

    to_add = [(a[0].strip().upper(), a[1], a[2], a[3]) for a in ADDITIONS if a[0].strip().upper() not in existing_m]
    skipped = [a[0] for a in ADDITIONS if a[0].strip().upper() in existing_m]
    if skipped:
        print("skipped (already in manifest):", ", ".join(skipped[:20]), "...", file=sys.stderr)

    if len(to_add) < 158:
        print(f"error: only {len(to_add)} new manifest rows (need 158). Add more candidates.", file=sys.stderr)
        sys.exit(1)
    if len(to_add) > 158:
        to_add = to_add[:158]

    with MAN.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        for t, slug, label, link in to_add:
            w.writerow([t, slug, label, link])

    new_tickers = [t for t, _, _, _ in to_add]
    with SCR.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        for t in new_tickers:
            if t in existing_s:
                continue
            w.writerow([t, 3, 3, 3, 3, 3, 3, NOTE])
        if "QUBT" in existing_m and "QUBT" not in existing_s:
            w.writerow(["QUBT", 2, 2, 2, 2, 4, 2, "Quantum micro-cap — sparse fundamentals; placeholder until refresh."])

    print(f"Appended {len(to_add)} rows to {MAN.relative_to(ROOT)}")
    print("Run: ./scripts/refresh_watchlists.sh")


if __name__ == "__main__":
    main()
