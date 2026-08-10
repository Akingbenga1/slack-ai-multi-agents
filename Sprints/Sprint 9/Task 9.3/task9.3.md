# Task 9.3 — Sync Celery task

## Steps

- [x] Domain sync: list channels → history with watermark → normalize `web_api` → ingest
- [x] Advance per-channel watermarks after successful pull
- [x] Celery task `worker.slack_history_sync` + job_meta kind + enqueue helper
- [x] Light unit tests for sync helper (mocked Slack + ingest)

## Acceptance criteria

- [x] Incremental pull uses install-store token + watermarks
- [x] Messages enter the same ingest pipeline with `source_format=web_api`
- [x] Task persists job success/failure like upload ingest
- [x] Beat / on-demand API deferred to Task 9.4
