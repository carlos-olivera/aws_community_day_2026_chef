"""LocalJsonStore: the whole database is one pretty-printed JSON file.

Open ``.localdata/db.json`` in your editor while running the demo and you can
literally watch the event walk through its lifecycle. That transparency is
the point - a real deployment would use DynamoDB behind the same protocol.
"""

from __future__ import annotations

import json
from pathlib import Path

from chef_andino.contracts.models import EventSnapshot, Menu, SurveyResponse
from chef_andino.lifecycle.states import EventState
from chef_andino.store.base import EventRecord


class LocalJsonStore:
    """A file-backed EventStore. Reads and rewrites the file on every call.

    Deliberately naive: no locking, no caching. Fine for one student on one
    laptop; the docstring of :mod:`chef_andino.store` explains what replaces
    it in the cloud.
    """

    def __init__(self, db_path: Path) -> None:
        """Bind the store to a JSON file path (created lazily)."""
        self._path = db_path

    # -- low-level file helpers ------------------------------------------------

    def _load(self) -> dict:
        if not self._path.exists():
            return {"events": {}}
        return json.loads(self._path.read_text())

    def _save(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2, default=str) + "\n")

    def _event(self, data: dict, event_id: str) -> dict:
        try:
            return data["events"][event_id]
        except KeyError:
            raise KeyError(f"event '{event_id}' does not exist - run `chef seed` first")

    # -- EventStore protocol ---------------------------------------------------

    def create_event(self, event_id: str) -> EventRecord:
        """Create an event in the OPEN state (idempotent)."""
        data = self._load()
        if event_id not in data["events"]:
            data["events"][event_id] = {
                "event_id": event_id,
                "state": EventState.OPEN.value,
                "responses": [],
                "snapshots": {},
                "menu": None,
            }
            self._save(data)
        return self.get_event(event_id)

    def get_event(self, event_id: str) -> EventRecord:
        """Return the event record; raise KeyError if it does not exist."""
        ev = self._event(self._load(), event_id)
        versions = [int(v) for v in ev["snapshots"]]
        return EventRecord(
            event_id=event_id,
            state=EventState(ev["state"]),
            latest_snapshot_version=max(versions) if versions else 0,
        )

    def set_state(self, event_id: str, state: EventState) -> None:
        """Persist a new lifecycle state."""
        data = self._load()
        self._event(data, event_id)["state"] = state.value
        self._save(data)

    def add_response(self, response: SurveyResponse) -> None:
        """Append one survey response."""
        data = self._load()
        ev = self._event(data, response.event_id)
        ev["responses"].append(response.model_dump(mode="json"))
        self._save(data)

    def list_responses(self, event_id: str) -> list[SurveyResponse]:
        """Return all responses for an event."""
        ev = self._event(self._load(), event_id)
        return [SurveyResponse.model_validate(r) for r in ev["responses"]]

    def save_snapshot(self, snapshot: EventSnapshot) -> None:
        """Persist a frozen aggregate. Overwriting a version is forbidden."""
        data = self._load()
        ev = self._event(data, snapshot.event_id)
        key = str(snapshot.snapshot_version)
        if key in ev["snapshots"]:
            raise ValueError(
                f"snapshot v{key} already exists - snapshots are immutable "
                "(re-freezing must bump the version)"
            )
        ev["snapshots"][key] = snapshot.model_dump(mode="json")
        self._save(data)

    def get_snapshot(self, event_id: str, version: int | None = None) -> EventSnapshot:
        """Return a snapshot by version (default: the latest one)."""
        ev = self._event(self._load(), event_id)
        if not ev["snapshots"]:
            raise KeyError(f"event '{event_id}' has no snapshot - freeze it first")
        if version is None:
            version = max(int(v) for v in ev["snapshots"])
        try:
            raw = ev["snapshots"][str(version)]
        except KeyError:
            raise KeyError(f"event '{event_id}' has no snapshot v{version}")
        return EventSnapshot.model_validate(raw)

    def save_menu(self, menu: Menu) -> None:
        """Persist the published menu."""
        data = self._load()
        self._event(data, menu.event_id)["menu"] = menu.model_dump(mode="json")
        self._save(data)

    def get_menu(self, event_id: str) -> Menu | None:
        """Return the published menu, or None if not published yet."""
        raw = self._event(self._load(), event_id)["menu"]
        return Menu.model_validate(raw) if raw else None
