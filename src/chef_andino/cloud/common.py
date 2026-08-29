"""Shared configuration and small helpers for cloud Lambda handlers."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

from chef_andino.store.dynamodb import DynamoCloudStore


@lru_cache(maxsize=1)
def store() -> DynamoCloudStore:
    """Build the DynamoDB adapter once per warm Lambda environment."""
    return DynamoCloudStore(
        os.environ["EVENTS_TABLE"],
        os.environ["RESPONSES_TABLE"],
        os.environ["INVENTORY_TABLE"],
    )


def json_body(event: dict[str, Any]) -> dict[str, Any]:
    """Decode an HTTP API request body."""
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        import base64

        raw = base64.b64decode(raw).decode()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("el cuerpo debe ser un objeto JSON")
    return value


def response(status: int, payload: Any) -> dict[str, Any]:
    """Return a no-cache JSON response understood by API Gateway v2."""
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json; charset=utf-8",
            "cache-control": "no-store",
        },
        "body": json.dumps(payload, ensure_ascii=False, default=str),
    }
