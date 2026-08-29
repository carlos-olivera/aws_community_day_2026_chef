"""Planners: the seam where the LLM plugs in.

Teaching concept: the "brain" is swappable. The agent loop drives a
:class:`~chef_andino.planner.base.Planner` that returns either a ToolCall or
Finish. :class:`~chef_andino.planner.mock.MockPlanner` is a deterministic,
readable stand-in that runs offline for free;
:class:`~chef_andino.planner.bedrock.BedrockPlanner` (optional, ``[aws]``
extra) is a real model on Amazon Bedrock - and the loop cannot tell the
difference. That indifference is the whole point.
"""

from chef_andino.planner.base import AgentState, Finish, Planner, PlannerAction, ToolCall

__all__ = ["AgentState", "Finish", "Planner", "PlannerAction", "ToolCall"]
