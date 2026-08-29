"""Lint the knowledge corpus: every document must be well-formed.

Checks:
* every ``*.md`` has a sibling ``*.meta.json`` (and vice versa)
* dish metadata carries every field the planner and validator rely on
* implied dietary flags are explicit (vegan => vegetarian + lactose_free)
* every dish ingredient exists in data/inventory.seed.json

Run:  python scripts/check_corpus.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "corpus"
INVENTORY = ROOT / "data" / "inventory.seed.json"

DISH_REQUIRED = {
    "type", "name", "course", "ingredients", "allergens",
    "dietary_flags", "spice_level", "bolivian_origin", "complexity",
}


def main() -> int:
    problems: list[str] = []
    inventory_ids = {i["ingredient_id"] for i in json.loads(INVENTORY.read_text())}

    md_files = set(CORPUS.rglob("*.md"))
    meta_files = set(CORPUS.rglob("*.meta.json"))
    for md in md_files:
        if md.with_suffix("").with_suffix(".meta.json") not in meta_files:
            problems.append(f"{md}: missing sibling .meta.json")
    for meta in meta_files:
        if meta.with_name(meta.name.replace(".meta.json", ".md")) not in md_files:
            problems.append(f"{meta}: missing sibling .md")

    for meta_path in sorted(meta_files):
        meta = json.loads(meta_path.read_text())
        if meta.get("type") != "dish":
            continue
        rel = meta_path.relative_to(CORPUS)
        missing = DISH_REQUIRED - set(meta)
        if missing:
            problems.append(f"{rel}: missing dish fields {sorted(missing)}")
            continue
        flags = set(meta["dietary_flags"])
        if "vegan" in flags and not {"vegetarian", "lactose_free"} <= flags:
            problems.append(
                f"{rel}: vegan implies vegetarian + lactose_free - list them explicitly"
            )
        for ing in meta["ingredients"]:
            if ing not in inventory_ids:
                problems.append(f"{rel}: ingredient '{ing}' not in inventory.seed.json")

    if problems:
        print(f"corpus lint: {len(problems)} problem(s)")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"corpus lint: OK ({len(md_files)} documents)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
