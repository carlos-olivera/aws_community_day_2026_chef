# ADR 0001: Monorepo with a single Python package

**Status:** accepted (backbone phase)

## Context

The system has an API layer, an agent, validators, a CLI and (later) Lambda
handlers. A common instinct is one package per concern (`backend/`,
`agent/`, `shared/`), or even separate repos.

## Decision

One installable package, `chef_andino`, under `src/`, holding everything
Python. Frontend, infra, data and docs are sibling top-level directories.

## Consequences

- Students run **one** `pip install -e .` and get one import root - no
  path gymnastics, no cross-package version skew.
- Business logic is transport-agnostic by construction: the CLI, FastAPI
  endpoints and (later) Lambda handlers are all thin wrappers over the same
  modules. The freeze Lambda of the cloud phase is `build_snapshot` with an
  event-parsing shim - which is itself a teaching point.
- If the project ever grows real deployment-unit boundaries, splitting a
  working monorepo is easier than stitching split packages back together.
