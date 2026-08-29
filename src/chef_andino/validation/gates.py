"""Shared hard constraints - implemented once, enforced twice.

The evaluator uses these as *zero-score gates* (the agent's own compass says
"this candidate is worthless"), and the validator uses the same functions as
*publish blockers* (the door refuses to open). One implementation, two
enforcement points: the rules can never drift apart.

Each gate returns a list of human-readable violation strings; empty = pass.
"""

from __future__ import annotations

from chef_andino.contracts.models import (
    SPICE_ORDER,
    EventSnapshot,
    InventoryItem,
    Menu,
    MenuItem,
)


def iter_menu_items(menu: Menu) -> list[tuple[str, MenuItem]]:
    """Flatten the menu into (slot label, item) pairs for error messages."""
    meals = menu.meals
    pairs = [(f"breakfast item '{i.name}'", i) for i in meals.breakfast.items]
    pairs.append((f"lunch starter '{meals.lunch.starter.name}'", meals.lunch.starter))
    pairs += [(f"lunch main '{i.name}'", i) for i in meals.lunch.mains]
    pairs.append((f"lunch dessert '{meals.lunch.dessert.name}'", meals.lunch.dessert))
    pairs.append((f"dinner main '{meals.dinner.main.name}'", meals.dinner.main))
    pairs.append((f"dinner dessert '{meals.dinner.dessert.name}'", meals.dinner.dessert))
    return pairs


def check_allergens(
    menu: Menu, snapshot: EventSnapshot, inventory: list[InventoryItem]
) -> list[str]:
    """No dish may involve an allergen someone in the audience declared.

    Checks both the dish's own allergen labels AND the allergens of every
    ingredient it uses (the cross-check catches mislabelled dishes).
    """
    banned = set(snapshot.derived_constraints.must_exclude_allergens)
    if not banned:
        return []
    by_id = {item.ingredient_id: item for item in inventory}
    violations: list[str] = []
    for label, item in iter_menu_items(menu):
        direct = banned & set(item.allergens)
        if direct:
            violations.append(f"{label} is labelled with banned allergen(s): {sorted(direct)}")
        for ing in item.ingredients:
            inv = by_id.get(ing)
            if inv and (hit := banned & set(inv.allergens)):
                violations.append(
                    f"{label} uses ingredient '{ing}' which contains banned "
                    f"allergen(s): {sorted(hit)}"
                )
    return violations


def check_dietary_coverage(menu: Menu, snapshot: EventSnapshot) -> list[str]:
    """Vegetarian / vegan / gluten-free / lactose-free coverage rules.

    The interesting rule: dinner has a SINGLE main, so if anyone needs an
    option, the dinner main itself must be that option. One dish must fit
    everyone - the agent is solving constraints, not generating recipes.
    """
    c = snapshot.derived_constraints
    meals = menu.meals
    violations: list[str] = []

    def has_flag(item: MenuItem, flag: str) -> bool:
        return flag in item.dietary_flags

    per_meal_rules = [
        ("vegan", c.require_vegan_option_per_meal),
        ("gluten_free", c.require_gluten_free_option_per_meal),
        ("lactose_free", c.require_lactose_free_option_per_meal),
    ]
    for flag, required in per_meal_rules:
        if not required:
            continue
        if not any(has_flag(i, flag) for i in meals.breakfast.items):
            violations.append(f"breakfast buffet has no {flag} item")
        if not any(has_flag(m, flag) for m in meals.lunch.mains):
            violations.append(f"neither lunch main is {flag}")
        if not has_flag(meals.dinner.main, flag):
            violations.append(
                f"dinner main '{meals.dinner.main.name}' is not {flag} - "
                "it is the only option, so it must fit everyone"
            )

    if c.require_vegetarian_lunch_main:
        if not any(has_flag(m, "vegetarian") for m in meals.lunch.mains):
            violations.append("neither lunch main is vegetarian")
        if not has_flag(meals.dinner.main, "vegetarian"):
            violations.append(
                f"dinner main '{meals.dinner.main.name}' is not vegetarian - "
                "it is the only option, so it must fit everyone"
            )
    return violations


def check_inventory(menu: Menu, inventory: list[InventoryItem]) -> list[str]:
    """Every ingredient of every dish must exist in stock (quantity > 0)."""
    by_id = {item.ingredient_id: item for item in inventory}
    violations: list[str] = []
    for label, item in iter_menu_items(menu):
        for ing in item.ingredients:
            inv = by_id.get(ing)
            if inv is None:
                violations.append(f"{label} uses unknown ingredient '{ing}'")
            elif inv.quantity <= 0:
                violations.append(f"{label} uses out-of-stock ingredient '{ing}'")
    return violations


def check_spice(menu: Menu, snapshot: EventSnapshot) -> list[str]:
    """No dish may be hotter than what ~90% of the audience enjoys."""
    limit = SPICE_ORDER[snapshot.derived_constraints.max_default_spice]
    return [
        f"{label} is '{item.spice_level}' but the audience limit is "
        f"'{snapshot.derived_constraints.max_default_spice}'"
        for label, item in iter_menu_items(menu)
        if SPICE_ORDER[item.spice_level] > limit
    ]


def run_hard_gates(
    menu: Menu, snapshot: EventSnapshot, inventory: list[InventoryItem]
) -> dict[str, list[str]]:
    """Run every hard gate; return {gate_name: violations} for failing gates."""
    results = {
        "allergens": check_allergens(menu, snapshot, inventory),
        "dietary_coverage": check_dietary_coverage(menu, snapshot),
        "inventory": check_inventory(menu, inventory),
        "spice": check_spice(menu, snapshot),
    }
    return {name: violations for name, violations in results.items() if violations}
