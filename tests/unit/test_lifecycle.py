"""The state machine: legal path, illegal edges, snapshot immutability."""

import pytest

from chef_andino.lifecycle.aggregate import build_snapshot
from chef_andino.lifecycle.states import EventState, IllegalTransition, transition


def test_happy_path(store, seeded_event):
    transition(store, seeded_event, EventState.FROZEN)
    transition(store, seeded_event, EventState.GENERATING)
    transition(store, seeded_event, EventState.PUBLISHED)
    assert store.get_event(seeded_event).state is EventState.PUBLISHED


def test_failed_run_returns_to_frozen(store, seeded_event):
    transition(store, seeded_event, EventState.FROZEN)
    transition(store, seeded_event, EventState.GENERATING)
    transition(store, seeded_event, EventState.FROZEN)
    assert store.get_event(seeded_event).state is EventState.FROZEN


@pytest.mark.parametrize(
    "target", [EventState.GENERATING, EventState.PUBLISHED, EventState.OPEN]
)
def test_illegal_from_open(store, seeded_event, target):
    with pytest.raises(IllegalTransition):
        transition(store, seeded_event, target)


def test_published_is_terminal(store, seeded_event):
    for state in (EventState.FROZEN, EventState.GENERATING, EventState.PUBLISHED):
        transition(store, seeded_event, state)
    for target in EventState:
        with pytest.raises(IllegalTransition):
            transition(store, seeded_event, target)


def test_snapshot_versions_are_immutable(store, seeded_event, responses):
    store.save_snapshot(build_snapshot(seeded_event, responses, version=1))
    with pytest.raises(ValueError, match="immutable"):
        store.save_snapshot(build_snapshot(seeded_event, responses, version=1))
    # A new version is fine, and becomes the latest.
    store.save_snapshot(build_snapshot(seeded_event, responses, version=2))
    assert store.get_snapshot(seeded_event).snapshot_version == 2
    assert store.get_event(seeded_event).latest_snapshot_version == 2
