"""HTTP API Lambda for the public experience and presenter controls."""

from __future__ import annotations

import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from chef_andino.cloud.common import json_body, response, store
from chef_andino.contracts.models import (
    Allergen,
    CuisinePreference,
    Diet,
    PreferredIngredient,
    SpiceLevel,
    SurveyResponse,
)
from chef_andino.lifecycle.states import EventState
from chef_andino.store.dynamodb import CloudConflict, _ddb

PROTECTED_ACTIONS = {"reset", "freeze", "generate", "run", "fallback"}


class SurveySubmission(BaseModel):
    """Strict anonymous survey payload accepted from browsers."""

    model_config = ConfigDict(extra="forbid")

    diet: Diet
    lactose_intolerant: bool
    gluten_free: bool
    allergies: list[Allergen] = Field(default_factory=list)
    spice_level: SpiceLevel
    cuisine_preference: CuisinePreference
    preferred_ingredients: list[PreferredIngredient] = Field(default_factory=list, max_length=3)
    consent: bool


@lru_cache(maxsize=1)
def _presenter_passphrase() -> str:
    """Read the presenter secret once; never log it or return it to clients."""
    import boto3

    value = boto3.client("secretsmanager").get_secret_value(
        SecretId=os.environ["PRESENTER_SECRET_ARN"]
    )["SecretString"]
    try:
        decoded = json.loads(value)
        return str(decoded["passphrase"])
    except (json.JSONDecodeError, KeyError, TypeError):
        return value


def _authorized(event: dict[str, Any]) -> bool:
    headers = {key.lower(): value for key, value in (event.get("headers") or {}).items()}
    provided = headers.get("authorization", "")
    if not provided.startswith("Bearer "):
        return False
    return hmac.compare_digest(provided[7:], _presenter_passphrase())


def _event_id(event: dict[str, Any]) -> str:
    event_id = (event.get("pathParameters") or {}).get("event_id", "")
    if event_id != os.environ.get("PUBLIC_EVENT_ID", "demo-event"):
        raise KeyError(event_id)
    return event_id


def _seed_synthetic(event_id: str) -> int:
    raw = json.loads(Path(os.environ["SYNTHETIC_RESPONSES_PATH"]).read_text())
    accepted = 0
    for item in raw:
        response_id = str(item.get("response_id") or uuid.uuid4())
        parsed = SurveyResponse.model_validate(
            item
            | {
                "event_id": event_id,
                "response_id": response_id,
                "submitted_at": item.get("submitted_at") or datetime.now(timezone.utc),
                "consent": True,
            }
        )
        accepted += int(store().submit_response(parsed, f"synthetic:{response_id}"))
    return accepted


def _reveal_fallback(event_id: str) -> dict[str, Any]:
    import boto3

    cloud_store = store()
    current = cloud_store.ensure_event(event_id)
    obj = boto3.client("s3").get_object(
        Bucket=os.environ["FALLBACK_BUCKET"], Key="fallback/last-good.json"
    )
    artifact = json.loads(obj["Body"].read())
    fallback_run = f"fallback-{uuid.uuid4().hex[:12]}"
    menu = artifact["menu"] | {
        "event_id": event_id,
        "cycle": current["cycle"],
        "snapshot_version": current["cycle"],
        "run_id": fallback_run,
        "generation_mode": "fallback_last_good",
    }
    run = {
        "run_id": fallback_run,
        "cycle": current["cycle"],
        "status": "COMPLETED",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "steps": [
            {
                "type": "fallback",
                "message": "Se reveló el último resultado válido, no una ejecución en vivo.",
            }
        ],
    }
    cloud_store.events.update_item(
        Key={"event_id": event_id},
        UpdateExpression=(
            "SET #state = :published, menu = :menu, #run = :run, updated_at = :updated"
        ),
        ExpressionAttributeNames={"#state": "state", "#run": "run"},
        ExpressionAttributeValues={
            ":published": EventState.PUBLISHED.value,
            ":menu": _ddb(menu),
            ":run": _ddb(run),
            ":updated": datetime.now(timezone.utc).isoformat(),
        },
    )
    return {"published": True, "run_id": fallback_run, "generation_mode": "fallback_last_good"}


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Dispatch API Gateway HTTP API routes."""
    route = event.get("routeKey", "")
    try:
        event_id = _event_id(event)
        protected_tokens = ("/reset", "/freeze", "/generate", "/runs/", "/fallback/")
        if any(token in route for token in protected_tokens):
            if not _authorized(event):
                return response(401, {"detail": "clave de presentador inválida"})

        if route == "GET /api/events/{event_id}":
            stats = store().stats(event_id)
            return response(
                200,
                {
                    "event_id": stats["event_id"],
                    "cycle": stats["cycle"],
                    "state": stats["state"],
                    "menu_available": stats["menu_available"],
                    "run": stats.get("run"),
                },
            )
        if route == "GET /api/events/{event_id}/stats":
            return response(200, store().stats(event_id))
        if route == "POST /api/events/{event_id}/responses":
            submission = SurveySubmission.model_validate(json_body(event))
            if not submission.consent:
                return response(422, {"detail": "debes aceptar el consentimiento"})
            headers = {key.lower(): value for key, value in (event.get("headers") or {}).items()}
            idempotency_key = headers.get("idempotency-key") or str(uuid.uuid4())
            survey_response = SurveyResponse(
                response_id="server-assigned",
                event_id=event_id,
                submitted_at=datetime.now(timezone.utc),
                consent=True,
                **submission.model_dump(exclude={"consent"}),
            )
            accepted = store().submit_response(survey_response, idempotency_key)
            return response(201, {"accepted": True, "duplicate": not accepted})
        if route == "GET /api/events/{event_id}/menu":
            menu = store().get_event(event_id).get("menu")
            if not menu:
                return response(404, {"detail": "todavía no existe un menú publicado"})
            return response(200, menu)
        if route == "POST /api/events/{event_id}/reset":
            body = json_body(event)
            fresh = store().reset(event_id)
            seeded = _seed_synthetic(event_id) if bool(body.get("seedSynthetic")) else 0
            return response(200, {"state": "OPEN", "cycle": fresh["cycle"], "seeded": seeded})
        if route == "POST /api/events/{event_id}/freeze":
            snapshot = store().freeze(event_id)
            return response(
                200,
                {
                    "state": "FROZEN",
                    "snapshot_version": snapshot.snapshot_version,
                    "total_responses": snapshot.total_responses,
                },
            )
        if route == "POST /api/events/{event_id}/generate":
            import boto3

            run_id = f"chef-{uuid.uuid4()}"
            run = store().start_run(event_id, run_id)
            try:
                boto3.client("lambda").invoke(
                    FunctionName=os.environ["WORKER_FUNCTION_NAME"],
                    InvocationType="Event",
                    Payload=json.dumps(
                        {"event_id": event_id, "cycle": run["cycle"], "run_id": run_id}
                    ).encode(),
                )
            except Exception as exc:
                store().fail_run(event_id, run_id, f"no se pudo iniciar el worker: {exc}")
                raise
            return response(202, {"run_id": run_id, "state": "GENERATING"})
        if route == "GET /api/events/{event_id}/runs/{run_id}":
            run_id = (event.get("pathParameters") or {})["run_id"]
            return response(200, store().get_run(event_id, run_id))
        if route == "POST /api/events/{event_id}/fallback/reveal":
            return response(200, _reveal_fallback(event_id))
        return response(404, {"detail": f"ruta desconocida: {route}"})
    except KeyError:
        return response(404, {"detail": "evento o ejecución desconocida"})
    except CloudConflict as exc:
        return response(409, {"detail": str(exc)})
    except (ValueError, TypeError) as exc:
        return response(422, {"detail": str(exc)})
    except Exception as exc:
        print(json.dumps({"level": "ERROR", "route": route, "error": type(exc).__name__}))
        return response(500, {"detail": "error interno de la demostración"})
