"""The harness enforces budgets no matter how the planner behaves."""

from rich.console import Console

from chef_andino.agent.runner import AgentRunner
from chef_andino.agent.trace import TraceWriter
from chef_andino.lifecycle.states import EventState
from chef_andino.planner.base import ToolCall
from chef_andino.tools.factory import build_local_toolset

QUIET = Console(quiet=True)


class RunawayPlanner:
    """A planner that never stops asking for the snapshot."""

    def next_action(self, state):
        return ToolCall("get_event_snapshot", rationale="again!")


class WebObsessedPlanner:
    """A planner that only ever wants to browse the internet."""

    def next_action(self, state):
        return ToolCall("research_web", args={"query": "more inspiration"})


def make_runner(store, settings, planner):
    trace = TraceWriter(settings.runs_dir, QUIET)
    tools = build_local_toolset(store, settings, "test-event", audit=trace.audit_sink)
    return AgentRunner(planner, tools, store, settings.budget, trace)


def test_runaway_planner_halts_at_max_iterations(store, frozen_event, settings):
    result = make_runner(store, settings, RunawayPlanner()).run(frozen_event)
    assert not result.published
    assert result.steps == settings.budget.max_iterations
    assert result.finish_reason == "budget_exhausted"


def test_failed_run_returns_event_to_frozen(store, frozen_event, settings):
    make_runner(store, settings, RunawayPlanner()).run(frozen_event)
    assert store.get_event(frozen_event).state is EventState.FROZEN


def test_web_budget_is_enforced_per_tool(store, frozen_event, settings):
    class Recorder(WebObsessedPlanner):
        def __init__(self):
            self.results = []

        def next_action(self, state):
            if state.last_result() is not None:
                self.results.append(state.last_result())
            return super().next_action(state)

    planner = Recorder()
    make_runner(store, settings, planner).run(frozen_event)
    max_web = settings.budget.max_web_queries
    allowed = [r for r in planner.results if r.ok]
    refused = [r for r in planner.results if not r.ok]
    assert len(allowed) == max_web
    assert refused and all("budget" in r.error for r in refused)


def test_publish_attempts_are_capped(store, frozen_event, settings, valid_menu_dict):
    class PublishSpammer:
        def __init__(self):
            self.refusals = 0

        def next_action(self, state):
            last = state.last_result()
            if last is not None and not last.ok and "budget" in (last.error or ""):
                self.refusals += 1
            menu = dict(valid_menu_dict, snapshot_version=99)  # never valid
            return ToolCall("validate_and_publish_menu", args={"menu": menu})

    planner = PublishSpammer()
    make_runner(store, settings, planner).run(frozen_event)
    assert planner.refusals >= 1  # attempts beyond 1 + retries were refused


def test_unknown_tool_becomes_an_error_result_not_a_crash(store, frozen_event, settings):
    class ConfusedPlanner:
        def __init__(self):
            self.last_error = None

        def next_action(self, state):
            if state.last_result() is not None:
                self.last_error = state.last_result().error
            return ToolCall("order_pizza", args={})

    planner = ConfusedPlanner()
    make_runner(store, settings, planner).run(frozen_event)
    assert "unknown tool" in planner.last_error
