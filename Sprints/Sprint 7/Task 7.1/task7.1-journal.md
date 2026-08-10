# Task 7.1 journal

## Status

`completed`

## Summary

Added `api/app/ingest` with `NormalizedMessage` + `SourceFormat` and `normalize_slack_message()` for Slack-shaped dicts (channel override, skip joins/empty, clear self `thread_ts`).

## Acceptance criteria checklist

- [x] Shared model — done (`NormalizedMessage`)
- [x] Normalizer stable fields — done
- [x] `source_format` required — done (`SourceFormat` enum)

## Decision log

- Package under `api/app/ingest` (shared by API + worker later).
- Skip noisy subtypes (`channel_join`, etc.) even when templated text exists.
- `content_key` = `channel:ts` for upcoming idempotent upsert (7.5).

## Needs human

None.

## Files changed

- `api/app/ingest/schema.py`, `normalize.py`, `__init__.py`
- `tests/ingest/test_normalize.py`
- `docs/slack-history-ingest.md`

## Resume notes

Continue Task 7.2 (same batch).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/ingest/test_normalize.py -q  → 4 passed
```
