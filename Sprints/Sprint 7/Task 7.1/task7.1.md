# Task 7.1 — Shared message schema + normalizer

## Steps

- [x] Define common message fields: `channel`, `ts`, `user`, `text`, `thread_ts`, `source_format`
- [x] Enum / literals for `source_format` (export, json, ndjson, csv, xlsx, web_api)
- [x] Normalizer: raw Slack-shaped dict (+ optional channel override) → shared model or skip
- [x] Skip empty / non-message noise; keep thread parent linkage via `thread_ts`
- [x] Light unit tests for happy path + skips

## Acceptance criteria

- [x] One Pydantic (or equivalent) model covers all bootstrap + live sync formats
- [x] Normalizer produces stable common fields from Slack message dicts
- [x] `source_format` is always set by caller / parser
