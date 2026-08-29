"""BedrockPlanner: a real LLM as the brain, via the Bedrock Converse API.

Requires the ``[aws]`` extra (boto3), AWS credentials, and model access -
and it costs real money per run. Everything else in the system is untouched:
the AgentRunner drives this planner exactly like the mock one.

The translation is mechanical and worth reading once:

* our ``Tool``            -> Converse ``toolSpec``
* model ``toolUse`` block -> our ``ToolCall``
* our ``ToolResult``      -> Converse ``toolResult`` message
* model ``end_turn``      -> our ``Finish``
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from chef_andino.config import aws_region, bedrock_model_id
from chef_andino.planner.base import AgentState, Finish, PlannerAction, ToolCall
from chef_andino.tools.base import ToolRegistry

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system_prompt.md"


class BedrockPlanner:
    """Drive the mission with a foundation model on Amazon Bedrock."""

    def __init__(
        self,
        tools: ToolRegistry,
        client: Any | None = None,
        model_id: str | None = None,
    ) -> None:
        """``client`` is injectable so tests never need AWS (or boto3)."""
        if client is None:
            import boto3  # imported lazily: only real-LLM mode needs it

            client = boto3.client("bedrock-runtime", region_name=aws_region())
        self._client = client
        self._model_id = model_id or bedrock_model_id()
        self._toolspecs = tools.as_bedrock_toolspecs()
        self._system = SYSTEM_PROMPT_PATH.read_text()
        self._messages: list[dict] = [
            {"role": "user", "content": [{"text": "Begin your mission."}]}
        ]
        self._pending_tool_use_id: str | None = None

    def next_action(self, state: AgentState) -> PlannerAction:
        """Feed the last tool result back to the model and ask what is next."""
        if self._pending_tool_use_id is not None:
            result = state.last_result()
            payload = (
                {"json": {"data": result.data}}
                if result and result.ok
                else {"text": f"ERROR: {result.error if result else 'no result'}"}
            )
            self._messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "toolResult": {
                                "toolUseId": self._pending_tool_use_id,
                                "content": [payload],
                                "status": "success" if result and result.ok else "error",
                            }
                        }
                    ],
                }
            )
            self._pending_tool_use_id = None

        response = self._client.converse(
            modelId=self._model_id,
            system=[{"text": self._system}],
            messages=list(self._messages),  # a copy: the SDK owns what it gets
            toolConfig={"tools": self._toolspecs},
        )
        message = response["output"]["message"]
        self._messages.append(message)

        for block in message["content"]:
            if "toolUse" in block:
                tool_use = block["toolUse"]
                self._pending_tool_use_id = tool_use["toolUseId"]
                rationale = next(
                    (b["text"] for b in message["content"] if "text" in b), ""
                )
                return ToolCall(
                    tool_name=tool_use["name"],
                    args=_ensure_dict(tool_use["input"]),
                    rationale=rationale[:200],
                )
        return Finish("model_end_turn")


def _ensure_dict(value: Any) -> dict:
    """Some SDK paths deliver tool input as a JSON string - normalize."""
    if isinstance(value, str):
        return json.loads(value)
    return dict(value)
