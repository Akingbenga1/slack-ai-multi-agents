# Task 9.2 journal

## Status

`completed`

## Summary

Added `api/app/slack/watermarks.py` helpers over the existing `sync_watermarks` table. Per-channel `oldest`/`latest` Slack timestamps live in `meta`; `cursor` mirrors `latest` for incremental `conversations.history(oldest=…)`. Upsert merges bounds (min oldest, max latest).

## Acceptance criteria checklist

- [x] Per-channel oldest + latest — done (`meta` + `cursor`)
- [x] Merge on upsert — done (`ts_min` / `ts_max`)
- [x] Ready for Celery sync — done

## Decision log

- No new migration — table already in initial schema.
- Default `source=slack_live` (file bootstrap can use `slack_history` later).
- Keep both bounds in JSONB `meta`; `cursor` = high-water for the common read path.

## Needs human

None new (same Slack reinstall / live verify as 9.1).

## Files changed

- `api/app/slack/watermarks.py` (new)
- `tests/slack/test_watermarks.py`
- `docs/slack-web-api.md`
- `Sprints/Sprint 9/Task 9.2/*`

## Resume notes

Next: **Task 9.3 — Sync Celery task** (incremental pull → ingest; `source_format=web_api`).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/slack -q  →  9 passed
```
