"""Central configuration: paths, budgets and defaults.

Teaching concept: *bounded autonomy*. The budgets defined here are enforced
by the deterministic harness (:mod:`chef_andino.agent.runner`), NOT by the
planner. Even a misbehaving LLM cannot exceed them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Repository root = three levels up from this file (src/chef_andino/config.py).
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

DEFAULT_EVENT_ID = "demo-event"


@dataclass(frozen=True)
class Budget:
    """Hard limits on what one agent run may do.

    The original talk proposal used ``max_iterations = 8``; we use 10 because
    the reference mission (mock planner, flaw injection on) takes exactly
    10 tool calls. Lower it and watch the harness halt the agent mid-mission.
    """

    max_iterations: int = 10
    max_web_queries: int = 3
    max_candidate_menus: int = 5
    max_validation_retries: int = 2  # publish attempts allowed = 1 + retries


@dataclass(frozen=True)
class Settings:
    """Paths and defaults for the local (offline) deployment."""

    data_dir: Path = REPO_ROOT / "data"
    local_dir: Path = REPO_ROOT / ".localdata"
    corpus_dir: Path = REPO_ROOT / "data" / "corpus"
    inventory_path: Path = REPO_ROOT / "data" / "inventory.seed.json"
    responses_path: Path = REPO_ROOT / "data" / "synthetic_responses.json"
    budget: Budget = field(default_factory=Budget)

    @property
    def db_path(self) -> Path:
        """The single JSON file that stands in for DynamoDB."""
        return self.local_dir / "db.json"

    @property
    def runs_dir(self) -> Path:
        """Where each agent run writes its trace and audit log."""
        return self.local_dir / "runs"


def bedrock_model_id() -> str:
    """Model used by the optional BedrockPlanner (real-LLM mode only)."""
    return os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-5")


def aws_region() -> str:
    """Region used by the optional BedrockPlanner (real-LLM mode only)."""
    return os.environ.get("AWS_REGION", "us-east-1")
