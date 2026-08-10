# Task 13.3 journal

## Status

`completed`

## Summary

Default **Haiku**; escalate to **Sonnet** on complexity heuristics (compare/analyze/long/summarize|status workflows). Compose records `usage_events` with `event_type=llm_tokens` (real Anthropic usage or stub estimate).

## Acceptance criteria checklist

- [x] Simple QA → Haiku
- [x] Complexity paths → Sonnet
- [x] Tokens counted toward budgets via usage events

## Decision log

- Heuristic flags in `policy.py` (no extra LLM call for routing yet).
- Usage write failures are logged, not fatal to the answer path.
- Hard budget deny / Slack messaging remains Sprint 14.

## Needs human

- `ANTHROPIC_API_KEY` for live Haiku/Sonnet (stub otherwise).

## Files changed

- `api/app/agent/policy.py`, `nodes/route.py`, `nodes/compose.py`, `llm.py`
- `api/app/settings.py`
- `tests/agent/test_policy.py`, `test_usage_policy.py`
- `docs/agent.md`, `docs/governance.md`
- `Sprints/Sprint 13/Task 13.3/*`

## Resume notes

Batch 13.1–13.3 done. Next: **Continue Sprint 13 from Task 13.4** (guardrails + sprint-exit grounded dry-run).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/agent -q  → 12 passed
```
