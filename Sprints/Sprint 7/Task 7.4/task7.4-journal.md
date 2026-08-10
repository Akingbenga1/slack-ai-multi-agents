# Task 7.4 journal

## Status

`completed`

## Summary

`iter_csv_messages` / `iter_xlsx_messages` map tabular dumps via default header aliases or `column_map=` overrides into `NormalizedMessage` (`source_format=csv|xlsx`). Missing channel column without override raises `MissingChannelError`; empty text / ts rows are skipped by the normalizer.

## Acceptance criteria checklist

- [x] CSV → shared schema — done
- [x] XLSX → shared schema — done
- [x] Missing channel / ts / text — done (raise MissingChannelError for no channel; skip empty text/ts)

## Decision log

- Alias table for common export headers (`message`→text, `channel_id`, etc.).
- Reuse `MissingChannelError` from JSON parser for consistent caller handling.
- Required columns: `ts` + `text` (raise if headers absent); channel column or `channel=` override.

## Needs human

None.

## Files changed

- `api/app/ingest/parsers/csv_xlsx.py`
- `api/app/ingest/parsers/__init__.py`
- `tests/ingest/test_csv_xlsx.py`
- `docs/slack-history-ingest.md`, `README.md` (with 7.5)

## Resume notes

Continue Task 7.5 (same batch).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/ingest -q  → 16 passed
```
