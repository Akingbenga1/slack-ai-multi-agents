# Task 13.2 — Postgres checkpointer

## Steps

- [x] Add `langgraph-checkpoint-postgres` dependency
- [x] Helper: SQLAlchemy URL → psycopg conninfo; process pool + `setup()`
- [x] Thread id `{client_id}:{conversation_id}` for tenant-scoped continuity
- [x] Wire checkpointer into compiled graph / `run_agent`
- [x] `AGENT_CHECKPOINTER=memory|postgres` setting + fallback
- [x] Light tests (thread key + memory continuity)

## Acceptance criteria

- [x] Checkpoints persist per tenant thread in Postgres (or memory for tests)
- [x] Threads cannot collide across tenants
