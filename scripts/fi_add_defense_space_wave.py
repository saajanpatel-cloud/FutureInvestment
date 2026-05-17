#!/usr/bin/env python3
"""
Append aerospace / defense / space / semi wave tickers to universe_manifest + rubric_scores.

Run from repo root:
  python3 scripts/fi_add_defense_space_wave.py

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

NOTE = "Placeholder rubric — one-liner to refresh after filing review."

# (ticker, theme_slug, theme_label, linkage_one_liner)
ADDITIONS: list[tuple[str, str, str, str]] = [
    ("HXL", "auto", "Industrial automation & robotics", "Carbon fibre composites for aerospace structures"),
    ("GE", "auto", "Industrial automation & robotics", "Aerospace engines and power — LEAP cycle and services mix"),
    ("BA", "auto", "Industrial automation & robotics", "Commercial aerospace duopoly — delivery ramp and balance sheet"),
    ("RDW", "auto", "Industrial automation & robotics", "Space systems integrator — NASA and defense missions"),
    ("TRMB", "auto", "Industrial automation & robotics", "Precision agriculture and construction positioning tech"),
    ("BAESY", "auto", "Industrial automation & robotics", "UK defense prime — electronic systems and US exposure"),
    ("PLTR", "auto", "Industrial automation & robotics", "Gov and enterprise AI platforms — contract wins and margins"),
    ("HEI.A", "auto", "Industrial automation & robotics", "Heico — aerospace aftermarket parts and acquisitions"),
    ("ESLT", "auto", "Industrial automation & robotics", "Elbit Systems — defense electronics Israel and export"),
    ("KTOS", "auto", "Industrial automation & robotics", "Unmanned systems and C5ISR — defense tech integrator"),
    ("SIDU", "quantum", "Quantum / frontier compute", "Sidus Space — small satellite and space services microcap"),
    ("ATRO", "auto", "Industrial automation & robotics", "Astronics — aircraft lighting and power distribution"),
    ("LDOS", "auto", "Industrial automation & robotics", "Leidos — defense IT and engineering services"),
    ("KULR", "quantum", "Quantum / frontier compute", "Thermal management for batteries and space hardware"),
    ("EADSY", "auto", "Industrial automation & robotics", "Airbus ADR — commercial jet backlog and helicopter mix"),
    ("RKLB", "quantum", "Quantum / frontier compute", "Rocket Lab — launch and space systems"),
    ("SPCE", "quantum", "Quantum / frontier compute", "Suborbital tourism — cash burn and commercialization risk"),
    ("FLY", "auto", "Industrial automation & robotics", "Fly Leasing / verify ticker — aircraft lessor exposure"),
    ("LUNR", "quantum", "Quantum / frontier compute", "Intuitive Machines — lunar lander programs"),
    ("VOYG", "quantum", "Quantum / frontier compute", "Voyager Technologies — defense and space systems"),
    ("MNTS", "quantum", "Quantum / frontier compute", "Momentus — in-space transportation — high dilution risk"),
    ("BKSY", "quantum", "Quantum / frontier compute", "BlackSky — geospatial intelligence satellites"),
    ("SATL", "quantum", "Quantum / frontier compute", "Satellogic — EO constellation operator"),
    ("ASTS", "quantum", "Quantum / frontier compute", "AST SpaceMobile — direct-to-cell satellite broadband"),
    ("PL", "quantum", "Quantum / frontier compute", "Planet Labs — daily Earth observation data"),
    ("SATS", "quantum", "Quantum / frontier compute", "EchoStar / satellite connectivity — verify segment mix"),
    ("SPIR", "quantum", "Quantum / frontier compute", "Spire Global — space-based data and analytics"),
    ("VSAT", "quantum", "Quantum / frontier compute", "Viasat — satellite broadband and Inmarsat integration"),
    ("IRDM", "quantum", "Quantum / frontier compute", "Iridium — LEO voice and IoT constellation"),
    ("GSAT", "quantum", "Quantum / frontier compute", "Globalstar — satellite IoT and Apple partnership"),
    ("TSAT", "quantum", "Quantum / frontier compute", "Telesat — LEO constellation development"),
    ("AMZN", "ai", "AI infra & compute", "AWS and retail — hyperscaler capex and AI services optionality"),
    ("CBRS", "cyber", "Cybersecurity & digital trust", "Ciber / verify — IT services and security"),
    ("LWLG", "ai", "AI infra & compute", "Lightwave Logic — photonic polymers for interconnect"),
    ("MRAM", "ai", "AI infra & compute", "Everspin MRAM — persistent memory niche"),
    ("NVTS", "ai", "AI infra & compute", "Navitas — GaN power ICs for data centre and EV"),
    ("ONDAS", "quantum", "Quantum / frontier compute", "Ondas — autonomous systems and rail wireless"),
    ("ANGO", "health", "Healthcare innovation & AI in medicine", "AngioDynamics — med devices vascular access"),
    ("NBIS", "ai", "AI infra & compute", "Nebius — AI cloud GPU infrastructure spin narrative"),
    ("GLW", "ai", "AI infra & compute", "Corning — optical fibre and display glass for DC builds"),
    ("IREN", "energy", "Energy transition & grids", "Bitcoin miner pivoting to AI data centre power"),
    ("CRWV", "ai", "AI infra & compute", "CoreWeave — GPU cloud for AI workloads"),
    ("LITE", "ai", "AI infra & compute", "Lumentum — optical components for AI networking"),
]


def main() -> None:
    existing_m = {
        r["ticker"].strip().upper()
        for r in csv.DictReader(MAN.open(encoding="utf-8", newline=""))
    }
    existing_s = {
        r["ticker"].strip().upper()
        for r in csv.DictReader(SCR.open(encoding="utf-8", newline=""))
    }

    to_add = [(a[0].strip().upper(), a[1], a[2], a[3]) for a in ADDITIONS if a[0].strip().upper() not in existing_m]
    skipped = [a[0] for a in ADDITIONS if a[0].strip().upper() in existing_m]

    if skipped:
        print("skipped (already in manifest):", ", ".join(skipped), file=sys.stderr)

    if not to_add:
        print("Nothing to append.", file=sys.stderr)
        return

    with MAN.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        for t, slug, label, link in to_add:
            w.writerow([t, slug, label, link])

    with SCR.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        for t, _, _, _ in to_add:
            if t in existing_s:
                continue
            w.writerow([t, 3, 3, 3, 3, 3, 3, NOTE])

    print(f"Appended {len(to_add)} rows to {MAN.relative_to(ROOT)}")
    print("Run: ./scripts/refresh_watchlists.sh")


if __name__ == "__main__":
    main()
