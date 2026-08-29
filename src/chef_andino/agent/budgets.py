"""Budget tracking: the deterministic wall around the agent's freedom.

    Autonomy is not unlimited freedom.
    Autonomy is freedom to decide within explicit boundaries.

The tracker charges specific tools against specific budgets. The planner is
never consulted: even a runaway LLM cannot loop forever or hammer the web.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from chef_andino.config import Budget


class BudgetExceeded(Exception):
    """Raised when an action would exceed one of the mission budgets."""


@dataclass
class BudgetTracker:
    """Counts what one run has spent, and refuses overspending."""

    budget: Budget
    iterations: int = 0
    spent: dict[str, int] = field(default_factory=dict)

    # Which tool draws from which budget.
    _LIMITS = {
        "research_web": ("max_web_queries", "web research queries"),
        "evaluate_menu": ("max_candidate_menus", "candidate evaluations"),
        "validate_and_publish_menu": ("max_validation_retries", "publish attempts"),
    }

    def charge_iteration(self) -> None:
        """Count one planner step; raise once the loop budget is gone.

        The refused step is NOT counted: ``iterations`` always equals the
        number of steps that actually ran.
        """
        if self.iterations + 1 > self.budget.max_iterations:
            raise BudgetExceeded(
                f"max_iterations={self.budget.max_iterations} exhausted"
            )
        self.iterations += 1

    def charge_tool(self, tool_name: str) -> None:
        """Count a tool call against its budget, if it has one."""
        if tool_name not in self._LIMITS:
            return
        attr, label = self._LIMITS[tool_name]
        limit = getattr(self.budget, attr)
        if attr == "max_validation_retries":
            limit += 1  # N retries = N+1 total attempts
        used = self.spent.get(tool_name, 0) + 1
        if used > limit:
            raise BudgetExceeded(f"budget for {label} ({limit}) exhausted")
        self.spent[tool_name] = used

    def remaining(self) -> dict[str, int]:
        """Snapshot of what is left, for the live trace display."""
        left = {"iterations": self.budget.max_iterations - self.iterations}
        for tool, (attr, _) in self._LIMITS.items():
            limit = getattr(self.budget, attr)
            if attr == "max_validation_retries":
                limit += 1
            left[tool] = limit - self.spent.get(tool, 0)
        return left
