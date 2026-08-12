# Task 33.3 journal

## Status

`completed`

## Summary

Replaced Claude nicknames on the graph with vendor-neutral `fast` / `capable`. Policy/route/run/compose use those tiers only; Anthropic and Ollama adapters map tiers to concrete model ids. Usage events continue to record `result.model` (resolved id).

## Acceptance criteria checklist

- [x] Graph / policy use only `fast` / `capable`
- [x] Tier → vendor model id mapping lives inside each adapter
- [x] Usage meta keeps resolved `model` id from `LlmResult`

## Decision log

- No second Strategy map for Claude nicknames — mapping is private `_model_id` on each adapter.
- Updated agent tests that asserted `haiku`/`sonnet` tier strings to `fast`/`capable`.

## Needs human

None.

## Files changed

- `api/app/agent/state.py`, `policy.py`, `run.py`, `routes.py`
- `api/app/agent/llm.py` (tier mapping)
- `tests/agent/*` (tier assertions)
- `docs/agent.md`, `docs/governance.md`
- `Sprints/Sprint 33/Task 33.3/task33.3.md`

## Resume notes

Next: **Task 33.4** — assert compose/graph/policy do not import vendor names; keep stub + Anthropic + Ollama (recorded HTTP) coverage green; optional lazy-import of `anthropic` inside adapter so stub-only imports stay light.

## Open questions

None.
