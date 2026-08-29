"""FastAPI backend for the survey / dashboard / menu web UI.

Endpoints (all under ``/api``):

* ``POST /events/{event_id}/responses`` - submit one survey answer (only
  while the event is OPEN). The server assigns id and timestamp; the client
  cannot forge them.
* ``GET  /events/{event_id}/stats``     - live aggregate counters. The
  dashboard polls this every ~2 s; the cloud phase replaces polling with
  AWS AppSync Events (WebSockets).
* ``POST /events/{event_id}/freeze``    - close the survey, write snapshot.
* ``POST /events/{event_id}/generate``  - run Chef Andino (mock planner).
* ``GET  /events/{event_id}/menu``      - the published menu, or 404.

No authentication, on purpose: locally there is nothing to protect, and the
cloud phase puts Cognito in front of the presenter actions only (attendees
never log in - a login wall would kill the QR experience).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from chef_andino.config import Settings
from chef_andino.contracts.models import (
    Allergen,
    CuisinePreference,
    Diet,
    PreferredIngredient,
    SpiceLevel,
    SurveyResponse,
)
from chef_andino.lifecycle.aggregate import build_snapshot
from chef_andino.lifecycle.states import EventState, IllegalTransition, transition
from chef_andino.store.local_json import LocalJsonStore

app = FastAPI(title="Chef Andino - local API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = Settings()


def _store() -> LocalJsonStore:
    return LocalJsonStore(settings.db_path)


class SurveySubmission(BaseModel):
    """What the browser sends: the answers only. Ids are assigned server-side."""

    model_config = ConfigDict(extra="forbid")

    diet: Diet
    lactose_intolerant: bool
    gluten_free: bool
    allergies: list[Allergen] = []
    spice_level: SpiceLevel
    cuisine_preference: CuisinePreference
    preferred_ingredients: list[PreferredIngredient] = []
    consent: bool


@app.post("/api/events/{event_id}/responses", status_code=201)
def submit_response(event_id: str, submission: SurveySubmission) -> dict:
    """Accept one survey answer while the event is OPEN."""
    if not submission.consent:
        raise HTTPException(status_code=422, detail="consent is required")
    store = _store()
    store.create_event(event_id)
    if store.get_event(event_id).state is not EventState.OPEN:
        raise HTTPException(status_code=409, detail="the survey is closed")
    response = SurveyResponse(
        response_id=str(uuid.uuid4()),
        event_id=event_id,
        submitted_at=datetime.now(timezone.utc),
        consent=True,
        **submission.model_dump(exclude={"consent"}),
    )
    store.add_response(response)
    return {"accepted": True}


@app.get("/api/events/{event_id}/stats")
def stats(event_id: str) -> dict:
    """Aggregate counters for the dashboard (poll me)."""
    store = _store()
    try:
        record = store.get_event(event_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown event")
    responses = store.list_responses(event_id)
    payload: dict = {
        "event_id": event_id,
        "state": record.state.value,
        "total_responses": len(responses),
    }
    if responses:
        snap = build_snapshot(event_id, responses, version=1)  # preview only
        payload |= {
            "diet_counts": snap.diet_counts,
            "lactose_intolerant_count": snap.lactose_intolerant_count,
            "gluten_free_count": snap.gluten_free_count,
            "allergen_counts": snap.allergen_counts,
            "spice_counts": snap.spice_counts,
            "derived_constraints": snap.derived_constraints.model_dump(),
            "top_preferred_ingredients": [
                c.model_dump() for c in snap.top_preferred_ingredients
            ],
        }
    return payload


@app.post("/api/events/{event_id}/freeze")
def freeze(event_id: str) -> dict:
    """Presenter action: close the survey and take the immutable snapshot."""
    store = _store()
    responses = store.list_responses(event_id)
    if not responses:
        raise HTTPException(status_code=409, detail="no responses to freeze")
    version = store.get_event(event_id).latest_snapshot_version + 1
    try:
        transition(store, event_id, EventState.FROZEN)
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    store.save_snapshot(build_snapshot(event_id, responses, version))
    return {"state": "FROZEN", "snapshot_version": version}


@app.post("/api/events/{event_id}/generate")
def generate(event_id: str) -> dict:
    """Presenter action: run Chef Andino (mock planner, flaw injection on)."""
    from chef_andino.agent.runner import AgentRunner
    from chef_andino.agent.trace import TraceWriter
    from chef_andino.planner.mock import MockPlanner
    from chef_andino.tools.factory import build_local_toolset

    store = _store()
    if store.get_event(event_id).state is not EventState.FROZEN:
        raise HTTPException(status_code=409, detail="freeze the event first")
    trace = TraceWriter(settings.runs_dir)
    tools = build_local_toolset(store, settings, event_id, audit=trace.audit_sink)
    runner = AgentRunner(MockPlanner(), tools, store, settings.budget, trace)
    result = runner.run(event_id)
    return {
        "run_id": result.run_id,
        "published": result.published,
        "steps": result.steps,
        "finish_reason": result.finish_reason,
    }


@app.get("/api/events/{event_id}/menu")
def menu(event_id: str) -> dict:
    """The published menu - the payload the big screen renders."""
    store = _store()
    try:
        published = store.get_menu(event_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown event")
    if published is None:
        raise HTTPException(status_code=404, detail="no menu published yet")
    return published.model_dump(mode="json")
