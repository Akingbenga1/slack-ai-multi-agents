# Task 9.5 journal

## Status

`completed`

## Summary

`GET /jobs/slack-history-sync/status` returns portal-ready sync status: Beat `enabled`, `slack_connected`, `last_success` / `last_failure` / `last_job` from `jobs` (`kind=slack_history_sync`), and watermark summary (`channel_count`, `last_synced_at`). Sprint 9 code path complete; live Qdrant verify still Needs human.

## Acceptance criteria checklist

- [x] Last success/failure readable — done
- [x] 401 / 403 — done (same tenant gate as other `/jobs` routes)

## Decision log

- Single status endpoint under `/jobs` alongside enqueue/schedule (no separate sync router yet).
- Include watermarks + install flag so portal can show freshness without a second call.
- Domain helper in `api.app.slack.sync_status` keeps the route thin.

## Needs human

- Slack reinstall with history scopes + running API/worker/Beat/TEI/Qdrant to confirm new messages land in Qdrant without re-upload (Sprint 9 exit).

## Files changed

- `api/app/slack/sync_status.py` (new)
- `api/app/jobs/routes.py`
- `tests/slack/test_sync_status.py`
- `docs/celery.md`, `docs/slack-web-api.md`, `README.md`
- `Sprints/Sprint 9/Task 9.5/*`

## Resume notes

Sprint 9 tasks 9.1–9.5 complete in code. Next: **Continue Sprint 10 from Task 10.1** (`search_knowledge`).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/slack -q  →  23 passed
```
