"""The whole backbone in one test: seed -> freeze -> agent -> published menu.

This is the automated version of the classroom walkthrough in the README.
"""

import json

from rich.console import Console

from chef_andino.agent.runner import AgentRunner
from chef_andino.agent.trace import TraceWriter
from chef_andino.contracts.models import DISCLAIMER, Menu
from chef_andino.lifecycle.states import EventState
from chef_andino.planner.mock import MockPlanner
from chef_andino.tools.factory import build_local_toolset


def test_full_pipeline(store, frozen_event, settings):
    trace = TraceWriter(settings.runs_dir, Console(quiet=True))
    tools = build_local_toolset(store, settings, frozen_event, audit=trace.audit_sink)
    runner = AgentRunner(MockPlanner(), tools, store, settings.budget, trace)

    result = runner.run(frozen_event)

    # The mission succeeded within its budgets.
    assert result.published
    assert result.finish_reason == "published"
    assert result.steps <= settings.budget.max_iterations

    # The event reached its terminal state.
    assert store.get_event(frozen_event).state is EventState.PUBLISHED

    # The published menu conforms to the contract (parsing IS validation)
    # and carries the honest, computed reports.
    menu = store.get_menu(frozen_event)
    assert isinstance(menu, Menu)
    assert menu.snapshot_version == 1
    assert menu.disclaimer == DISCLAIMER
    assert menu.validation is not None and menu.validation.passed
    assert menu.coverage is not None and menu.coverage.vegan_option_per_meal
    # It survives a JSON round-trip against the same contract.
    Menu.model_validate(json.loads(menu.model_dump_json()))

    # The trace tells the governance story: at least one DENY, a final ALLOW.
    audit_lines = [
        json.loads(line)
        for line in (trace.run_dir / "audit.jsonl").read_text().splitlines()
    ]
    effects = [entry["effect"] for entry in audit_lines]
    assert "DENY" in effects
    assert effects[-1] == "ALLOW"

    # And the step trace recorded every tool call.
    step_lines = [
        json.loads(line)
        for line in (trace.run_dir / "trace.jsonl").read_text().splitlines()
        if json.loads(line)["kind"] == "step"
    ]
    assert len(step_lines) == result.steps
    assert step_lines[0]["tool"] == "get_event_snapshot"
    assert step_lines[-1]["tool"] == "validate_and_publish_menu"
