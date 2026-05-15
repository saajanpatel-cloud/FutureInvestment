#!/usr/bin/env python3
"""Load canonical theme target weights for Discover / shortlist caps / ~Alloc %."""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "research" / "watchlists" / "theme_target_weights.json"


def load_theme_weights(path: Path | None = None) -> dict[str, float]:
    p = path or DEFAULT_PATH
    if not p.is_file():
        raise FileNotFoundError(f"theme weights not found: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    out: dict[str, float] = {}
    for k, v in raw.items():
        if k.startswith("_"):
            continue
        out[str(k).strip()] = float(v)
    s = sum(out.values())
    if abs(s - 1.0) > 1e-6:
        raise ValueError(f"theme_target_weights must sum to 1.0, got {s}")
    return out


def caps_from_weights(weights: dict[str, float], seat_budget: int) -> dict[str, int]:
    """Largest-remainder allocation of integer seats to themes (sum == seat_budget)."""
    if seat_budget <= 0:
        return {k: 0 for k in weights}
    keys = list(weights.keys())
    exact = [weights[k] * seat_budget for k in keys]
    floors = [int(math.floor(x + 1e-9)) for x in exact]
    rem = [e - f for e, f in zip(exact, floors)]
    n = seat_budget - sum(floors)
    order = sorted(range(len(keys)), key=lambda i: (-rem[i], -exact[i], keys[i]))
    caps = dict(zip(keys, floors))
    for i in order[: max(0, n)]:
        caps[keys[i]] += 1
    return caps
