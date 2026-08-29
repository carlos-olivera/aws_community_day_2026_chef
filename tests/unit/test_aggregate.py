"""build_snapshot: counts, percentages and derived-constraint edge cases."""

from datetime import datetime, timezone

import pytest

from chef_andino.contracts.models import SurveyResponse
from chef_andino.lifecycle.aggregate import build_snapshot


def make_response(i: int = 0, **overrides) -> SurveyResponse:
    base = dict(
        response_id=f"00000000-0000-0000-0000-{i:012d}",
        event_id="test-event",
        submitted_at=datetime(2026, 8, 29, 9, 0, tzinfo=timezone.utc),
        diet="none",
        lactose_intolerant=False,
        gluten_free=False,
        allergies=[],
        spice_level="medium",
        cuisine_preference="no_preference",
        preferred_ingredients=[],
        consent=True,
    )
    return SurveyResponse.model_validate(base | overrides)


def test_counts_and_totals(responses):
    snap = build_snapshot("test-event", responses, version=1)
    assert snap.total_responses == 40
    assert snap.diet_counts == {"none": 30, "vegetarian": 6, "vegan": 4}
    assert snap.lactose_intolerant_count == 10
    assert snap.gluten_free_count == 6
    assert snap.allergen_counts == {"peanut": 2, "shellfish": 1}


def test_derived_constraints_from_seed(responses):
    c = build_snapshot("test-event", responses, version=1).derived_constraints
    assert c.must_exclude_allergens == ["peanut", "shellfish"]
    assert c.require_vegetarian_lunch_main is True
    assert c.require_vegan_option_per_meal is True
    assert c.require_gluten_free_option_per_meal is True
    assert c.require_lactose_free_option_per_meal is True
    assert c.max_default_spice == "medium"


def test_all_omnivores_relaxes_everything():
    snap = build_snapshot("e", [make_response(i, spice_level="hot") for i in range(10)], 1)
    c = snap.derived_constraints
    assert c.must_exclude_allergens == []
    assert c.require_vegetarian_lunch_main is False
    assert c.require_vegan_option_per_meal is False
    assert c.max_default_spice == "hot"


def test_one_vegan_forces_vegan_option():
    responses = [make_response(0, diet="vegan")] + [make_response(i) for i in range(1, 10)]
    c = build_snapshot("e", responses, 1).derived_constraints
    assert c.require_vegan_option_per_meal is True
    assert c.require_vegetarian_lunch_main is True


def test_spice_threshold_is_90_percent():
    # 1 mild-only among 10 = 90% accept medium -> medium is allowed.
    responses = [make_response(0, spice_level="mild")] + [
        make_response(i, spice_level="medium") for i in range(1, 10)
    ]
    assert build_snapshot("e", responses, 1).derived_constraints.max_default_spice == "medium"
    # 2 mild-only among 10 = 80% accept medium -> stay mild.
    responses = [make_response(i, spice_level="mild") for i in range(2)] + [
        make_response(i, spice_level="medium") for i in range(2, 10)
    ]
    assert build_snapshot("e", responses, 1).derived_constraints.max_default_spice == "mild"


def test_zero_responses_raises():
    with pytest.raises(ValueError, match="zero responses"):
        build_snapshot("e", [], 1)
