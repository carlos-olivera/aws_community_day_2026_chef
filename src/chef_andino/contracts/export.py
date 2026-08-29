"""Export the Pydantic models as JSON Schema files.

Run ``make schemas`` (or ``python -m chef_andino.contracts.export``) after
changing :mod:`chef_andino.contracts.models`. A test asserts the checked-in
files match the models, so a stale schema fails CI instead of drifting.
"""

from __future__ import annotations

import json
from pathlib import Path

from chef_andino.contracts.models import (
    EventSnapshot,
    InventoryItem,
    Menu,
    SurveyResponse,
)

SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"

EXPORTS: dict[str, type] = {
    "survey_response": SurveyResponse,
    "event_snapshot": EventSnapshot,
    "inventory_item": InventoryItem,
    "menu": Menu,
}


def schema_for(model: type) -> dict:
    """Return the JSON Schema for a model, with a stable ``$id``."""
    schema = model.model_json_schema()
    name = next(k for k, v in EXPORTS.items() if v is model)
    return {"$id": f"https://chef-andino.example/schemas/{name}.schema.json", **schema}


def export_all(target_dir: Path = SCHEMAS_DIR) -> list[Path]:
    """Write every schema file and return the paths written."""
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in EXPORTS.items():
        path = target_dir / f"{name}.schema.json"
        path.write_text(json.dumps(schema_for(model), indent=2) + "\n")
        written.append(path)
    return written


if __name__ == "__main__":
    for p in export_all():
        print(f"wrote {p}")
