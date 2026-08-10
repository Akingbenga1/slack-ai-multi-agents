# Task 9.4 — Beat schedule + on-demand enqueue API

## Steps

- [x] Per-tenant enable/disable via `agent_configs.schedules.slack_history_sync`
- [x] Hourly Celery Beat dispatcher → enqueue sync for enabled tenants with Slack install
- [x] Auth-required `POST /jobs/slack-history-sync` on-demand enqueue
- [x] Light unit tests + docs

## Acceptance criteria

- [x] Default Beat interval is hourly
- [x] Disabled tenants are skipped by Beat (on-demand still allowed)
- [x] Authenticated enqueue returns `task_id` (401/403 like heartbeat stub)
