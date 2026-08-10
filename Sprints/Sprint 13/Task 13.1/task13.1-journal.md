# Task 13.1 journal

## Status

`completed`

## Summary

Implemented LangGraph `AgentState` and nodes **route → retrieve → compose**. Retrieve calls `search_knowledge` with mandatory `client_id`. Compose uses Anthropic when keyed, else deterministic stub. Dry-run via `run_agent`, `POST /agent/dry-run`, and `scripts/agent_dry_run.py`.

## Acceptance criteria checklist

- [x] State carries tenant + RAG fields
- [x] Graph path route → retrieve → compose
- [x] Offline dry-run with stub LLM

## Decision log

- Messages use LangChain `HumanMessage` / `AIMessage` with `add_messages`.
- Stub LLM when `ANTHROPIC_API_KEY` empty so laptop tests/dry-runs work without Anthropic.
- Soft `hedge` flag when no hits (hard messaging in 13.4).

## Needs human

- `ANTHROPIC_API_KEY` for live (non-stub) compose — optional until demo; put in `.env`.

## Files changed

- `api/app/agent/*` (state, graph, run, llm, chunks, nodes, routes)
- `api/app/main.py`, `api/app/settings.py`
- `tests/agent/test_graph.py`, `test_policy.py`
- `docs/agent.md`, `scripts/agent_dry_run.py`, `.env.example`, `README.md`
- `Sprints/Sprint 13/Task 13.1/*`

## Resume notes

Next in batch: **Task 13.2 — Postgres checkpointer**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/agent -q  → 12 passed (after 13.2/13.3 also)
```
