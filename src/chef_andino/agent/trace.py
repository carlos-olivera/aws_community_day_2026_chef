"""Run traces: what the agent ACTUALLY did, step by step.

Two JSONL files per run under ``.localdata/runs/<run_id>/``:

* ``trace.jsonl`` - every planner action and tool result summary.
* ``audit.jsonl`` - every policy decision (written via the publisher's sink).

We never show chain-of-thought; we show observable actions - which is also
what AgentCore Observability (CloudWatch/OTEL) shows in the cloud phase.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from chef_andino.planner.base import ToolCall
from chef_andino.tools.base import ToolResult


class TraceWriter:
    """Append-only JSONL writer plus a live console rendering."""

    def __init__(self, runs_dir: Path, console: Console | None = None) -> None:
        """Create a fresh run directory named after a new run id."""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        self.run_id = f"{stamp}-{uuid.uuid4().hex[:6]}"
        self.run_dir = runs_dir / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._console = console or Console()

    def _append(self, filename: str, record: dict) -> None:
        record = {"at": datetime.now(timezone.utc).isoformat(), **record}
        with (self.run_dir / filename).open("a") as fh:
            fh.write(json.dumps(record, default=str) + "\n")

    def event(self, kind: str, **fields) -> None:
        """Record a lifecycle event (run_started, budget_exhausted, ...)."""
        self._append("trace.jsonl", {"kind": kind, **fields})
        self._console.print(f"[dim]{kind}[/dim] {fields if fields else ''}".rstrip())

    def step(
        self, step: int, action: ToolCall, result: ToolResult, remaining: dict
    ) -> None:
        """Record one loop step and render it like the on-stage display."""
        self._append(
            "trace.jsonl",
            {
                "kind": "step",
                "step": step,
                "tool": action.tool_name,
                "args": _compact_args(action.args),
                "rationale": action.rationale,
                "ok": result.ok,
                "summary": result.summary(),
                "budgets_remaining": remaining,
            },
        )
        icon = "[green]v[/green]" if result.ok else "[red]x[/red]"
        self._console.print(
            f" {icon} [bold]{action.tool_name}[/bold]  {result.summary()}"
        )
        if action.rationale:
            self._console.print(f"    [dim italic]{action.rationale}[/dim italic]")

    def audit_sink(self, record: dict) -> None:
        """The publisher writes every policy decision through this."""
        self._append("audit.jsonl", record)
        colour = "green" if record.get("effect") == "ALLOW" else "red"
        self._console.print(
            f"    [bold {colour}]POLICY {record.get('effect')}[/bold {colour}] "
            f"[dim]{record.get('reason')}[/dim]"
        )


def _compact_args(args: dict) -> dict:
    """Keep the trace readable: replace bulky values (menus) with a stub."""
    return {
        k: (v if not isinstance(v, dict) or len(json.dumps(v, default=str)) < 200
            else f"<{k}: {len(json.dumps(v, default=str))} bytes>")
        for k, v in args.items()
    }
