"""Tool 6/6: ``validate_and_publish_menu`` - where the three control layers meet.

    LLM proposes a menu
            |
            v
    deterministic validator   (validation/)
            |
            v
    policy engine             (policy/)  -- ALWAYS consulted, decision audited
            |
       DENY '- ALLOW
            |      |
       reject   publish + state -> PUBLISHED

The publish gate never trusts the caller: it re-validates, recomputes
coverage, and asks the policy engine with the REAL facts in the context.
A ``skip_validation`` switch exists purely so ``chef demo-governance`` can
show what happens when something tries to bypass the validator: DENY.
"""

from __future__ import annotations

import uuid
from typing import Callable

from chef_andino.contracts.models import Menu
from chef_andino.lifecycle.states import EventState, transition
from chef_andino.policy.engine import LocalPolicyEngine, PolicyRequest
from chef_andino.store.base import EventStore
from chef_andino.tools.base import Tool, ToolResult
from chef_andino.tools.evaluate import compute_coverage
from chef_andino.tools.inventory import InventorySource
from chef_andino.validation.validator import validate_menu

AGENT_PRINCIPAL = "agent/chef-andino"

AuditSink = Callable[[dict], None]


class MenuPublisher:
    """Validator -> policy -> store, with every decision written to the audit."""

    def __init__(
        self,
        store: EventStore,
        policy: LocalPolicyEngine,
        inventory: InventorySource,
        event_id: str,
        audit: AuditSink = lambda record: None,
    ) -> None:
        """Wire the three layers together for one event."""
        self._store = store
        self._policy = policy
        self._inventory = inventory
        self._event_id = event_id
        self._audit = audit

    def validate_and_publish(self, menu: dict, skip_validation: bool = False) -> ToolResult:
        """Run the full gate. Returns ok=False with the reasons on any refusal."""
        try:
            parsed = Menu.model_validate(menu)
        except Exception as exc:  # pydantic.ValidationError
            return ToolResult(
                ok=False,
                error=f"menu does not match the schema, validation cannot even start: {exc}",
            )

        snapshot = self._store.get_snapshot(self._event_id)
        inventory = self._inventory.list()
        report = None if skip_validation else validate_menu(parsed, snapshot, inventory)

        # The policy context carries FACTS computed here - not claims made by
        # the caller. This is what "enforcement outside the agent" means.
        context = {
            "validation_passed": bool(report and report.passed),
            "event_state": self._store.get_event(self._event_id).state.value,
            "snapshot_version_matches": parsed.snapshot_version == snapshot.snapshot_version,
        }
        decision = self._policy.decide(
            PolicyRequest(
                principal=AGENT_PRINCIPAL,
                action="publish_menu",
                resource=f"event/{self._event_id}",
                context=context,
            )
        )
        self._audit(
            {
                "action": "publish_menu",
                "principal": AGENT_PRINCIPAL,
                "context": context,
                "effect": decision.effect,
                "policy_id": decision.policy_id,
                "reason": decision.reason,
            }
        )

        if decision.effect == "DENY":
            failed = [c.model_dump() for c in report.checks if not c.passed] if report else []
            return ToolResult(
                ok=False,
                error=f"policy DENIED publish_menu: {decision.reason}",
                data={"failed_checks": failed, "policy_id": decision.policy_id},
            )

        published = parsed.model_copy(
            update={
                # Candidates carry throwaway ids; the published record gets
                # its own, assigned here - not by the agent.
                "menu_id": f"menu-{uuid.uuid4().hex[:8]}",
                "coverage": compute_coverage(parsed, snapshot, inventory),
                "validation": report,
            }
        )
        self._store.save_menu(published)
        transition(self._store, self._event_id, EventState.PUBLISHED)
        return ToolResult(
            ok=True,
            data={"menu_id": published.menu_id, "policy_id": decision.policy_id},
        )


def make_publish_tool(publisher: MenuPublisher) -> Tool:
    """Wrap the publisher as the agent-facing tool (no bypass switch exposed)."""

    def fn(menu: dict) -> ToolResult:
        return publisher.validate_and_publish(menu)

    return Tool(
        name="validate_and_publish_menu",
        description=(
            "Validate a menu against every hard constraint and, if policy "
            "allows, publish it. This is the only way to finish the mission. "
            "On refusal, the result lists exactly which checks failed."
        ),
        args_schema={
            "type": "object",
            "properties": {"menu": {"type": "object"}},
            "required": ["menu"],
        },
        fn=fn,
    )
