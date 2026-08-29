"""CDK custom-resource handler that initializes reproducible demo data."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from chef_andino.cloud.common import store
from chef_andino.store.dynamodb import _ddb


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Seed inventory and the default event; deletion intentionally does nothing."""
    if event.get("RequestType") == "Delete":
        return {"PhysicalResourceId": "ChefAndinoSeedData"}
    cloud_store = store()
    inventory = json.loads(Path(os.environ["INVENTORY_SEED_PATH"]).read_text())
    with cloud_store.inventory.batch_writer(overwrite_by_pkeys=["ingredient_id"]) as batch:
        for item in inventory:
            batch.put_item(Item=_ddb(item))
    cloud_store.ensure_event(os.environ.get("PUBLIC_EVENT_ID", "demo-event"))
    return {
        "PhysicalResourceId": "ChefAndinoSeedData",
        "Data": {"InventoryItems": len(inventory)},
    }
