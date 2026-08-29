"""Asynchronous worker that invokes the managed AgentCore Harness."""

from __future__ import annotations

import json
import os
from typing import Any

from chef_andino.cloud.common import store
from chef_andino.lifecycle.states import EventState


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Run one mission and project observable Harness events into DynamoDB."""
    import boto3

    event_id = event["event_id"]
    cycle = int(event["cycle"])
    run_id = event["run_id"]
    cloud_store = store()
    cloud_store.mark_run_running(event_id, run_id)
    try:
        client = boto3.client("bedrock-agentcore")
        proxy_token = boto3.client("secretsmanager").get_secret_value(
            SecretId=os.environ["MCP_PROXY_SECRET_ARN"]
        )["SecretString"]
        result = client.invoke_harness(
            harnessArn=os.environ["HARNESS_ARN"],
            runtimeSessionId=run_id,
            tools=[
                {
                    "type": "remote_mcp",
                    "name": "chef_tools",
                    "config": {
                        "remoteMcp": {
                            "url": os.environ["MCP_PROXY_URL"],
                            "headers": {
                                "x-chef-proxy-token": proxy_token,
                                "x-chef-policy-session-id": run_id,
                            },
                        }
                    },
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "text": (
                                "Diseña y publica el menú para "
                                f"event_id={event_id}, cycle={cycle}. Sigue la misión "
                                "completa y no termines hasta publicar o agotar el límite."
                            )
                        }
                    ],
                }
            ],
        )
        for message in result["stream"]:
            if "contentBlockStart" in message:
                block = message["contentBlockStart"]
                start = block.get("start", {})
                if "toolUse" in start:
                    name = start["toolUse"].get("name", "herramienta")
                    cloud_store.append_run_step(
                        event_id,
                        run_id,
                        {"type": "tool_call", "tool": name, "status": "RUNNING"},
                    )
                elif "toolResult" in start:
                    status = start["toolResult"].get("status", "UNKNOWN")
                    cloud_store.append_run_step(
                        event_id,
                        run_id,
                        {"type": "tool_result", "status": status},
                    )
            elif "messageStop" in message:
                cloud_store.append_run_step(
                    event_id,
                    run_id,
                    {
                        "type": "model_stop",
                        "reason": message["messageStop"].get("stopReason", "unknown"),
                    },
                )
            elif any(
                key in message
                for key in ("internalServerException", "validationException", "runtimeClientError")
            ):
                key = next(
                    key
                    for key in message
                    if key.endswith("Exception") or key == "runtimeClientError"
                )
                raise RuntimeError(message[key].get("message", key))

        final = cloud_store.get_event(event_id)
        if int(final["cycle"]) != cycle:
            return {"published": False, "cancelled_by_reset": True, "run_id": run_id}
        if final["state"] != EventState.PUBLISHED.value:
            raise RuntimeError("Harness terminó sin publicar un menú")
        return {"published": True, "run_id": run_id}
    except Exception as exc:
        print(json.dumps({"level": "ERROR", "run_id": run_id, "error": str(exc)}))
        current = cloud_store.get_event(event_id)
        if (
            int(current["cycle"]) == cycle
            and current["state"] != EventState.PUBLISHED.value
            and (current.get("run") or {}).get("run_id") == run_id
        ):
            cloud_store.fail_run(event_id, run_id, str(exc))
        raise
