"""The policy decision matrix: default DENY, explicit ALLOW conditions."""

import pytest

from chef_andino.policy.engine import LocalPolicyEngine, PolicyRequest

ENGINE = LocalPolicyEngine()


def publish_request(**context_overrides) -> PolicyRequest:
    context = {
        "validation_passed": True,
        "event_state": "GENERATING",
        "snapshot_version_matches": True,
    } | context_overrides
    return PolicyRequest(
        principal="agent/chef-andino",
        action="publish_menu",
        resource="event/test-event",
        context=context,
    )


def test_happy_path_is_allowed():
    decision = ENGINE.decide(publish_request())
    assert decision.effect == "ALLOW"
    assert decision.policy_id == "allow-validated-publish"


@pytest.mark.parametrize(
    "overrides",
    [
        {"validation_passed": False},
        {"event_state": "OPEN"},
        {"event_state": "FROZEN"},
        {"snapshot_version_matches": False},
    ],
)
def test_unmet_conditions_are_denied(overrides):
    decision = ENGINE.decide(publish_request(**overrides))
    assert decision.effect == "DENY"
    assert decision.policy_id == "default-deny"
    key = next(iter(overrides))
    assert key in decision.reason  # the denial explains itself


def test_unknown_principal_is_denied():
    request = PolicyRequest(
        principal="agent/impostor", action="publish_menu",
        resource="event/test-event",
        context={"validation_passed": True, "event_state": "GENERATING",
                 "snapshot_version_matches": True},
    )
    assert ENGINE.decide(request).effect == "DENY"


def test_reads_are_allowed_without_conditions():
    for action in ("read_snapshot", "read_inventory", "search_knowledge"):
        request = PolicyRequest(
            principal="agent/chef-andino", action=action, resource="event/x"
        )
        assert ENGINE.decide(request).effect == "ALLOW"


def test_unlisted_action_is_denied():
    request = PolicyRequest(
        principal="agent/chef-andino", action="delete_everything", resource="event/x"
    )
    decision = ENGINE.decide(request)
    assert decision.effect == "DENY"
    assert "no rule allows" in decision.reason
