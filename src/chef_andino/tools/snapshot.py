"""Tool 1/6: ``get_event_snapshot`` - the agent's only view of the audience.

Local adapter reads the frozen snapshot from the JSON store; the cloud
adapter reads the same shape from DynamoDB. The agent NEVER sees individual
survey responses - only this aggregate.
"""

from __future__ import annotations

from typing import Protocol

from chef_andino.contracts.models import EventSnapshot
from chef_andino.store.base import EventStore
from chef_andino.tools.base import Tool, ToolResult


class SnapshotSource(Protocol):
    """Port: anything that can hand over the frozen aggregate."""

    def get(self, event_id: str) -> EventSnapshot:
        """Return the latest frozen snapshot for the event."""
        ...


class LocalSnapshotSource:
    """Adapter: read the snapshot from the local store."""

    def __init__(self, store: EventStore) -> None:
        """Bind to a store."""
        self._store = store

    def get(self, event_id: str) -> EventSnapshot:
        """Return the latest frozen snapshot for the event."""
        return self._store.get_snapshot(event_id)


def make_snapshot_tool(source: SnapshotSource, event_id: str) -> Tool:
    """Wrap the port as a named tool bound to one event (one mission)."""

    def fn() -> ToolResult:
        try:
            return ToolResult(ok=True, data=source.get(event_id).model_dump(mode="json"))
        except KeyError as exc:
            return ToolResult(ok=False, error=str(exc))

    return Tool(
        name="get_event_snapshot",
        description=(
            "Get the aggregated, anonymous dietary preferences of the event "
            "audience: counts, percentages and hard constraints derived from "
            "the survey. Call this first - it defines the problem."
        ),
        fn=fn,
    )
