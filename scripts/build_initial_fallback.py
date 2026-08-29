#!/usr/bin/env python3
"""Build a private last-known-good artifact from the deterministic local planner."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    database = json.loads((ROOT / ".localdata/db.json").read_text())
    event = database["events"]["demo-event"]
    menu = event["menu"]
    snapshot = event["snapshots"][str(menu["snapshot_version"])]
    traces = sorted((ROOT / ".localdata/runs").glob("*/trace.jsonl"))
    trace = [json.loads(line) for line in traces[-1].read_text().splitlines()] if traces else []
    artifact = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "source": "deterministic_initial_deployment",
        "snapshot": snapshot,
        "menu": menu,
        "run": {"status": "COMPLETED", "steps": trace[-20:]},
    }
    output = ROOT / ".cloud/fallback/last-good.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, default=str))
    print(f"built fallback artifact {output}")


if __name__ == "__main__":
    main()
