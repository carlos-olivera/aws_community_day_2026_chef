# ADR 0002: Ports and adapters for the six tools

**Status:** accepted

## Context

The local agent uses snapshot, inventory, knowledge, optional canned web
research, evaluation and publication capabilities. In the deployed cloud
version the Gateway exposes snapshot, inventory, Knowledge Base retrieval,
deterministic evaluation, validation and publication as Lambda-backed MCP
tools. Browser/Web Search and Code Interpreter are intentionally omitted.

## Decision

Each capability is a `typing.Protocol` (the port) with a `Local*` adapter
now and an AWS adapter later. A thin `Tool` record (name, description,
JSON-Schema args, function) makes each port callable-by-name through a
`ToolRegistry` - deliberately the same shape as Bedrock tool-use / MCP.

## Consequences

- The agent loop never changes when the backend does; swapping
  `build_local_toolset` for `build_aws_toolset` is the entire migration.
- The registry projects directly to Bedrock `toolSpec`s
  (`as_bedrock_toolspecs()`), so the mock planner and a real LLM drive
  literally the same tool surface.
- Cost: a little indirection (port + adapter + wrapper per tool). Accepted:
  the indirection IS the lesson - "tools are the API of the agent's world".
