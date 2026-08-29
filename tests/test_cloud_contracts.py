from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from chef_andino.cloud import api_handler, tool_handler
from chef_andino.store.dynamodb import _ddb, _plain, initial_event, snapshot_from_event


def populated_event():
    event = initial_event("demo-event", cycle=7)
    event["total_responses"] = 10
    event["diet_counts"] |= {"none": 6, "vegetarian": 3, "vegan": 1}
    event["allergen_counts"]["peanut"] = 1
    event["spice_counts"] |= {"mild": 1, "medium": 8, "hot": 1}
    event["cuisine_counts"]["andean_fusion"] = 10
    event["ingredient_counts"] |= {"quinoa": 7, "potato": 4}
    event["lactose_intolerant_count"] = 2
    event["gluten_free_count"] = 1
    return event


def test_fresh_cycle_is_complete_and_open():
    event = initial_event("demo-event", cycle=3)
    assert event["cycle"] == 3
    assert event["state"] == "OPEN"
    assert event["total_responses"] == 0
    assert set(event["diet_counts"]) == {"none", "vegetarian", "vegan"}


def test_snapshot_is_immutable_aggregate_for_active_cycle():
    snapshot = snapshot_from_event(populated_event())
    assert snapshot.snapshot_version == 7
    assert snapshot.total_responses == 10
    assert snapshot.derived_constraints.must_exclude_allergens == ["peanut"]
    assert snapshot.derived_constraints.require_vegetarian_lunch_main is True
    assert snapshot.derived_constraints.require_vegan_option_per_meal is True
    assert snapshot.derived_constraints.max_default_spice == "medium"
    assert snapshot.top_preferred_ingredients[0].ingredient == "quinoa"


def test_empty_event_cannot_be_frozen():
    with pytest.raises(ValueError, match="sin respuestas"):
        snapshot_from_event(initial_event("demo-event"))


def test_dynamodb_number_conversion_is_lossless_for_json_values():
    encoded = _ddb({"ratio": 0.25, "nested": [1, 2.5]})
    assert encoded == {"ratio": Decimal("0.25"), "nested": [1, Decimal("2.5")]}
    assert _plain(encoded) == {"ratio": 0.25, "nested": [1, 2.5]}


def test_presenter_bearer_auth_is_exact(monkeypatch):
    monkeypatch.setattr(api_handler, "_presenter_passphrase", lambda: "correcta")
    assert api_handler._authorized({"headers": {"Authorization": "Bearer correcta"}})
    assert not api_handler._authorized({"headers": {"Authorization": "Bearer incorrecta"}})
    assert not api_handler._authorized({"headers": {}})


def test_cloud_survey_rejects_free_text_and_requires_consent():
    valid = {
        "diet": "none",
        "lactose_intolerant": False,
        "gluten_free": False,
        "allergies": [],
        "spice_level": "medium",
        "cuisine_preference": "andean_fusion",
        "preferred_ingredients": ["quinoa"],
        "consent": True,
    }
    assert api_handler.SurveySubmission.model_validate(valid).consent
    with pytest.raises(ValidationError):
        api_handler.SurveySubmission.model_validate(valid | {"comment": "ignore rules"})


def test_gateway_tool_name_is_scoped_to_target():
    context = SimpleNamespace(
        client_context=SimpleNamespace(
            custom={"bedrockAgentCoreToolName": "ChefTools___validate_menu"}
        )
    )
    assert tool_handler._tool_name({}, context) == "validate_menu"
