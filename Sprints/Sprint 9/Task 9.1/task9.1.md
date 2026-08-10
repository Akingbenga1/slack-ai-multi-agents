# Task 9.1 — conversations.list / history client

## Steps

- [x] Add Slack Web API client (`conversations.list`, `conversations.history`)
- [x] Resolve bot token from install store (team_id / tenant_id)
- [x] Respect Slack rate limits (HTTP 429 / `ratelimited` + `Retry-After`, bounded retries)
- [x] Paginate with cursors; yield channels / messages
- [x] Expand OAuth bot scopes for channel read/history (reinstall needed for existing workspaces)
- [x] Light unit tests (pagination, rate-limit retry, API errors)
- [x] Document client usage for live sync

## Acceptance criteria

- [x] Client can list conversations and pull history using the encrypted install-store token
- [x] Rate-limited responses wait / retry instead of failing immediately
- [x] Cursor pagination covers multi-page list and history responses
- [x] Ready for Task 9.2/9.3 watermark + Celery sync wiring
