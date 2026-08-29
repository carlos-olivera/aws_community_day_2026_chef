# ADR 0004: Deterministic validator + policy gate on publish

**Status:** accepted

## Context

"DO NOT violate allergies" in a prompt is not a safety mechanism. LLM
output is probabilistic; some rules must hold with certainty, and some
actions (publishing) must be authorized independently of what the model
believes.

## Decision

Two deterministic layers sit inside the `validate_and_publish_menu` tool,
outside the agent's control:

1. a **validator** - ordered, named, pure-Python checks over the exact
   artifact (shared gate functions with the evaluator, so rules exist once);
2. a **policy engine** - default-deny YAML rules (Cedar-shaped), evaluated
   against context facts the gate computes itself (`validation_passed`,
   `event_state`, `snapshot_version_matches`). Every decision is audited.

The evaluator remains advisory: skipping it wastes budget, nothing else.

## Consequences

- The model's mistakes do not become actions; the DENY -> repair -> ALLOW
  cycle is demonstrable in every run and in `chef demo-governance`.
- Policy checks *process*, not just artifacts: even a perfectly valid menu
  is denied if validation was skipped.
- The YAML rules translate line-for-line to Cedar for AgentCore Policy in
  the cloud phase - the local stub is shaped for that migration.
- Cost: publish re-runs validation even if the agent already evaluated.
  Accepted: the gate must never trust the caller.
