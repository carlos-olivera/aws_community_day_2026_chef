# Governance

> **Probabilistic intelligence. Deterministic control.**
>
> We do not try to make the LLM never be wrong. We build a system where its
> mistakes do not necessarily become actions.

Chef Andino has three distinct control layers. Keeping them separate - and
knowing which is which - is the single most transferable lesson in this
repo.

| Layer | File | Role | Analogy |
|---|---|---|---|
| **Evaluator** | [`tools/evaluate.py`](../src/chef_andino/tools/evaluate.py) | the agent's own compass: scores candidates, zeroes on hard-gate violations | advice |
| **Validator** | [`validation/validator.py`](../src/chef_andino/validation/validator.py) | the door: deterministic pass/fail on the exact publish artifact | law |
| **Policy** | [`policy/engine.py`](../src/chef_andino/policy/engine.py) | the guard at the door: may this principal perform this action under these facts? | enforcement |

The agent can *skip* the evaluator (it only wastes its own budget). It
cannot skip the validator or the policy - they live inside the
`validate_and_publish_menu` tool
([`tools/publish.py`](../src/chef_andino/tools/publish.py)), outside the
agent's control.

## One rule, two enforcement points

The hard constraints (allergens, dietary coverage, inventory, spice) are
implemented **once** in [`validation/gates.py`](../src/chef_andino/validation/gates.py)
and consumed twice: the evaluator uses them as zero-score gates, the
validator as publish blockers. The rules cannot drift apart because there
is only one copy.

`"DO NOT violate allergies"` in a prompt is a wish. `check_allergens()` is
a guarantee - it even cross-checks each dish's ingredients against the
inventory's allergen labels, so a *mislabelled* dish is caught too.

## The policy engine

[`policies.yaml`](../src/chef_andino/policy/policies.yaml) is deliberately
Cedar-shaped: default-deny, explicit permits with conditions, first match
wins.

```yaml
- id: allow-validated-publish
  effect: ALLOW
  principal: agent/chef-andino
  action: publish_menu
  when:
    validation_passed: true
    event_state: GENERATING
    snapshot_version_matches: true
```

The crucial detail is in `tools/publish.py`: the `when` context is built
from **facts the gate computes itself** (it re-runs the validator, reads
the event state from the store, compares snapshot versions). The agent
never gets to *claim* `validation_passed: true`. Enforcement happens
outside the model - the model does not decide whether the rule applies.

Cloud-phase translation (AgentCore Policy, Cedar):

```cedar
permit (
  principal == Agent::"chef-andino",
  action == Action::"publish_menu",
  resource
) when {
  context.validation_passed == true &&
  context.event_state == "GENERATING" &&
  context.snapshot_version_matches == true
};
```

Same shape, line for line - which is exactly why the local stub is written
this way. In the cloud, AgentCore Policy intercepts tool calls at the
AgentCore Gateway, so not even a compromised tool implementation can be
reached without passing the rules.

## The DENY -> ALLOW demo

Two ways to see it, both writing to `audit.jsonl`:

**1. Organic - every default agent run** (`chef run-agent`): the mock
planner's flawed first candidate reaches the gate, validation fails,
policy denies:

```
POLICY DENY  no rule matched; closest rule 'allow-validated-publish'
             requires validation_passed is False (rule requires True)
```

The planner reads the failed checks, repairs the menu, and the second
attempt gets `POLICY ALLOW`.

**2. Explicit - `chef demo-governance`** (on a frozen event): builds a
*perfectly valid* menu, then tries to publish it with
`skip_validation=True` - simulating code that bypasses the validator. The
menu is fine; the policy still refuses, because `validation_passed` is a
fact about *process*, not about the artifact. Then the honest path runs
and is allowed. This is the 30-second stage demo:

> "The model wanted to publish. The system did not let it."
>
> **Autonomy without governance is just uncontrolled automation.**

## What each layer catches

| Failure | Caught by |
|---|---|
| Menu with a declared allergen | validator (`allergens`) -> policy DENY |
| Vegan guests but a meat-only dinner main | validator (`dietary_coverage`) |
| Ingredient not in stock | validator (`inventory`) |
| Menu computed from a stale snapshot | validator (`snapshot_version`) |
| Publishing while the event is not GENERATING | policy (`event_state`) |
| Any attempt to skip validation | policy (`validation_passed`) |
| Agent looping forever / hammering the web | runner budgets (see [agent-loop.md](agent-loop.md)) |
| Output that does not match the Menu schema | Pydantic parse at the gate - validation cannot even start |
