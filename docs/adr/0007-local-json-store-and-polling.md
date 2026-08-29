# ADR 0007: Local JSON store and a polling dashboard

**Status:** accepted locally; cloud implementation completed

## Context

The cloud deployment uses DynamoDB and the same two-second polling contract. For the
offline backbone we considered DynamoDB Local, moto, SQLite, and local
WebSocket emulation.

## Decision

- Storage: a single pretty-printed JSON file (`.localdata/db.json`) behind
  the `EventStore` protocol.
- Realtime: the dashboard polls `GET /stats` every 2 seconds.

## Consequences

- Students can open `db.json` in an editor and literally watch the state
  machine walk OPEN -> FROZEN -> GENERATING -> PUBLISHED. A DynamoDB
  container teaches nothing extra here and costs setup friction.
- Polling is sufficient at demo scale and keeps the deployed system easy to
  reset and operate. The UI depends only on the stats payload, so a future
  event transport would remain an adapter change.
- Known non-goals, accepted: no locking, no concurrency, no durability
  guarantees. The `EventStore` port is where DynamoDB lands later.
