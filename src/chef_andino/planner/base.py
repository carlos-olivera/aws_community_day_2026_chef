"""The Planner protocol: "given what has happened, what next?"."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Union

from chef_andino.tools.base import ToolResult


@dataclass(frozen=True)
class ToolCall:
    """The planner wants to invoke a tool."""

    tool_name: str
    args: dict = field(default_factory=dict)
    rationale: str = ""  # one line of "why" - shown live in the trace


@dataclass(frozen=True)
class Finish:
    """The planner is done (successfully or not)."""

    reason: str  # "published" | "budget_exhausted" | "gave_up: ..."


PlannerAction = Union[ToolCall, Finish]


@dataclass
class AgentState:
    """Everything a planner may look at: the mission id and the history."""

    event_id: str
    history: list[tuple[ToolCall, ToolResult]] = field(default_factory=list)

    def last_result(self) -> ToolResult | None:
        """The result of the most recent tool call, if any."""
        return self.history[-1][1] if self.history else None


class Planner(Protocol):
    """Port: any brain that can decide the next action.

    Implementations: :class:`~chef_andino.planner.mock.MockPlanner`
    (deterministic, offline) and
    :class:`~chef_andino.planner.bedrock.BedrockPlanner` (a real LLM).
    """

    def next_action(self, state: AgentState) -> PlannerAction:
        """Return the next tool call, or Finish."""
        ...
