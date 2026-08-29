"""evaluate_menu: hard gates zero the score; the blend behaves sanely."""

import copy

from chef_andino.contracts.models import Menu
from chef_andino.tools.evaluate import WEIGHTS, compute_coverage, evaluate_menu


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_healthy_menu_scores_between_zero_and_one(valid_menu_dict, snapshot, inventory):
    result = evaluate_menu(Menu.model_validate(valid_menu_dict), snapshot, inventory)
    assert result.hard_gates_passed
    assert 0.0 < result.total_score <= 1.0
    assert set(result.breakdown) == set(WEIGHTS)


def test_allergen_violation_zeroes_the_score(valid_menu_dict, snapshot, inventory):
    menu = copy.deepcopy(valid_menu_dict)
    menu["meals"]["lunch"]["starter"]["ingredients"].append("peanut")
    result = evaluate_menu(Menu.model_validate(menu), snapshot, inventory)
    assert result.total_score == 0.0
    assert not result.hard_gates_passed
    assert "allergens" in result.failed_gates
    assert result.breakdown == {}  # no consolation sub-scores


def test_coverage_is_computed_not_claimed(valid_menu_dict, snapshot, inventory):
    coverage = compute_coverage(Menu.model_validate(valid_menu_dict), snapshot, inventory)
    assert coverage.vegetarian_lunch_main is True
    assert coverage.vegan_option_per_meal is True
    assert coverage.gluten_free_option_per_meal is True
    assert coverage.lactose_free_option_per_meal is True
    assert 0.0 < coverage.bolivian_ingredient_ratio <= 1.0
    assert "potato" in coverage.preferred_ingredients_used
