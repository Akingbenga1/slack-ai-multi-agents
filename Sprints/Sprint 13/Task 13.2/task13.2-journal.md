# Task 13.2 journal

## Status

`completed`

## Summary

Wired `PostgresSaver` (connection pool + `setup()`) for thread continuity. Thread keys are `{client_id}:{conversation_id}`. `AGENT_CHECKPOINTER=memory|postgres` with fail-open to memory. Bumped `langgraph` to `>=0.5,<0.7` for checkpoint-postgres compatibility.

## Acceptance criteria checklist

- [x] Postgres (or memory) checkpoints per thread
- [x] Tenant-scoped thread ids

## Decision log

- Checkpoint tables via LangGraph `setup()`, not Alembic (vendor-owned schema).
- Process-wide pool singleton for API lifetime; tests use `MemorySaver`.
- Sanitized `:` out of conversation_id to keep a two-part key.

## Needs human

None new (uses existing Postgres).

## Files changed

- `api/app/agent/checkpointer.py`, `graph.py`, `run.py`
- `pyproject.toml`, `uv.lock` (`langgraph-checkpoint-postgres`, langgraph 0.6.x)
- `tests/agent/test_checkpointer.py`, continuity test in `test_graph.py`
- `docs/agent.md`, `.env.example`
- `Sprints/Sprint 13/Task 13.2/*`

## Resume notes

Next in batch: **Task 13.3 — Haiku / Sonnet policy**.

## Open questions

None.

## Smoke test results

```
get_checkpointer(Settings()) → PostgresSaver (local Compose Postgres)
uv run pytest tests/agent -q  → 12 passed
```
