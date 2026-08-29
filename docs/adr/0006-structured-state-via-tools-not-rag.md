# ADR 0006: Structured state via tools, not RAG

**Status:** accepted

## Context

It is tempting to put *everything* the agent should know - dish lore AND
current stock levels - into one vector store and retrieve it all
semantically.

## Decision

Split by nature of the information:

- **Semantic knowledge** (what tarwi is, which dishes suit a buffet) ->
  the RAG corpus (`search_culinary_knowledge`).
- **Real, changing state** (18 kg of quinoa, current prices, response
  counts) -> structured tools backed by a database
  (`get_available_ingredients`, `get_event_snapshot`).

## Consequences

- State is exact, current and cheap to query - no embedding staleness, no
  similarity fuzz on numbers that must be right.
- The corpus stays small and curated; retrieval quality problems and data
  freshness problems never mix.
- The pattern transfers directly to enterprise agents: manuals -> RAG,
  stock -> ERP API; documentation -> RAG, balance -> banking API.
- The mock planner cross-checks retrieved dishes against the inventory,
  modelling the general rule: knowledge suggests, state decides.
