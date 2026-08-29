"""Tool, ToolResult and ToolRegistry: callable-by-name capabilities.

The shape mirrors how tools look to a real model (Bedrock ``toolSpec`` /
MCP): a name, a description the model reads, a JSON-Schema for arguments,
and a function. Because the mock planner and a real LLM both drive tools
through this same registry, swapping the brain changes nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolResult:
    """What a tool call returns to the agent (and to the trace)."""

    ok: bool
    data: Any = None
    error: str | None = None

    def summary(self) -> str:
        """One line for the live trace display."""
        if not self.ok:
            return f"ERROR: {self.error}"
        if isinstance(self.data, list):
            return f"ok ({len(self.data)} items)"
        return "ok"


@dataclass(frozen=True)
class Tool:
    """One capability the agent may invoke by name."""

    name: str
    description: str  # read by the (real) LLM to decide when to call it
    args_schema: dict = field(default_factory=lambda: {"type": "object", "properties": {}})
    fn: Callable[..., ToolResult] = None  # type: ignore[assignment]


class ToolRegistry:
    """Name -> Tool lookup, plus the Bedrock toolSpec projection."""

    def __init__(self, tools: list[Tool]) -> None:
        """Index the tools by name (duplicate names are a bug)."""
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"duplicate tool name: {tool.name}")
            self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        """Return a tool; unknown names raise KeyError with the valid list."""
        try:
            return self._tools[name]
        except KeyError:
            raise KeyError(f"unknown tool '{name}' (available: {sorted(self._tools)})")

    def names(self) -> list[str]:
        """All registered tool names."""
        return sorted(self._tools)

    def as_bedrock_toolspecs(self) -> list[dict]:
        """Project the registry into Bedrock Converse-API ``toolSpec`` format.

        Used by the optional BedrockPlanner; shown here so students see that
        a 'tool' for a real LLM is literally name + description + schema.
        """
        return [
            {
                "toolSpec": {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": {"json": t.args_schema},
                }
            }
            for t in self._tools.values()
        ]
