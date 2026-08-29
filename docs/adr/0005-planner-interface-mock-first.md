# ADR 0005: Planner interface, mock-first

**Status:** accepted

## Context

The LLM is the most expensive, least deterministic and least debuggable
part of the system. Building around it first makes every test slow, flaky
and costly - and hides whether the surrounding system actually works.

## Decision

Isolate the model behind a one-method protocol
(`Planner.next_action(state) -> ToolCall | Finish`) and build the
**deterministic MockPlanner first**: a readable, scripted decision policy
that drives the real tools through the real registry, with optional flaw
injection so the governance path is exercised on every run.
`BedrockPlanner` (Converse API) is a drop-in second implementation behind
the `[aws]` extra.

## Consequences

- The whole pipeline - tools, validator, policy, trace, API, UI - is
  testable offline, for free, deterministically (66 tests in <1 s).
- Swapping in a real model changes zero lines of the runner; the diff IS
  the lesson about where the "intelligence boundary" sits.
- The mock is honest about being scripted: it is a decision policy, not a
  fake text generator, so it cannot overfit tests to prose.
- Risk: the mock's happy path may hide real-LLM failure modes (malformed
  args, hallucinated tools). Mitigated by runner-level handling (unknown
  tools and crashes become error ToolResults) and dedicated tests.
