"""One passing and one failing case for every deterministic validator rule."""

import copy

from chef_andino.contracts.models import Menu
from chef_andino.validation.validator import validate_menu


def run(menu_dict, snapshot, inventory):
    return validate_menu(Menu.model_validate(menu_dict), snapshot, inventory)


def check_ids(report, passed: bool) -> set[str]:
    return {c.id for c in report.checks if c.passed is passed}


def test_valid_menu_passes_everything(valid_menu_dict, snapshot, inventory):
    report = run(valid_menu_dict, snapshot, inventory)
    assert report.passed, [c.message for c in report.checks if not c.passed]
    assert {"structure", "snapshot_version", "disclaimer", "allergens",
            "dietary_coverage", "inventory", "spice"} <= check_ids(report, True)


def test_banned_allergen_is_rejected(valid_menu_dict, snapshot, inventory):
    menu = copy.deepcopy(valid_menu_dict)
    # Peanut is banned by the seed data; sneak it into the lunch starter.
    menu["meals"]["lunch"]["starter"]["ingredients"].append("peanut")
    report = run(menu, snapshot, inventory)
    assert not report.passed
    assert "allergens" in check_ids(report, False)


def test_mislabelled_dish_is_caught_via_ingredients(valid_menu_dict, snapshot, inventory):
    # The dish claims no allergens, but its ingredient list betrays it.
    menu = copy.deepcopy(valid_menu_dict)
    starter = menu["meals"]["lunch"]["starter"]
    starter["ingredients"].append("peanut")
    assert "peanut" not in starter["allergens"]
    assert "allergens" in check_ids(run(menu, snapshot, inventory), False)


def test_non_vegetarian_dinner_main_is_rejected(valid_menu_dict, snapshot, inventory):
    menu = copy.deepcopy(valid_menu_dict)
    main = menu["meals"]["dinner"]["main"]
    main["dietary_flags"] = []  # a meat dish in the single-option slot
    report = run(menu, snapshot, inventory)
    assert "dietary_coverage" in check_ids(report, False)
    assert "only option" in "; ".join(
        c.message for c in report.checks if c.id == "dietary_coverage"
    )


def test_unknown_ingredient_is_rejected(valid_menu_dict, snapshot, inventory):
    menu = copy.deepcopy(valid_menu_dict)
    menu["meals"]["dinner"]["dessert"]["ingredients"].append("unicorn_meat")
    assert "inventory" in check_ids(run(menu, snapshot, inventory), False)


def test_out_of_stock_ingredient_is_rejected(valid_menu_dict, snapshot, inventory):
    depleted = [
        item.model_copy(update={"quantity": 0.0})
        if item.ingredient_id == "potato" else item
        for item in inventory
    ]
    assert "inventory" in check_ids(run(valid_menu_dict, snapshot, depleted), False)


def test_too_spicy_dish_is_rejected(valid_menu_dict, snapshot, inventory):
    menu = copy.deepcopy(valid_menu_dict)
    menu["meals"]["lunch"]["mains"][0]["spice_level"] = "hot"  # limit is medium
    assert "spice" in check_ids(run(menu, snapshot, inventory), False)


def test_stale_snapshot_version_is_rejected(valid_menu_dict, snapshot, inventory):
    menu = copy.deepcopy(valid_menu_dict)
    menu["snapshot_version"] = 99
    assert "snapshot_version" in check_ids(run(menu, snapshot, inventory), False)


def test_duplicate_dish_is_rejected(valid_menu_dict, snapshot, inventory):
    menu = copy.deepcopy(valid_menu_dict)
    menu["meals"]["dinner"]["dessert"] = menu["meals"]["lunch"]["dessert"]
    assert "structure" in check_ids(run(menu, snapshot, inventory), False)


def test_altered_disclaimer_does_not_even_parse(valid_menu_dict):
    import pytest
    from pydantic import ValidationError

    menu = copy.deepcopy(valid_menu_dict)
    menu["disclaimer"] = "trust me, it is fine"
    with pytest.raises(ValidationError):
        Menu.model_validate(menu)
