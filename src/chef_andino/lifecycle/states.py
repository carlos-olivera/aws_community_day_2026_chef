"""The event state machine: OPEN -> FROZEN -> GENERATING -> PUBLISHED.

A failed agent run returns the event from GENERATING to FROZEN so it can be
retried. PUBLISHED is terminal. Every other transition is illegal and raises.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # imported for annotations only - avoids a circular import
    from chef_andino.store.base import EventStore


class EventState(str, Enum):
    """Where an event is in its life."""

    OPEN = "OPEN"              # survey is accepting responses
    FROZEN = "FROZEN"          # survey closed, snapshot taken
    GENERATING = "GENERATING"  # the agent is running
    PUBLISHED = "PUBLISHED"    # a validated menu exists (terminal)


ALLOWED_TRANSITIONS: dict[EventState, set[EventState]] = {
    EventState.OPEN: {EventState.FROZEN},
    EventState.FROZEN: {EventState.GENERATING},
    EventState.GENERATING: {EventState.PUBLISHED, EventState.FROZEN},
    EventState.PUBLISHED: set(),
}


class IllegalTransition(Exception):
    """Raised when code tries to move an event along a forbidden edge."""


def transition(store: EventStore, event_id: str, to: EventState) -> None:
    """Move an event to a new state, enforcing the transition table."""
    current = store.get_event(event_id).state
    if to not in ALLOWED_TRANSITIONS[current]:
        raise IllegalTransition(
            f"event '{event_id}': {current.value} -> {to.value} is not allowed "
            f"(allowed: {sorted(s.value for s in ALLOWED_TRANSITIONS[current]) or 'none'})"
        )
    store.set_state(event_id, to)
