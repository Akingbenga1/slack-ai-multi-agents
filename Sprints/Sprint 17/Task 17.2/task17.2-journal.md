# Task 17.2 journal

## Status

`completed`

## Summary

Added per-tenant recurring report schedule on `agent_configs.schedules.recurring_report` (`enabled`, `channel_id`, `cadence`, `window_label`) with GET/PATCH `/jobs/recurring-report/schedule`. Defaults: disabled, weekly, no channel. `list_tenants_for_scheduled_reports` requires enable + channel for Beat.

## Acceptance criteria checklist

- [x] Channel + cadence + enable
- [x] Safe defaults (opt-in)
- [x] Due-list helper for 17.3

## Decision log

- Opt-in (`enabled=false` default) unlike Slack sync (default on) — avoid surprise channel posts.
- Cadence limited to `daily` / `weekly`; window_label auto-derived unless overridden.
- Module under `api/app/reports/` (not Slack package).

## Needs human

None new — live channel post still needs Slack install (17.3+).

## Files changed

- `api/app/reports/{__init__,schedule}.py`
- `api/app/jobs/routes.py`, `api/app/membership.py`
- `tests/reports/{test_schedule,test_schedule_api}.py`
- `docs/celery.md`, `docs/agent.md`
- `Sprints/Sprint 17/Task 17.2/*`

## Resume notes

Next: **Task 17.3 — Celery Beat report task** (sync freshness preference; direct channel post).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/reports tests/agent/test_report.py tests/mcp/test_server.py -q
→ 28 passed
```

## Commercial mapping

TM-13 / OR-03 (schedules) — config before Beat posts.
