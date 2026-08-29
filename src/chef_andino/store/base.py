"""The EventStore port: what any storage backend must provide."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from chef_andino.contracts.models import EventSnapshot, Menu, SurveyResponse
from chef_andino.lifecycle.states import EventState


@dataclass
class EventRecord:
    """The stored state of one event (not its responses - those are listed)."""

    event_id: str
    state: EventState
    latest_snapshot_version: int  # 0 = never frozen


class EventStore(Protocol):
    """Everything the application needs from storage, backend-agnostic.

    Local implementation: :class:`~chef_andino.store.local_json.LocalJsonStore`
    (one JSON file). Cloud implementation (later phase): DynamoDB tables with
    the same method signatures, called from Lambda.
    """

    def create_event(self, event_id: str) -> EventRecord:
        """Create an event in the OPEN state (idempotent)."""
        ...

    def get_event(self, event_id: str) -> EventRecord:
        """Return the event record; raise KeyError if it does not exist."""
        ...

    def set_state(self, event_id: str, state: EventState) -> None:
        """Persist a new lifecycle state (legality is checked by lifecycle)."""
        ...

    def add_response(self, response: SurveyResponse) -> None:
        """Append one survey response."""
        ...

    def list_responses(self, event_id: str) -> list[SurveyResponse]:
        """Return all responses for an event."""
        ...

    def save_snapshot(self, snapshot: EventSnapshot) -> None:
        """Persist a frozen aggregate (versions are immutable once written)."""
        ...

    def get_snapshot(self, event_id: str, version: int | None = None) -> EventSnapshot:
        """Return a snapshot by version (default: the latest one)."""
        ...

    def save_menu(self, menu: Menu) -> None:
        """Persist the published menu."""
        ...

    def get_menu(self, event_id: str) -> Menu | None:
        """Return the published menu, or None if not published yet."""
        ...
