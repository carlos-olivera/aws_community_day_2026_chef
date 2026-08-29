#!/usr/bin/env python3
"""Exercise the deployed HTTPS lifecycle, authorization, fallback, and optional load."""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import boto3

from chef_andino.config import aws_region

ROOT = Path(__file__).resolve().parents[1]


def request(
    base_url: str,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    passphrase: str | None = None,
    idempotency_key: str | None = None,
) -> tuple[int, Any, float]:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    if passphrase:
        headers["Authorization"] = f"Bearer {passphrase}"
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(
            urllib.request.Request(base_url + path, data=data, headers=headers, method=method),
            timeout=35,
        ) as response:
            raw = response.read()
            payload = json.loads(raw) if raw else {}
            return response.status, payload, time.perf_counter() - started
    except urllib.error.HTTPError as error:
        raw = error.read()
        payload = json.loads(raw) if raw else {}
        return error.code, payload, time.perf_counter() - started


def configuration() -> tuple[str, str]:
    values = json.loads((ROOT / ".cloud/outputs.json").read_text())
    base_url = values["ChefAndinoFrontend"]["SiteUrl"]
    secret_arn = values["ChefAndinoSurvey"]["PresenterSecretArn"]
    value = boto3.client("secretsmanager", region_name=aws_region()).get_secret_value(
        SecretId=secret_arn
    )["SecretString"]
    return base_url, json.loads(value)["passphrase"]


def reset(base_url: str, passphrase: str, synthetic: bool) -> dict[str, Any]:
    status, payload, _ = request(
        base_url,
        "POST",
        "/api/events/demo-event/reset",
        body={"seedSynthetic": synthetic},
        passphrase=passphrase,
    )
    assert status == 200, payload
    return payload


def lifecycle(base_url: str, passphrase: str) -> None:
    wrong, _, _ = request(
        base_url,
        "POST",
        "/api/events/demo-event/reset",
        body={"seedSynthetic": False},
        passphrase="incorrecta",
    )
    assert wrong == 401, f"wrong presenter key returned {wrong}"
    reset_result = reset(base_url, passphrase, True)
    assert reset_result["seeded"] > 0
    status, stats, _ = request(base_url, "GET", "/api/events/demo-event/stats")
    assert status == 200 and stats["total_responses"] == reset_result["seeded"], stats

    frozen, _, _ = request(
        base_url, "POST", "/api/events/demo-event/freeze", passphrase=passphrase
    )
    assert frozen == 200
    rejected, _, _ = request(
        base_url,
        "POST",
        "/api/events/demo-event/responses",
        body=synthetic_response(),
        idempotency_key=str(uuid.uuid4()),
    )
    assert rejected == 409, f"response after freeze returned {rejected}"

    generated, run, _ = request(
        base_url, "POST", "/api/events/demo-event/generate", passphrase=passphrase
    )
    assert generated == 202, run
    run_id = run["run_id"]
    deadline = time.monotonic() + 360
    while time.monotonic() < deadline:
        code, state, _ = request(
            base_url,
            "GET",
            f"/api/events/demo-event/runs/{run_id}",
            passphrase=passphrase,
        )
        assert code == 200, state
        print(f"run {run_id}: {state['status']} ({len(state.get('steps', []))} steps)")
        if state["status"] == "COMPLETED":
            break
        if state["status"] == "FAILED":
            raise RuntimeError(state.get("error", "AgentCore run failed"))
        time.sleep(5)
    else:
        raise TimeoutError("AgentCore run exceeded six minutes")

    menu_code, menu, _ = request(base_url, "GET", "/api/events/demo-event/menu")
    assert menu_code == 200 and menu["generation_mode"] == "live_agentcore", menu
    assert menu["validation"]["passed"] is True
    reset(base_url, passphrase, False)
    missing, _, _ = request(base_url, "GET", "/api/events/demo-event/menu")
    assert missing == 404, "reset left the prior menu visible"
    fallback_code, fallback, _ = request(
        base_url,
        "POST",
        "/api/events/demo-event/fallback/reveal",
        passphrase=passphrase,
    )
    assert fallback_code == 200, fallback
    _, fallback_menu, _ = request(base_url, "GET", "/api/events/demo-event/menu")
    assert fallback_menu["generation_mode"] == "fallback_last_good"
    print("HTTPS lifecycle, auth, live menu, reset, and fallback verified")


def synthetic_response() -> dict[str, Any]:
    return {
        "diet": "none",
        "lactose_intolerant": False,
        "gluten_free": False,
        "allergies": [],
        "spice_level": "medium",
        "cuisine_preference": "andean_fusion",
        "preferred_ingredients": ["quinoa"],
        "consent": True,
    }


def load_test(base_url: str, passphrase: str) -> None:
    reset(base_url, passphrase, False)
    latencies: list[float] = []
    failures: list[tuple[int, Any]] = []

    def submit(_: int) -> tuple[int, Any, float]:
        return request(
            base_url,
            "POST",
            "/api/events/demo-event/responses",
            body=synthetic_response(),
            idempotency_key=str(uuid.uuid4()),
        )

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(submit, index) for index in range(1300)]
        for future in as_completed(futures):
            code, payload, latency = future.result()
            latencies.append(latency)
            if code >= 500 or code != 201:
                failures.append((code, payload))
    elapsed = time.monotonic() - started
    p95 = statistics.quantiles(latencies, n=100)[94]
    _, stats, _ = request(base_url, "GET", "/api/events/demo-event/stats")
    assert not failures, failures[:5]
    assert stats["total_responses"] == 1300, stats["total_responses"]
    assert elapsed < 180, elapsed
    assert p95 < 1.5, p95
    print(f"load verified: 1300 responses in {elapsed:.1f}s, p95={p95:.3f}s")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--load-test", action="store_true")
    parser.add_argument("--reset-only", action="store_true")
    args = parser.parse_args()
    base_url, passphrase = configuration()
    if args.reset_only:
        result = reset(base_url, passphrase, False)
        print(f"demo reset to cycle {result['cycle']}")
    elif args.load_test:
        load_test(base_url, passphrase)
    else:
        lifecycle(base_url, passphrase)


if __name__ == "__main__":
    main()
