"""MockPlanner: a deterministic brain you can read top to bottom.

It is NOT a fake text generator - it is a scripted decision policy that
drives the same tools, through the same registry, as a real LLM would:

    observe snapshot -> inspect inventory -> search knowledge (4 courses)
    -> optional web inspiration -> assemble candidate -> evaluate
    -> validate & publish (repairing once if refused)

Flaw injection (on by default in the CLI): the first candidate deliberately
includes a dish carrying a banned allergen, and the planner "confidently"
publishes it without evaluating first. The validator + policy DENY it, the
planner reads the failed checks, repairs the menu and succeeds - so every
classroom run shows the reject -> repair -> publish cycle instead of a
suspiciously perfect first try.

Fully deterministic: same corpus + same snapshot -> same menu. No RNG.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from chef_andino.contracts.models import (
    DISCLAIMER,
    SPICE_ORDER,
    MenuItem,
)
from chef_andino.planner.base import AgentState, Finish, PlannerAction, ToolCall

# The four knowledge searches the planner runs, in order.
_SEARCHES = [
    ("breakfast", "bolivian breakfast buffet"),
    ("starter", "bolivian starters and soups"),
    ("main", "bolivian main dishes for events"),
    ("dessert", "bolivian desserts"),
]


class MockPlanner:
    """A scripted planner: readable, testable, and honest about being scripted."""

    def __init__(self, first_candidate_flaw: str | None = "declared_allergen") -> None:
        """``first_candidate_flaw=None`` gives a clean (no-DENY) run."""
        self._flaw = first_candidate_flaw
        self._phase = 0
        self._snapshot: dict | None = None
        self._inventory: list[dict] = []
        self._pools: dict[str, list[dict]] = {}
        self._candidate: dict | None = None
        self._published = False

    # ------------------------------------------------------------------ loop

    def next_action(self, state: AgentState) -> PlannerAction:
        """Walk the scripted phases, consuming the previous tool result."""
        last = state.last_result()

        if self._phase == 0:
            self._phase = 1
            return ToolCall(
                "get_event_snapshot",
                rationale="First, understand who I am cooking for.",
            )

        if self._phase == 1:
            if not last or not last.ok:
                return Finish("gave_up: cannot read the event snapshot")
            self._snapshot = last.data
            self._phase = 2
            return ToolCall(
                "get_available_ingredients",
                rationale="Now, what does the kitchen actually have?",
            )

        if self._phase == 2:
            if not last or not last.ok:
                return Finish("gave_up: cannot read the inventory")
            self._inventory = last.data
            self._phase = 3

        if 3 <= self._phase <= 6:
            search_idx = self._phase - 3
            if search_idx > 0 and last and last.ok:
                self._pools[_SEARCHES[search_idx - 1][0]] = [h["metadata"] | {
                    "doc_id": h["doc_id"], "snippet": h["snippet"]
                } for h in last.data]
            course, query = _SEARCHES[search_idx]
            self._phase += 1
            return ToolCall(
                "search_culinary_knowledge",
                args={"query": query, "filters": {"type": "dish", "course": course}},
                rationale=f"Looking for {course} options in the knowledge base.",
            )

        if self._phase == 7:
            if last and last.ok:
                self._pools[_SEARCHES[-1][0]] = [h["metadata"] | {
                    "doc_id": h["doc_id"], "snippet": h["snippet"]
                } for h in last.data]
            self._phase = 8
            return ToolCall(
                "research_web",
                args={"query": "large event buffet ideas with andean grains"},
                rationale="Optional inspiration - the mission survives if this fails.",
            )

        if self._phase == 8:
            # Web results (if any) are inspiration only; nothing depends on them.
            self._phase = 9
            if self._flaw:
                self._candidate = self._assemble(apply_allergen_filter=False)
                return ToolCall(
                    "validate_and_publish_menu",
                    args={"menu": self._candidate},
                    rationale="The menu looks delicious - publishing right away.",
                )
            self._candidate = self._assemble(apply_allergen_filter=True)
            return ToolCall(
                "evaluate_menu",
                args={"menu": self._candidate},
                rationale="Scoring the candidate before trying to publish.",
            )

        if self._phase == 9:
            if self._flaw:
                # The overconfident publish was DENIED. Read the checks, repair.
                assert last is not None
                failed = [c["id"] for c in (last.data or {}).get("failed_checks", [])]
                self._candidate = self._assemble(apply_allergen_filter=True)
                self._phase = 10
                return ToolCall(
                    "evaluate_menu",
                    args={"menu": self._candidate},
                    rationale=(
                        f"Publish was denied (failed checks: {failed or 'unknown'}). "
                        "Repaired the menu; scoring the new candidate."
                    ),
                )
            self._phase = 10
            return ToolCall(
                "validate_and_publish_menu",
                args={"menu": self._candidate},
                rationale="Score is healthy - asking the gate to publish.",
            )

        if self._phase == 10:
            if last and last.ok and "menu_id" in (last.data or {}):
                self._published = True
                return Finish("published")
            if self._flaw:
                self._phase = 11
                return ToolCall(
                    "validate_and_publish_menu",
                    args={"menu": self._candidate},
                    rationale="Repaired candidate scored well - publishing.",
                )
            return Finish("gave_up: publish was refused twice")

        if self._phase == 11:
            if last and last.ok:
                self._published = True
                return Finish("published")
            return Finish("gave_up: repaired menu was still refused")

        return Finish("gave_up: script exhausted")

    # ------------------------------------------------------------- assembly

    def _assemble(self, apply_allergen_filter: bool) -> dict:
        """Delegate to the module-level :func:`assemble_menu`."""
        assert self._snapshot is not None
        return assemble_menu(
            self._snapshot, self._inventory, self._pools, apply_allergen_filter
        )


def assemble_menu(
    snapshot: dict,
    inventory: list[dict],
    pools: dict[str, list[dict]],
    apply_allergen_filter: bool = True,
) -> dict:
    """Build a candidate menu from knowledge pools and the inventory.

    With ``apply_allergen_filter=False`` the banned-allergen rule is
    deliberately ignored - simulating a model that overlooked a constraint.
    Everything else (stock, spice, coverage) is respected. Deterministic:
    same inputs, same menu.
    """
    constraints = snapshot["derived_constraints"]
    banned = set(constraints["must_exclude_allergens"])
    in_stock = {i["ingredient_id"] for i in inventory if i["quantity"] > 0}
    allergens_of = {i["ingredient_id"]: set(i["allergens"]) for i in inventory}
    max_spice = SPICE_ORDER[constraints["max_default_spice"]]

    def acceptable(dish: dict, check_allergens: bool) -> bool:
        if not set(dish["ingredients"]) <= in_stock:
            return False
        if SPICE_ORDER[dish["spice_level"]] > max_spice:
            return False
        if check_allergens:
            if banned & set(dish["allergens"]):
                return False
            for ing in dish["ingredients"]:
                if banned & allergens_of.get(ing, set()):
                    return False
        return True

    def pool(course: str, check_allergens: bool = True) -> list[dict]:
        dishes = [
            d for d in pools.get(course, [])
            if acceptable(d, check_allergens)
        ]
        return sorted(dishes, key=lambda d: d["doc_id"])

    def needs(dish: dict, flag: str) -> bool:
        return flag in dish["dietary_flags"]

    required_flags = [
        flag
        for flag, key in (
            ("vegan", "require_vegan_option_per_meal"),
            ("gluten_free", "require_gluten_free_option_per_meal"),
            ("lactose_free", "require_lactose_free_option_per_meal"),
        )
        if constraints[key]
    ]

    # Breakfast: cover every required flag first, then fill up to 5 items.
    breakfast_pool = pool("breakfast")
    breakfast: list[dict] = []
    for flag in required_flags:
        if not any(needs(d, flag) for d in breakfast):
            match = next(
                (d for d in breakfast_pool if needs(d, flag) and d not in breakfast),
                None,
            )
            if match:
                breakfast.append(match)
    for dish in breakfast_pool:
        if len(breakfast) >= 5:
            break
        if dish not in breakfast:
            breakfast.append(dish)

    # Lunch mains: one universal (all required flags + vegetarian if
    # required), one free choice - two real options for the audience.
    main_pool = pool("main")
    universal_flags = list(required_flags)
    if constraints["require_vegetarian_lunch_main"]:
        universal_flags.append("vegetarian")
    universal = [d for d in main_pool if all(needs(d, f) for f in universal_flags)]
    first_main = universal[0] if universal else main_pool[0]
    second_main = next(
        (d for d in main_pool if d not in universal and d is not first_main),
        next((d for d in main_pool if d is not first_main), first_main),
    )

    # Dinner has a SINGLE main: it must itself be the universal option
    # (and a different dish from the lunch mains - no repeats).
    taken = (first_main, second_main)
    dinner_main = next(
        (d for d in universal if d not in taken),
        next((d for d in main_pool if d not in taken), main_pool[-1]),
    )

    # Starter: with the flaw active, pick from the UNFILTERED pool so a
    # banned-allergen dish (hello, sopa de mani) can sneak in.
    starter_pool = pool("starter", check_allergens=apply_allergen_filter)
    if not apply_allergen_filter:
        flawed = [d for d in starter_pool if banned & set(d["allergens"])]
        starter = flawed[0] if flawed else starter_pool[0]
    else:
        starter = starter_pool[0]

    dessert_pool = pool("dessert")
    lunch_dessert, dinner_dessert = dessert_pool[0], dessert_pool[1]

    def to_item(dish: dict) -> dict:
        return MenuItem(
            dish_id=dish["doc_id"].split("/")[-1],
            name=dish["name"],
            description=dish.get("snippet", "")[:300],
            ingredients=dish["ingredients"],
            allergens=dish["allergens"],
            dietary_flags=dish["dietary_flags"],
            spice_level=dish["spice_level"],
            bolivian_origin=dish["bolivian_origin"],
            complexity=dish["complexity"],
            sources=[{"type": "knowledge_base", "ref": dish["doc_id"]}],
        ).model_dump(mode="json")

    return {
        "menu_id": f"candidate-{uuid.uuid4().hex[:8]}",
        "event_id": snapshot["event_id"],
        "snapshot_version": snapshot["snapshot_version"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": DISCLAIMER,
        "meals": {
            "breakfast": {"style": "buffet", "items": [to_item(d) for d in breakfast]},
            "lunch": {
                "starter": to_item(starter),
                "mains": [to_item(first_main), to_item(second_main)],
                "dessert": to_item(lunch_dessert),
            },
            "dinner": {
                "main": to_item(dinner_main),
                "dessert": to_item(dinner_dessert),
            },
        },
        "warnings": [],
    }
