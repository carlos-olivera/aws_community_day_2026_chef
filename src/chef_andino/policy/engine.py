"""A tiny default-deny policy engine over ``policies.yaml``.

Roughly 60 lines that make the talk's best moment possible:

    Agent:  publish_menu(...)
    Policy: DENIED - validation_passed is false

The agent WANTED to publish. The system did not let it. See
docs/governance.md for the Cedar (AgentCore Policy) equivalent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

DEFAULT_POLICIES_PATH = Path(__file__).resolve().parent / "policies.yaml"


@dataclass(frozen=True)
class PolicyRequest:
    """Who wants to do what, to what, under which circumstances."""

    principal: str
    action: str
    resource: str
    context: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyDecision:
    """The verdict, with enough detail to explain itself on a big screen."""

    effect: Literal["ALLOW", "DENY"]
    reason: str
    policy_id: str  # "default-deny" when no rule matched


class LocalPolicyEngine:
    """Evaluate requests against the YAML rules. Default effect: DENY."""

    def __init__(self, policies_path: Path = DEFAULT_POLICIES_PATH) -> None:
        """Load the rule list once at construction."""
        self._rules: list[dict] = yaml.safe_load(policies_path.read_text())

    def decide(self, request: PolicyRequest) -> PolicyDecision:
        """Return the first matching rule's effect, or the default DENY."""
        for rule in self._rules:
            if not self._matches(rule, request):
                continue
            return PolicyDecision(
                effect=rule["effect"],
                reason=f"matched rule '{rule['id']}'",
                policy_id=rule["id"],
            )
        return PolicyDecision(
            effect="DENY",
            reason=self._explain_denial(request),
            policy_id="default-deny",
        )

    @staticmethod
    def _matches(rule: dict, request: PolicyRequest) -> bool:
        if rule.get("principal") != request.principal:
            return False
        actions = rule.get("action")
        actions = actions if isinstance(actions, list) else [actions]
        if request.action not in actions:
            return False
        for key, expected in (rule.get("when") or {}).items():
            if request.context.get(key) != expected:
                return False
        return True

    def _explain_denial(self, request: PolicyRequest) -> str:
        """Explain WHY nothing matched - great on stage, great in an audit log."""
        for rule in self._rules:
            actions = rule.get("action")
            actions = actions if isinstance(actions, list) else [actions]
            if request.action in actions and rule.get("principal") == request.principal:
                unmet = [
                    f"{key} is {request.context.get(key)!r} (rule requires {expected!r})"
                    for key, expected in (rule.get("when") or {}).items()
                    if request.context.get(key) != expected
                ]
                return (
                    f"no rule matched; closest rule '{rule['id']}' requires "
                    + ", ".join(unmet)
                )
        return f"no rule allows principal '{request.principal}' to '{request.action}'"
