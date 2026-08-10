# Task 9.2 — Watermarks in Postgres

## Steps

- [x] Store helpers for per-channel sync watermarks (`sync_watermarks` table already migrated)
- [x] Persist per-channel `oldest` / `latest` Slack ts cursors
- [x] Upsert by `(tenant_id, source, channel_id)`; merge bounds on update
- [x] Expose read helpers for incremental sync (`latest` → history `oldest=`)
- [x] Light unit tests for merge / upsert behaviour

## Acceptance criteria

- [x] Each tenant channel can store oldest + latest cursors
- [x] Upsert advances `latest` and keeps the earliest `oldest`
- [x] Ready for Task 9.3 Celery sync to read/write watermarks
