"""Tool 2/6: ``get_available_ingredients`` - real state, NOT RAG.

Teaching point said out loud in the talk: "RAG is for finding knowledge.
I am not using it as a transactional database." Stock levels are facts that
change; they live behind a tool backed by a database (a JSON seed file
locally, DynamoDB in the cloud).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from chef_andino.contracts.models import InventoryItem
from chef_andino.tools.base import Tool, ToolResult


class InventorySource(Protocol):
    """Port: anything that can list what the kitchen actually has."""

    def list(self) -> list[InventoryItem]:
        """Return every inventory item (including out-of-stock ones)."""
        ...


class LocalInventorySource:
    """Adapter: read the seed file from ``data/inventory.seed.json``."""

    def __init__(self, path: Path) -> None:
        """Bind to the seed file path."""
        self._path = path

    def list(self) -> list[InventoryItem]:
        """Return every inventory item, validated against the contract."""
        raw = json.loads(self._path.read_text())
        return [InventoryItem.model_validate(item) for item in raw]


def make_inventory_tool(source: InventorySource) -> Tool:
    """Wrap the port as a named tool."""

    def fn() -> ToolResult:
        items = source.list()
        return ToolResult(ok=True, data=[i.model_dump(mode="json") for i in items])

    return Tool(
        name="get_available_ingredients",
        description=(
            "List the ingredients actually available in the kitchen, with "
            "quantities, allergens and dietary flags. Menus may only use "
            "ingredients that appear here with stock."
        ),
        fn=fn,
    )
