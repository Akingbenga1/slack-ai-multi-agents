# Task 26.3 journal

## Status

`completed`

## Summary

Split Slack file helpers into `api/app/slack/files/{refs,intake,pdf,rename}` with a public facade. Legacy `attachments` / `file_actions` re-export. Moved `client_for_tenant` / `client_for_team` onto `store`; `SlackWebClient` stays HTTP-only.

## Acceptance criteria checklist

- [x] File helpers are modular; facade usable by delivery Strategies
- [x] Token/install factory lives in store; client is HTTP Adapter
- [x] Existing import paths still work

## Decision log

- **Facade + shims:** prefer `slack.files` for new code; keep old module paths to avoid churn in MCP/tests.
- **Adapter:** factories on store use lazy import of `SlackWebClient` to avoid client↔store cycles; `client.slack_client_for_*` remain thin wrappers.

## Needs human

(none new — existing Slack scope reinstall / live verify items still in project progress)

## Files changed

- `api/app/slack/files/__init__.py`
- `api/app/slack/files/refs.py`
- `api/app/slack/files/intake.py`
- `api/app/slack/files/pdf.py`
- `api/app/slack/files/rename.py`
- `api/app/slack/attachments.py` (shim)
- `api/app/slack/file_actions.py` (shim)
- `api/app/slack/store.py`
- `api/app/slack/client.py`
- `api/app/slack/sync.py`
- `docs/slack-web-api.md`
- `Sprints/Sprint 26/Task 26.3/task26.3.md`

## Resume notes

Batch 26.1–26.3 done. Next: **Task 26.4** — Slack smoke / regression (mention/DM, PDF/rename, library confirm paths).

## Open questions

(none)

## Smoke test results

- `tests/slack/` — 64 passed
