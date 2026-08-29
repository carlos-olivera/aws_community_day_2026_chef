"""Data contracts: the four schemas every layer of the system agrees on.

Teaching concept: *structured output*. The agent's final product is not free
text - it is a Menu object that must validate against a strict JSON Schema.
The Pydantic models in :mod:`chef_andino.contracts.models` are the source of
truth; :mod:`chef_andino.contracts.export` dumps them as JSON Schema files
that are checked in and kept in sync by a test.
"""

from chef_andino.contracts.models import (
    DISCLAIMER,
    Check,
    Coverage,
    DerivedConstraints,
    EvaluationResult,
    EventSnapshot,
    InventoryItem,
    Menu,
    MenuItem,
    SurveyResponse,
    ValidationReport,
)

__all__ = [
    "DISCLAIMER",
    "Check",
    "Coverage",
    "DerivedConstraints",
    "EvaluationResult",
    "EventSnapshot",
    "InventoryItem",
    "Menu",
    "MenuItem",
    "SurveyResponse",
    "ValidationReport",
]
