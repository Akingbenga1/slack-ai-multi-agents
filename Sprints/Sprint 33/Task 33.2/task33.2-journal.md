# Task 33.2 journal

## Status

`completed`

## Summary

Added `LLM_PROVIDER` and Ollama adapter settings; kept Anthropic env names as adapter secrets; updated `.env.example` and operator-facing docs so offline is explicitly `LLM_PROVIDER=stub`.

## Acceptance criteria checklist

- [x] Settings expose `llm_provider` and Ollama URL/model tags
- [x] Anthropic env names unchanged
- [x] `.env.example` documents the selector and adapter secrets

## Decision log

- Demo default `llm_provider=anthropic` per jira.
- Added `OLLAMA_MAX_TOKENS` (default 1024) so Ollama does not reuse `ANTHROPIC_MAX_TOKENS`.
- Default Ollama tags: `llama3.2` (fast) / `llama3.1` (capable) — operators override via env.

## Needs human

None.

## Files changed

- `api/app/settings.py`
- `.env.example`
- `docs/agent.md`, `docs/operator.md`, `docs/demo-script.md`, `docs/governance.md`
- `Sprints/Sprint 33/Task 33.2/task33.2.md`

## Resume notes

Done.

## Open questions

None.
