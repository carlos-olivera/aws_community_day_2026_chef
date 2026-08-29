"""Shared fixtures: a temp-dir Settings and pre-seeded events.

Tests use the REAL corpus and inventory from data/ (they are part of the
system under test) but write all runtime state to a temp directory.
"""

from __future__ import annotations

import json

import pytest

from chef_andino.config import Settings
from chef_andino.contracts.models import SurveyResponse
from chef_andino.lifecycle.aggregate import build_snapshot
from chef_andino.lifecycle.states import EventState, transition
from chef_andino.store.local_json import LocalJsonStore

EVENT_ID = "test-event"


@pytest.fixture()
def settings(tmp_path) -> Settings:
    return Settings(local_dir=tmp_path / ".localdata")


@pytest.fixture()
def store(settings) -> LocalJsonStore:
    return LocalJsonStore(settings.db_path)


@pytest.fixture()
def responses(settings) -> list[SurveyResponse]:
    raw = json.loads(settings.responses_path.read_text())
    parsed = []
    for item in raw:
        item["event_id"] = EVENT_ID
        parsed.append(SurveyResponse.model_validate(item))
    return parsed


@pytest.fixture()
def seeded_event(store, responses) -> str:
    store.create_event(EVENT_ID)
    for r in responses:
        store.add_response(r)
    return EVENT_ID


@pytest.fixture()
def frozen_event(store, seeded_event, responses) -> str:
    transition(store, seeded_event, EventState.FROZEN)
    store.save_snapshot(build_snapshot(seeded_event, responses, version=1))
    return seeded_event


@pytest.fixture()
def snapshot(responses):
    return build_snapshot(EVENT_ID, responses, version=1)


@pytest.fixture()
def inventory(settings):
    from chef_andino.tools.inventory import LocalInventorySource

    return LocalInventorySource(settings.inventory_path).list()


@pytest.fixture()
def corpus_pools(settings):
    """Dish pools per course, exactly as the mock planner would fetch them."""
    from chef_andino.tools.knowledge import LocalCorpusSearch

    search = LocalCorpusSearch(settings.corpus_dir)
    pools = {}
    for course in ("breakfast", "starter", "main", "dessert"):
        hits = search.search("", filters={"type": "dish", "course": course})
        pools[course] = [
            h.metadata | {"doc_id": h.doc_id, "snippet": h.snippet} for h in hits
        ]
    return pools


@pytest.fixture()
def valid_menu_dict(snapshot, inventory, corpus_pools) -> dict:
    """A menu that passes every validator check, as a plain dict."""
    from chef_andino.planner.mock import assemble_menu

    return assemble_menu(
        snapshot.model_dump(mode="json"),
        [i.model_dump(mode="json") for i in inventory],
        corpus_pools,
    )
