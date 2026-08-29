"""Tool 5/6: ``evaluate_menu`` - the agent's own compass.

"The LLM proposes. Code calculates." Scoring is plain arithmetic the agent
can run on candidates BEFORE trying the door (the validator). In the cloud
phase the same computation runs inside AgentCore Code Interpreter.

Hard gates come first and zero the score: an allergy violation is not
"a low score", it is worthless. Then the weighted blend from the talk:

    score = preference_coverage      * 0.35
          + bolivian_identity        * 0.25
          + ingredient_availability  * 0.15
          + operational_simplicity   * 0.15
          + menu_variety             * 0.10

Every sub-score is a short, documented function - illustrative by design.
"""

from __future__ import annotations

from chef_andino.contracts.models import (
    Coverage,
    EvaluationResult,
    EventSnapshot,
    InventoryItem,
    Menu,
)
from chef_andino.tools.base import Tool, ToolResult
from chef_andino.validation.gates import iter_menu_items, run_hard_gates

WEIGHTS = {
    "preference_coverage": 0.35,
    "bolivian_identity": 0.25,
    "ingredient_availability": 0.15,
    "operational_simplicity": 0.15,
    "menu_variety": 0.10,
}

# "Comfortable stock" threshold (kg/l/units) for the availability sub-score.
COMFORT_STOCK = 5


def _used_ingredients(menu: Menu) -> list[str]:
    """Every ingredient reference on the menu (with repetitions)."""
    return [ing for _, item in iter_menu_items(menu) for ing in item.ingredients]


def compute_coverage(
    menu: Menu, snapshot: EventSnapshot, inventory: list[InventoryItem]
) -> Coverage:
    """Compute (never ask the LLM to claim) who this menu serves."""
    meals = menu.meals

    def option_per_meal(flag: str) -> bool:
        return (
            any(flag in i.dietary_flags for i in meals.breakfast.items)
            and any(flag in m.dietary_flags for m in meals.lunch.mains)
            and flag in meals.dinner.main.dietary_flags
        )

    used = set(_used_ingredients(menu))
    bolivian = {i.ingredient_id for i in inventory if i.is_bolivian}
    preferred = {c.ingredient for c in snapshot.top_preferred_ingredients}
    return Coverage(
        vegetarian_lunch_main=any(
            "vegetarian" in m.dietary_flags for m in meals.lunch.mains
        ),
        vegan_option_per_meal=option_per_meal("vegan"),
        gluten_free_option_per_meal=option_per_meal("gluten_free"),
        lactose_free_option_per_meal=option_per_meal("lactose_free"),
        preferred_ingredients_used=sorted(used & preferred),
        bolivian_ingredient_ratio=round(len(used & bolivian) / len(used), 3) if used else 0.0,
    )


def _preference_coverage(menu: Menu, snapshot: EventSnapshot) -> float:
    """Share of the audience's favourite ingredients that made the menu."""
    preferred = {c.ingredient for c in snapshot.top_preferred_ingredients}
    if not preferred:
        return 1.0
    return len(set(_used_ingredients(menu)) & preferred) / len(preferred)


def _bolivian_identity(menu: Menu, inventory: list[InventoryItem]) -> float:
    """Half dish heritage, half ingredient origin."""
    items = [item for _, item in iter_menu_items(menu)]
    dish_share = sum(1 for i in items if i.bolivian_origin) / len(items)
    used = set(_used_ingredients(menu))
    bolivian = {i.ingredient_id for i in inventory if i.is_bolivian}
    ingredient_share = len(used & bolivian) / len(used) if used else 0.0
    return 0.5 * dish_share + 0.5 * ingredient_share


def _ingredient_availability(menu: Menu, inventory: list[InventoryItem]) -> float:
    """Share of used ingredients with comfortable stock (>= COMFORT_STOCK)."""
    by_id = {i.ingredient_id: i for i in inventory}
    used = set(_used_ingredients(menu))
    if not used:
        return 0.0
    comfortable = sum(
        1 for ing in used if ing in by_id and by_id[ing].quantity >= COMFORT_STOCK
    )
    return comfortable / len(used)


def _operational_simplicity(menu: Menu) -> float:
    """1.0 when every dish is trivial (complexity 1), 0.0 when all are 3."""
    items = [item for _, item in iter_menu_items(menu)]
    mean_complexity = sum(i.complexity for i in items) / len(items)
    return 1.0 - (mean_complexity - 1) / 2


def _menu_variety(menu: Menu) -> float:
    """Distinct / total ingredient references: 1.0 means nothing repeats."""
    refs = _used_ingredients(menu)
    return len(set(refs)) / len(refs) if refs else 0.0


def evaluate_menu(
    menu: Menu, snapshot: EventSnapshot, inventory: list[InventoryItem]
) -> EvaluationResult:
    """Hard gates first (score 0 on any failure), weighted blend second."""
    gate_failures = run_hard_gates(menu, snapshot, inventory)
    if gate_failures:
        return EvaluationResult(
            total_score=0.0,
            breakdown={},
            hard_gates_passed=False,
            failed_gates=sorted(gate_failures),
        )
    breakdown = {
        "preference_coverage": _preference_coverage(menu, snapshot),
        "bolivian_identity": _bolivian_identity(menu, inventory),
        "ingredient_availability": _ingredient_availability(menu, inventory),
        "operational_simplicity": _operational_simplicity(menu),
        "menu_variety": _menu_variety(menu),
    }
    total = sum(WEIGHTS[k] * v for k, v in breakdown.items())
    return EvaluationResult(
        total_score=round(total, 4),
        breakdown={k: round(v, 4) for k, v in breakdown.items()},
        hard_gates_passed=True,
    )


def make_evaluate_tool(
    snapshot_getter, inventory_getter
) -> Tool:
    """Wrap scoring as a tool.

    Snapshot and inventory are fetched fresh inside the tool, so the agent
    cannot feed the evaluator a doctored world.
    """

    def fn(menu: dict) -> ToolResult:
        try:
            parsed = Menu.model_validate(menu)
        except Exception as exc:  # pydantic.ValidationError
            return ToolResult(ok=False, error=f"menu does not match the contract: {exc}")
        result = evaluate_menu(parsed, snapshot_getter(), inventory_getter())
        return ToolResult(ok=True, data=result.model_dump(mode="json"))

    return Tool(
        name="evaluate_menu",
        description=(
            "Score a candidate menu (0..1). Any hard-constraint violation "
            "(allergen, coverage, stock, spice) zeroes the score and names "
            "the failed gate. Use this before trying to publish."
        ),
        args_schema={
            "type": "object",
            "properties": {"menu": {"type": "object"}},
            "required": ["menu"],
        },
        fn=fn,
    )
