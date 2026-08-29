"""BedrockPlanner round-trip with a fake client - no AWS, no network, no boto3."""

from chef_andino.planner.base import AgentState, Finish, ToolCall
from chef_andino.planner.bedrock import BedrockPlanner
from chef_andino.tools.base import ToolResult
from chef_andino.tools.factory import build_local_toolset


class FakeBedrockClient:
    """Replays scripted Converse responses and records what it was sent."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def tool_use_response(name, tool_input, text="thinking..."):
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {"text": text},
                    {"toolUse": {"toolUseId": "t-1", "name": name, "input": tool_input}},
                ],
            }
        },
        "stopReason": "tool_use",
    }


END_TURN = {
    "output": {"message": {"role": "assistant", "content": [{"text": "done"}]}},
    "stopReason": "end_turn",
}


def make_planner(store, settings, event_id, responses):
    tools = build_local_toolset(store, settings, event_id)
    client = FakeBedrockClient(responses)
    return BedrockPlanner(tools, client=client, model_id="test-model"), client


def test_tool_use_becomes_a_tool_call(store, frozen_event, settings):
    planner, client = make_planner(
        store, settings, frozen_event,
        [tool_use_response("get_event_snapshot", {}), END_TURN],
    )
    state = AgentState(event_id=frozen_event)
    action = planner.next_action(state)
    assert isinstance(action, ToolCall)
    assert action.tool_name == "get_event_snapshot"
    assert action.rationale == "thinking..."
    # The request carried our system prompt and the six toolSpecs.
    request = client.calls[0]
    assert "Chef Andino" in request["system"][0]["text"]
    assert len(request["toolConfig"]["tools"]) == 6


def test_tool_result_is_fed_back_and_end_turn_finishes(store, frozen_event, settings):
    planner, client = make_planner(
        store, settings, frozen_event,
        [tool_use_response("get_event_snapshot", {}), END_TURN],
    )
    state = AgentState(event_id=frozen_event)
    action = planner.next_action(state)
    state.history.append((action, ToolResult(ok=True, data={"total_responses": 40})))

    final = planner.next_action(state)
    assert isinstance(final, Finish)
    assert final.reason == "model_end_turn"
    # Second request must contain the toolResult for toolUseId t-1.
    tool_result = client.calls[1]["messages"][-1]["content"][0]["toolResult"]
    assert tool_result["toolUseId"] == "t-1"
    assert tool_result["status"] == "success"


def test_string_tool_input_is_normalized(store, frozen_event, settings):
    planner, _ = make_planner(
        store, settings, frozen_event,
        [tool_use_response("search_culinary_knowledge", '{"query": "quinoa"}')],
    )
    action = planner.next_action(AgentState(event_id=frozen_event))
    assert action.args == {"query": "quinoa"}
