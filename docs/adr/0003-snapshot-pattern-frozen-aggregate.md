# ADR 0003: The snapshot pattern - a frozen, versioned aggregate

**Status:** accepted

## Context

Survey responses keep arriving until the presenter closes the survey. An
agent reading a live table mid-mission would compute a menu from data that
no longer matches what anyone saw; and passing hundreds of raw responses
to an LLM would waste tokens, leak individual data and open an injection
surface.

## Decision

The event lifecycle is an explicit state machine (OPEN -> FROZEN ->
GENERATING -> PUBLISHED). Freezing runs `build_snapshot` - a pure function -
and writes an **immutable, versioned** `EventSnapshot`. Snapshots can never
be overwritten; re-freezing bumps the version. The agent reads exactly one
snapshot version, and the published menu must cite it (validator check
`snapshot_version`).

## Consequences

- Runs are reproducible: replay any run against its snapshot version.
- Individual responses never reach the LLM - only counts and derived
  constraints - which addresses privacy, tokens and injection at once.
- One LLM mission per event, not one invocation per participant:
  aggregation stays deterministic software.
- A failed run returns GENERATING -> FROZEN, so retrying is safe.
