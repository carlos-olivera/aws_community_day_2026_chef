"""The deterministic validator: an ordered list of named, testable checks.

Pure Python. No LLM, no I/O, no randomness. Given the same menu, snapshot
and inventory it always returns the same report - which is exactly why it,
and not the model, gets to decide whether a menu may be published.
"""

from __future__ import annotations

from chef_andino.contracts.models import (
    DISCLAIMER,
    Check,
    EventSnapshot,
    InventoryItem,
    Menu,
    ValidationReport,
)
from chef_andino.validation.gates import iter_menu_items, run_hard_gates

VALIDATOR_VERSION = "1.0"


def _check_structure(menu: Menu) -> Check:
    """Day structure: buffet breakfast, lunch with 2 mains, single-main dinner.

    Pydantic already enforces most of this at parse time; this check restates
    the rules readably and catches anything constructed by hand.
    """
    problems: list[str] = []
    if not 4 <= len(menu.meals.breakfast.items) <= 8:
        problems.append("breakfast buffet needs 4-8 items")
    if len(menu.meals.lunch.mains) != 2:
        problems.append("lunch needs exactly 2 main options")
    ids = [i.dish_id for _, i in iter_menu_items(menu)]
    if len(ids) != len(set(ids)):
        problems.append("the same dish appears twice on the menu")
    return Check(
        id="structure",
        passed=not problems,
        message="; ".join(problems) or "day structure is correct",
    )


def _check_snapshot_version(menu: Menu, snapshot: EventSnapshot) -> Check:
    """The menu must cite the exact snapshot version this run was given.

    This is the snapshot pattern enforced: a menu computed from stale or
    future data is rejected even if it is otherwise perfect.
    """
    ok = menu.snapshot_version == snapshot.snapshot_version
    return Check(
        id="snapshot_version",
        passed=ok,
        message=(
            "menu matches snapshot"
            if ok
            else f"menu cites snapshot v{menu.snapshot_version} but the frozen "
            f"snapshot is v{snapshot.snapshot_version}"
        ),
    )


def _check_disclaimer(menu: Menu) -> Check:
    """The published menu must carry the exact demo disclaimer."""
    ok = menu.disclaimer == DISCLAIMER
    return Check(
        id="disclaimer",
        passed=ok,
        message="disclaimer present" if ok else "demo disclaimer missing or altered",
    )


def validate_menu(
    menu: Menu, snapshot: EventSnapshot, inventory: list[InventoryItem]
) -> ValidationReport:
    """Run every check and return the full report (never short-circuits).

    Reporting every failure at once lets the agent repair a menu in one
    revision instead of discovering problems one at a time.
    """
    checks: list[Check] = [
        _check_structure(menu),
        _check_snapshot_version(menu, snapshot),
        _check_disclaimer(menu),
    ]
    for gate_name, violations in run_hard_gates(menu, snapshot, inventory).items():
        checks.append(
            Check(id=gate_name, passed=False, message="; ".join(violations))
        )
    for gate_name in ("allergens", "dietary_coverage", "inventory", "spice"):
        if not any(c.id == gate_name for c in checks):
            checks.append(Check(id=gate_name, passed=True, message="ok"))

    return ValidationReport(
        passed=all(c.passed for c in checks),
        validator_version=VALIDATOR_VERSION,
        checks=checks,
    )
