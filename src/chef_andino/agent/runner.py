"""AgentRunner: the bounded loop. This file IS the "agent" everyone talks about.

    while budget remains:
        action = planner.next_action(state)      # the probabilistic part
        result = tools[action].fn(**action.args) # the deterministic part
        remember, trace, repeat

Notice what the runner owns and the planner does not: lifecycle transitions,
budget enforcement, and the trace. A hostile or broken planner can waste its
budget, but it cannot loop forever, skip governance, or flip event states.
"""

from __future__ import annotations

from dataclasses import dataclass

from chef_andino.agent.budgets import BudgetExceeded, BudgetTracker
from chef_andino.agent.trace import TraceWriter
from chef_andino.config import Budget
from chef_andino.lifecycle.states import EventState, transition
from chef_andino.planner.base import AgentState, Finish, Planner, ToolCall
from chef_andino.store.base import EventStore
from chef_andino.tools.base import ToolRegistry, ToolResult


@dataclass
class RunResult:
    """What one mission produced."""

    run_id: str
    published: bool
    steps: int
    finish_reason: str


class AgentRunner:
    """Drive a planner against a tool registry, within budgets, with a trace."""

    def __init__(
        self,
        planner: Planner,
        tools: ToolRegistry,
        store: EventStore,
        budget: Budget,
        trace: TraceWriter,
    ) -> None:
        """Assemble the harness for one mission."""
        self._planner = planner
        self._tools = tools
        self._store = store
        self._budget = budget
        self._trace = trace

    def run(self, event_id: str) -> RunResult:
        """Execute the mission: FROZEN -> GENERATING -> (PUBLISHED | FROZEN)."""
        transition(self._store, event_id, EventState.GENERATING)
        tracker = BudgetTracker(self._budget)
        state = AgentState(event_id=event_id)
        self._trace.event("run_started", event_id=event_id, tools=self._tools.names())

        finish_reason = "budget_exhausted"
        while True:
            action = self._planner.next_action(state)
            if isinstance(action, Finish):
                finish_reason = action.reason
                self._trace.event("finish", reason=action.reason)
                break

            # Only actions that DO something consume the iteration budget;
            # deciding to stop is always free.
            try:
                tracker.charge_iteration()
            except BudgetExceeded as exc:
                self._trace.event("budget_exhausted", detail=str(exc))
                break

            result = self._execute(action, tracker)
            self._trace.step(tracker.iterations, action, result, tracker.remaining())
            state.history.append((action, result))

        published = self._store.get_event(event_id).state == EventState.PUBLISHED
        if not published:
            # A failed mission returns the event to FROZEN so it can be retried.
            transition(self._store, event_id, EventState.FROZEN)
        self._trace.event("run_finished", published=published, steps=tracker.iterations)
        return RunResult(
            run_id=self._trace.run_id,
            published=published,
            steps=tracker.iterations,
            finish_reason=finish_reason,
        )

    def _execute(self, action: ToolCall, tracker: BudgetTracker) -> ToolResult:
        """Charge budgets, then run the tool. Failures become results, not crashes."""
        try:
            tracker.charge_tool(action.tool_name)
        except BudgetExceeded as exc:
            return ToolResult(ok=False, error=str(exc))
        try:
            tool = self._tools.get(action.tool_name)
            return tool.fn(**action.args)
        except KeyError as exc:
            return ToolResult(ok=False, error=str(exc))
        except Exception as exc:  # a tool bug must not kill the mission
            return ToolResult(ok=False, error=f"tool crashed: {exc}")
