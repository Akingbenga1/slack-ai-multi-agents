# Task 12.3 journal

## Status

`completed`

## Summary

Added `record_usage` writing to existing `usage_events`. Wired Slack echo → `slack_mention`; Celery heartbeat → `job`; sync → `sync_run`; upload ingest → `ingest`. `llm_tokens` / `report_post` constants ready for agent / proactive sprints.

## Acceptance criteria checklist

- [x] Durable rows for mention / sync / job / ingest
- [x] `llm_tokens` recordable
- [x] Feeds 12.2 budget sums; ready for 12.4 summary API

## Decision log

- Record on success paths (not enqueue) so failed jobs do not consume budget.
- Slack usage commit after successful echo only.

## Needs human

None.

## Files changed

- `api/app/governance/usage.py`
- `api/app/slack/routes.py`
- `worker/tasks.py`
- `tests/governance/test_usage.py`
- `docs/governance.md`

## Resume notes

Next: **Task 12.4 — Usage summary API**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/governance tests/billing -q  → 32 passed
```
