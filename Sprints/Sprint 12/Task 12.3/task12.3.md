# Task 12.3 — Usage event recording

## Steps

- [x] `record_usage` helper → `usage_events`
- [x] Wire Slack mention/DM echo → `slack_mention`
- [x] Wire Celery success paths → `job` / `sync_run` / `ingest`
- [x] Canonical event types + token type stub for agent sprint
- [x] Light tests + docs

## Acceptance criteria

- [x] Mentions, sync runs, jobs, ingest leave durable usage rows
- [x] Token events can be recorded (`llm_tokens`) for later agent budget
- [x] Events feed budget sums (12.2) and summary API (12.4)
