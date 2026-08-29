"""Event lifecycle: an explicit state machine plus a pure aggregation function.

Teaching concept: *the snapshot pattern*. The survey may keep receiving
responses, but the agent never reads a moving target - the presenter freezes
the event, aggregation produces an immutable versioned snapshot, and the
whole agent run works from that one version.
"""

from chef_andino.lifecycle.aggregate import build_snapshot
from chef_andino.lifecycle.states import EventState, IllegalTransition, transition

__all__ = ["EventState", "IllegalTransition", "build_snapshot", "transition"]
