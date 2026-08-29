"""Lambda target containing Chef Andino's deterministic Gateway tools."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from chef_andino.cloud.common import store
from chef_andino.contracts.models import Menu
from chef_andino.lifecycle.states import EventState
from chef_andino.store.dynamodb import CloudConflict, _ddb
from chef_andino.tools.evaluate import compute_coverage, evaluate_menu
from chef_andino.validation.validator import validate_menu


def _tool_name(event: dict[str, Any], context: Any) -> str:
    explicit = event.pop("_tool_name", None)
    if explicit:
        return str(explicit).split("___")[-1]
    client_context = getattr(context, "client_context", None)
    custom = getattr(client_context, "custom", None) or {}
    full = custom.get("bedrockAgentCoreToolName", "")
    if not full:
        raise ValueError("AgentCore no proporcionó el nombre de la herramienta")
    return full.split("___")[-1]


def _assert_active(event_id: str, cycle: int) -> dict[str, Any]:
    item = store().get_event(event_id)
    if int(item["cycle"]) != cycle:
        raise CloudConflict("el ciclo solicitado ya no está activo")
    if item["state"] != EventState.GENERATING.value:
        raise CloudConflict("las herramientas solo operan durante GENERATING")
    return item


def _menu_hash(menu: Menu) -> str:
    canonical = json.dumps(menu.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _validate_identity(menu: Menu, event_id: str, cycle: int) -> None:
    if menu.event_id != event_id:
        raise ValueError("el menu.event_id no coincide con la misión")
    if menu.snapshot_version != cycle:
        raise ValueError("el menú no cita el snapshot del ciclo activo")


def _get_snapshot(event: dict[str, Any]) -> dict[str, Any]:
    event_id = str(event["event_id"])
    cycle = int(event["cycle"])
    _assert_active(event_id, cycle)
    return store().get_snapshot(event_id).model_dump(mode="json")


def _get_inventory(event: dict[str, Any]) -> dict[str, Any]:
    _assert_active(str(event["event_id"]), int(event["cycle"]))
    return {
        "items": [item.model_dump(mode="json") for item in store().list_inventory()]
    }


def _retrieve(event: dict[str, Any]) -> dict[str, Any]:
    event_id = str(event["event_id"])
    cycle = int(event["cycle"])
    _assert_active(event_id, cycle)
    query = str(event["query"]).strip()
    if not query:
        raise ValueError("la consulta RAG no puede estar vacía")
    number = max(1, min(int(event.get("number_of_results", 5)), 8))
    import boto3

    result = boto3.client("bedrock-agent-runtime").retrieve(
        knowledgeBaseId=os.environ["KNOWLEDGE_BASE_ID"],
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": number}
        },
    )
    return {"retrievalResults": result.get("retrievalResults", [])}


def _evaluate(event: dict[str, Any]) -> dict[str, Any]:
    event_id = str(event["event_id"])
    cycle = int(event["cycle"])
    _assert_active(event_id, cycle)
    menu = Menu.model_validate(event["menu"])
    _validate_identity(menu, event_id, cycle)
    result = evaluate_menu(menu, store().get_snapshot(event_id), store().list_inventory())
    return result.model_dump(mode="json")


def _validate(event: dict[str, Any]) -> dict[str, Any]:
    event_id = str(event["event_id"])
    cycle = int(event["cycle"])
    candidate_id = str(event["candidate_id"])
    if not candidate_id or len(candidate_id) > 64:
        raise ValueError("candidate_id inválido")
    item = _assert_active(event_id, cycle)
    menu = Menu.model_validate(event["menu"])
    _validate_identity(menu, event_id, cycle)
    snapshot = store().get_snapshot(event_id)
    inventory = store().list_inventory()
    evaluation = evaluate_menu(menu, snapshot, inventory)
    report = validate_menu(menu, snapshot, inventory)
    enriched = menu.model_copy(
        update={
            "menu_id": candidate_id,
            "cycle": cycle,
            "run_id": item["run"]["run_id"],
            "generation_mode": "live_agentcore",
            "coverage": compute_coverage(menu, snapshot, inventory),
            "evaluation": evaluation,
            "validation": report,
        }
    )
    menu_hash = _menu_hash(enriched)
    result = {
        "candidate_id": candidate_id,
        "passed": report.passed,
        "menu_hash": menu_hash,
        "failed_checks": [
            check.model_dump(mode="json") for check in report.checks if not check.passed
        ],
        "evaluation": evaluation.model_dump(mode="json"),
    }
    store().append_run_step(
        event_id,
        item["run"]["run_id"],
        {
            "type": "validation",
            "candidate_id": candidate_id,
            "status": "PASSED" if report.passed else "FAILED",
            "failed_checks": [check.id for check in report.checks if not check.passed],
        },
    )
    if report.passed:
        candidate = {
            "candidate_id": candidate_id,
            "menu_hash": menu_hash,
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "menu": enriched.model_dump(mode="json"),
        }
        store().events.update_item(
            Key={"event_id": event_id},
            UpdateExpression="SET validated_candidate = :candidate, updated_at = :updated",
            ConditionExpression="#state = :generating AND #cycle = :cycle",
            ExpressionAttributeNames={"#state": "state", "#cycle": "cycle"},
            ExpressionAttributeValues={
                ":candidate": _ddb(candidate),
                ":updated": datetime.now(timezone.utc).isoformat(),
                ":generating": EventState.GENERATING.value,
                ":cycle": cycle,
            },
        )
    return result


def _publish(event: dict[str, Any]) -> dict[str, Any]:
    event_id = str(event["event_id"])
    cycle = int(event["cycle"])
    candidate_id = str(event["candidate_id"])
    item = _assert_active(event_id, cycle)
    candidate = item.get("validated_candidate")
    if not candidate or candidate.get("candidate_id") != candidate_id:
        raise CloudConflict("ese candidato no tiene una validación aprobada")
    menu = Menu.model_validate(candidate["menu"])
    snapshot = store().get_snapshot(event_id)
    inventory = store().list_inventory()
    report = validate_menu(menu, snapshot, inventory)
    if not report.passed or _menu_hash(menu) != candidate["menu_hash"]:
        raise CloudConflict("la revalidación del candidato falló")
    run_id = item["run"]["run_id"]
    published = menu.model_copy(
        update={
            "menu_id": f"menu-{uuid.uuid4().hex[:12]}",
            "cycle": cycle,
            "run_id": run_id,
            "generation_mode": "live_agentcore",
            "validation": report,
        }
    )
    try:
        store().events.update_item(
            Key={"event_id": event_id},
            UpdateExpression=(
                "SET #state = :published, menu = :menu, #run.#status = :complete, "
                "#run.#finished = :finished, updated_at = :finished"
            ),
            ConditionExpression=(
                "#state = :generating AND #cycle = :cycle AND "
                "validated_candidate.candidate_id = :candidate_id"
            ),
            ExpressionAttributeNames={
                "#state": "state",
                "#run": "run",
                "#status": "status",
                "#finished": "finished_at",
                "#cycle": "cycle",
            },
            ExpressionAttributeValues={
                ":published": EventState.PUBLISHED.value,
                ":generating": EventState.GENERATING.value,
                ":cycle": cycle,
                ":candidate_id": candidate_id,
                ":menu": _ddb(published.model_dump(mode="json")),
                ":complete": "COMPLETED",
                ":finished": datetime.now(timezone.utc).isoformat(),
            },
        )
    except store().client.exceptions.ConditionalCheckFailedException as exc:
        raise CloudConflict("el estado cambió antes de publicar") from exc

    import boto3

    boto3.client("s3").put_object(
        Bucket=os.environ["FALLBACK_BUCKET"],
        Key="fallback/last-good.json",
        Body=json.dumps(
            {
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "snapshot": snapshot.model_dump(mode="json"),
                "menu": published.model_dump(mode="json"),
                "run": item["run"],
            },
            ensure_ascii=False,
            default=str,
        ).encode(),
        ContentType="application/json",
        ServerSideEncryption="AES256",
    )
    return {"published": True, "menu_id": published.menu_id, "candidate_id": candidate_id}


HANDLERS = {
    "get_event_snapshot": _get_snapshot,
    "get_available_ingredients": _get_inventory,
    "Retrieve": _retrieve,
    "evaluate_menu": _evaluate,
    "validate_menu": _validate,
    "publish_menu": _publish,
}


def lambda_handler(event: dict[str, Any], context: Any) -> Any:
    """Dispatch the AgentCore tool name supplied through Lambda client context."""
    name = _tool_name(event, context)
    if name not in HANDLERS:
        raise ValueError(f"herramienta desconocida: {name}")
    result = HANDLERS[name](event)
    print(json.dumps({"tool": name, "ok": True}, ensure_ascii=False))
    return result
