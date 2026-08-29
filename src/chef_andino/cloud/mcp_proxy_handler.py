"""Authenticated MCP bridge from Harness to the IAM-protected AgentCore Gateway.

Harness' native ``agentcore_gateway`` tool does not currently expose custom
request headers. Temporal Policy requires a caller-managed policy session ID,
so the worker invokes Harness with this small remote-MCP bridge. The bridge
validates a private token, adds the run ID as the policy session, and SigV4
signs the request with its Lambda execution role.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from typing import Any

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.httpsession import URLLib3Session

_secret: str | None = None


def _proxy_secret() -> str:
    global _secret
    if _secret is None:
        result = boto3.client("secretsmanager").get_secret_value(
            SecretId=os.environ["MCP_PROXY_SECRET_ARN"]
        )
        _secret = result["SecretString"]
    return _secret


def _headers(event: dict[str, Any]) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in event.get("headers", {}).items()}


def _response(status: int, body: str, content_type: str = "application/json") -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "content-type": content_type,
            "cache-control": "no-store",
        },
        "body": body,
    }


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Forward one MCP request after authenticating and applying SigV4."""
    headers = _headers(event)
    supplied = headers.get("x-chef-proxy-token", "")
    if not supplied or not hmac.compare_digest(supplied, _proxy_secret()):
        return _response(401, json.dumps({"error": "unauthorized"}))

    policy_session = headers.get("x-chef-policy-session-id", "")
    if not policy_session or len(policy_session) > 128:
        return _response(400, json.dumps({"error": "missing policy session"}))

    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body_bytes = base64.b64decode(body)
    else:
        body_bytes = body.encode()

    target_headers = {
        "accept": headers.get("accept", "application/json, text/event-stream"),
        "content-type": headers.get("content-type", "application/json"),
        "mcp-protocol-version": headers.get("mcp-protocol-version", "2025-06-18"),
        "x-amzn-bedrock-agentcore-policy-session-id": policy_session,
    }
    if headers.get("mcp-session-id"):
        target_headers["mcp-session-id"] = headers["mcp-session-id"]

    session = boto3.Session()
    credentials = session.get_credentials()
    if credentials is None:
        return _response(500, json.dumps({"error": "AWS credentials unavailable"}))
    request = AWSRequest(
        method="POST",
        url=os.environ["GATEWAY_URL"],
        data=body_bytes,
        headers=target_headers,
    )
    SigV4Auth(
        credentials.get_frozen_credentials(),
        "bedrock-agentcore",
        os.environ.get("AWS_REGION", "us-east-1"),
    ).add_auth(request)
    result = URLLib3Session().send(request.prepare())
    payload = result.content.decode("utf-8")
    response_headers = {
        "content-type": result.headers.get("content-type", "application/json"),
        "cache-control": "no-store",
    }
    for name in ("mcp-session-id", "mcp-protocol-version"):
        if result.headers.get(name):
            response_headers[name] = result.headers[name]

    print(
        json.dumps(
            {
                "status": result.status_code,
                "request_sha256": hashlib.sha256(body_bytes).hexdigest(),
            }
        )
    )
    return {"statusCode": result.status_code, "headers": response_headers, "body": payload}
