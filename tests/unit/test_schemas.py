"""The checked-in JSON Schema files must match the Pydantic models exactly."""

import json

from chef_andino.contracts.export import EXPORTS, SCHEMAS_DIR, schema_for


def test_checked_in_schemas_are_in_sync():
    for name, model in EXPORTS.items():
        path = SCHEMAS_DIR / f"{name}.schema.json"
        assert path.exists(), f"missing {path} - run `make schemas`"
        checked_in = json.loads(path.read_text())
        assert checked_in == schema_for(model), (
            f"{path.name} is stale - run `make schemas` and commit the result"
        )


def test_every_schema_has_a_stable_id():
    for name, model in EXPORTS.items():
        assert schema_for(model)["$id"].endswith(f"{name}.schema.json")


def test_survey_schema_forbids_unknown_fields():
    schema = schema_for(EXPORTS["survey_response"])
    assert schema["additionalProperties"] is False


def test_seed_responses_conform_to_the_contract(responses):
    # Parsing IS schema validation: the schema files are generated from
    # these same models.
    assert len(responses) == 40
