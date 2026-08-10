# Task 7.3 journal

## Status

`completed`

## Summary

`iter_json_messages` / `iter_ndjson_messages` accept history-style wrappers, flat arrays, and single objects. Flat JSON without channel raises `MissingChannelError`; NDJSON lines without channel are skipped (unless `channel=` override).

## Acceptance criteria checklist

- [x] JSON → shared schema — done
- [x] NDJSON → shared schema — done
- [x] Missing channel behavior — done (raise for JSON; skip line for NDJSON); documented

## Decision log

- JSON fail-fast vs NDJSON per-line skip: batch files should be fixed; streams should continue.
- Accept `channel` or `channel_id` (string or `{id}` object).

## Needs human

None.

## Files changed

- `api/app/ingest/parsers/json_dump.py`
- `tests/ingest/test_json_dump.py`
- `docs/slack-history-ingest.md`, `README.md`

## Resume notes

Next batch: **Continue Sprint 7 from Task 7.4** (CSV/Excel parser, then 7.5 pipeline).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/ingest -q  → 10 passed
```
