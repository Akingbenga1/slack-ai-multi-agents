# Task 9.3 journal

## Status

`completed`

## Summary

Live Slack history sync is wired end-to-end in code: `sync_slack_history` pulls via the Web API client, normalizes with `SourceFormat.WEB_API`, ingests through the shared pipeline, and advances per-channel watermarks. Celery task `worker.slack_history_sync` mirrors upload ingest job lifecycle; `enqueue_slack_history_sync` defaults to the low queue.

## Acceptance criteria checklist

- [x] Incremental pull + install token + watermarks — done
- [x] Same ingest pipeline / `web_api` — done
- [x] Job success/failure persistence — done (`kind=slack_history_sync`)
- [x] Beat / on-demand API deferred — done (Task 9.4)

## Decision log

- Domain logic in `api/app/slack/sync.py`; worker task is orchestration only.
- Default enqueue `priority=-1` (bulk/low) so sync does not starve urgent jobs.
- Empty channel still upserts watermark (`last_synced_at`) for later status API.
- Boundary message may be re-fetched (`inclusive=True`); idempotent uuid5 upserts absorb it.

## Needs human

- Live sync still needs Slack reinstall with history scopes + running worker/TEI/Qdrant (same Sprint 4 rollup).

## Files changed

- `api/app/slack/sync.py` (new)
- `worker/tasks.py`, `worker/job_meta.py`
- `tests/slack/test_sync.py`
- `docs/celery.md`, `docs/slack-web-api.md`, `README.md`
- `Sprints/Sprint 9/Task 9.3/*`

## Resume notes

Next batch: **Continue Sprint 9 from Task 9.4** (Beat schedule + on-demand enqueue API), then 9.5 sync status read API.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/slack -q  →  11 passed
```
