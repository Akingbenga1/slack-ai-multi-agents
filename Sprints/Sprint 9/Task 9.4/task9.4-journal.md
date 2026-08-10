# Task 9.4 journal

## Status

`completed`

## Summary

Hourly Beat runs `worker.dispatch_slack_history_syncs`, which enqueues `worker.slack_history_sync` for tenants that have a Slack install and are not disabled via `agent_configs.schedules.slack_history_sync.enabled` (default on). On-demand `POST /jobs/slack-history-sync` always enqueues; `GET`/`PATCH /jobs/slack-history-sync/schedule` toggles Beat enable.

## Acceptance criteria checklist

- [x] Default Beat interval hourly — done (`SLACK_HISTORY_SYNC_INTERVAL_SECONDS=3600`)
- [x] Disabled tenants skipped by Beat; on-demand allowed — done
- [x] Auth enqueue returns `task_id` (401/403) — done

## Decision log

- Dispatcher task (not one Beat entry per tenant) so enable/disable stays in Postgres.
- Enable gates **Beat only**; on-demand bypasses for portal/manual refresh.
- Schedule JSON on existing `agent_configs.schedules` — no new migration.
- Demo seed upserts default agent_config with sync enabled.

## Needs human

- Live sync still needs Slack reinstall with history scopes + worker/Beat/TEI/Qdrant (Sprint 4 rollup).

## Files changed

- `api/app/slack/schedule.py` (new)
- `api/app/jobs/routes.py`, `api/app/membership.py`, `api/app/settings.py`
- `worker/celery_app.py`, `worker/tasks.py`
- `tests/slack/test_schedule.py`, `tests/slack/test_schedule_api.py`
- `docs/celery.md`, `docs/slack-web-api.md`, `README.md`, `.env.example`
- `Sprints/Sprint 9/Task 9.4/*`

## Resume notes

Next: **Task 9.5 — Sync status read API** (last success/failure for portal).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/slack -q  →  20 passed
```
