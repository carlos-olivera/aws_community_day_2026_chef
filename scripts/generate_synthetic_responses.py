"""Regenerate data/synthetic_responses.json - 40 deterministic survey answers.

Assignment is index-based (no RNG), so the file is fully reproducible and
the resulting snapshot is predictable. The mix is designed to exercise every
derived constraint:

* 4 vegans + 6 vegetarians  -> vegetarian lunch main AND vegan option per meal
* 10 lactose intolerant, 6 gluten free -> options per meal for both
* 2 peanut + 1 shellfish allergy -> peanut and shellfish banned event-wide
  (shellfish bans nothing on this menu - a nice conservative-rule talking point)
* exactly 4 "mild"-only respondents (10%) -> max_default_spice = "medium"
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVENT_ID = "demo-event"
TOTAL = 40

BASE_TIME = datetime(2026, 8, 29, 9, 0, tzinfo=timezone.utc)

PREFERRED_CYCLE = [
    ["quinoa", "potato"],
    ["corn", "aji_amarillo"],
    ["quinoa", "trout"],
    ["potato", "chuno"],
    ["llama_meat"],
    ["quinoa", "corn", "potato"],
    ["broad_beans"],
    ["amaranth", "quinoa"],
    [],
    ["potato"],
]

CUISINE_CYCLE = [
    "traditional_bolivian", "traditional_bolivian", "andean_fusion",
    "no_preference", "traditional_bolivian", "international",
    "andean_fusion", "no_preference", "traditional_bolivian", "no_preference",
]


def build_responses() -> list[dict]:
    responses = []
    for i in range(TOTAL):
        diet = "vegan" if i < 4 else "vegetarian" if i < 10 else "none"
        spice = "mild" if i % 10 == 3 else "hot" if i % 4 == 0 else "medium"
        allergies = []
        if i in (5, 17):
            allergies = ["peanut"]
        elif i == 23:
            allergies = ["shellfish"]
        responses.append(
            {
                "response_id": str(uuid.UUID(int=i + 1)),
                "event_id": EVENT_ID,
                "submitted_at": (BASE_TIME + timedelta(seconds=30 * i)).isoformat(),
                "diet": diet,
                "lactose_intolerant": i % 4 == 1,       # 10 of 40
                "gluten_free": i % 7 == 2,              # 6 of 40
                "allergies": allergies,
                "spice_level": spice,
                "cuisine_preference": CUISINE_CYCLE[i % len(CUISINE_CYCLE)],
                "preferred_ingredients": PREFERRED_CYCLE[i % len(PREFERRED_CYCLE)],
                "consent": True,
            }
        )
    return responses


if __name__ == "__main__":
    out = ROOT / "data" / "synthetic_responses.json"
    out.write_text(json.dumps(build_responses(), indent=2) + "\n")
    print(f"wrote {TOTAL} responses to {out}")
