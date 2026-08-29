# The agent loop

> **Agent = Model + Goal + Context + Tools + Loop**

This document explains the loop half of that equation: the
[`AgentRunner`](../src/chef_andino/agent/runner.py), the
[`Planner`](../src/chef_andino/planner/base.py) seam, the budgets and the
trace. In the cloud phase, Amazon Bedrock AgentCore **Harness** plays the
runner's role as a managed service - locally it is ~60 lines you can read.

## The seam: Planner

```python
class Planner(Protocol):
    def next_action(self, state: AgentState) -> ToolCall | Finish: ...
```

That is the entire LLM boundary. `AgentState` holds the mission id and the
full history of `(ToolCall, ToolResult)` pairs. The planner answers one
question - *given what has happened, what next?* - and the runner does
everything else.

Two implementations ship:

| | MockPlanner | BedrockPlanner |
|---|---|---|
| File | [`planner/mock.py`](../src/chef_andino/planner/mock.py) | [`planner/bedrock.py`](../src/chef_andino/planner/bedrock.py) |
| Brain | a scripted, readable decision policy | a foundation model on Amazon Bedrock (Converse API) |
| Cost / network | zero / none | real money / AWS credentials required |
| Determinism | same corpus + snapshot -> same menu | probabilistic |
| Use | classroom, tests, CI | the real thing |

**The runner cannot tell them apart.** That indifference is the design: swap
the brain, keep the harness, contracts, validator and policy.

## The mock mission, step by step

```
 1. get_event_snapshot            observe the world
 2. get_available_ingredients     what exists, really
 3. search_culinary_knowledge     breakfast dishes
 4. search_culinary_knowledge     starters
 5. search_culinary_knowledge     mains
 6. search_culinary_knowledge     desserts
 7. research_web                  optional inspiration (survives failure)
 8. validate_and_publish_menu     flawed candidate -> validator FAILS -> policy DENY
 9. evaluate_menu                 repaired candidate -> score
10. validate_and_publish_menu     validator PASSES -> policy ALLOW -> PUBLISHED
```

### Flaw injection

`MockPlanner(first_candidate_flaw="declared_allergen")` - the default in
the CLI - makes the first candidate include a banned-allergen dish (the
iconic Sopa de Mani, when peanut is declared) and publish it
*overconfidently, without evaluating first*. The gate refuses, the planner
reads the failed check ids from the ToolResult, repairs the menu and
succeeds. Every classroom run therefore shows the reject -> repair ->
publish cycle instead of a suspiciously perfect first try.

Pass `--no-flaw` (CLI) or `first_candidate_flaw=None` for a clean run.

## Budgets: bounded autonomy

> Autonomy is not unlimited freedom. It is freedom to decide **within
> explicit boundaries.**

Defined in [`config.py`](../src/chef_andino/config.py), enforced in
[`agent/budgets.py`](../src/chef_andino/agent/budgets.py) by the runner -
never by the planner:

| Budget | Value | Charged on |
|---|---|---|
| `max_iterations` | 10 | every executed tool call (deciding to stop is free) |
| `max_web_queries` | 3 | `research_web` |
| `max_candidate_menus` | 5 | `evaluate_menu` |
| `max_validation_retries` | 2 | `validate_and_publish_menu` (1 + retries attempts) |

A tool call over budget returns an **error ToolResult** the planner can
react to; exceeding `max_iterations` halts the loop outright. The tests
prove that a runaway planner is stopped
([`test_runner.py`](../tests/unit/test_runner.py)). The talk used
`max_iterations=8`; we use 10 because the reference mission takes exactly
10 tool calls - lower it and watch the harness cut the agent off.

## Observability: the trace

Every run writes two JSONL files under `.localdata/runs/<run_id>/`:

- **`trace.jsonl`** - one record per step: tool, compacted args, the
  planner's one-line rationale, ok/error summary, budgets remaining.
- **`audit.jsonl`** - one record per policy decision: principal, action,
  the context *as computed by the system*, effect, rule id, reason.

We show **observable actions, not chain-of-thought** - the same philosophy
as AgentCore Observability (CloudWatch / OTEL traces) in the cloud phase.
When a chatbot fails, someone reads a bad answer; when an agent fails, it
may execute a bad action. That is why the audit log exists.

## Running with a real model

```bash
pip install -e ".[aws]"        # adds boto3
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID=anthropic.claude-sonnet-5   # or any tool-use model
chef run-agent --planner bedrock
```

Cost warning: one mission is a handful of model invocations with tool
definitions and history attached. Cheap for a demo, not free. The system
prompt lives at
[`planner/prompts/system_prompt.md`](../src/chef_andino/planner/prompts/system_prompt.md) -
notice it *restates* the hard rules but the system never relies on the
model obeying them: the validator and policy would catch it anyway. Prompts
are wishes; gates are guarantees.
