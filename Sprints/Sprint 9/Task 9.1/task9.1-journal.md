# Task 9.1 journal

## Status

`completed`

## Summary

Added `SlackWebClient` for `conversations.list` / `conversations.history` with cursor pagination and Slack rate-limit retries (`Retry-After` / `ratelimited`). Factory helpers load the Fernet-encrypted bot token from the install store by `team_id` or `tenant_id`. OAuth bot scopes expanded for channel/group history (existing workspaces need reinstall).

## Acceptance criteria checklist

- [x] Client + install-store token — done (`slack_client_for_team` / `slack_client_for_tenant`)
- [x] Rate-limit wait/retry — done (`max_retries`, `SlackRateLimitError`)
- [x] Cursor pagination — done
- [x] Ready for watermarks / Celery — done

## Decision log

- Raw httpx (same as echo/OAuth), not slack-bolt WebClient — keeps deps light and matches TEI client pattern.
- GET for list/history; bool params as `"true"`/`"false"` query strings.
- MVP: one install per tenant via `order_by(installed_at.desc()).limit(1)`.
- `users:read` included with history scopes for later display-name resolution.

## Needs human

- Reinstall Slack app after adding scopes in api.slack.com UI (same as open Sprint 4 tunnel/OAuth verify).
- Live API smoke against a real workspace still blocked on those credentials.

## Files changed

- `api/app/slack/client.py` (new)
- `api/app/slack/store.py` (`get_install_by_tenant`)
- `api/app/slack/routes.py` (`BOT_SCOPES`)
- `api/app/slack/__init__.py`
- `tests/slack/test_client.py`
- `docs/slack-web-api.md`, `docs/slack-app-setup.md`, `docs/slack-history-ingest.md`, `README.md`
- `Sprints/Sprint 9/Task 9.1/*`

## Resume notes

Next: **Task 9.2 — Watermarks in Postgres** (per-channel `oldest`/`latest` cursor).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/slack -q  →  5 passed
```
