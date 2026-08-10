# Task 23.1 journal

## Status

`completed`

## Summary

Implemented Slack attachment intake: detect `event.files` + permalink/`file_id` in text, download with bot token, store under tenant upload root, parse via `extract_document`, and pass `attached_evidence` into LangGraph so file analysis is not RAG-only.

## Acceptance criteria checklist

- [x] Mention/DM with supported file → parsed text on agent state
- [x] Empty `client_id` fail-closed
- [x] Per-file failures recorded; no cross-tenant leak
- [x] Attachment evidence avoids hard RAG hedge for file analyse

## Decision log

- Reused `store_upload` + document parsers rather than a separate temp tree
- Attachment chunks shaped like `retrieved_chunks` (`kind=attachment`) so compose/evidence formatting stays unified
- Added `files:read` (and `files:write` for 23.3) to `BOT_SCOPES`

## Needs human

- Reinstall Slack app after adding `files:read` / `files:write` in the Slack UI so live download works (`docs/slack-app-setup.md`, `docs/slack-file-actions.md`)

## Files changed

- `api/app/slack/attachments.py` (new)
- `api/app/slack/client.py` (`files_info`, `download_file`, POST path)
- `api/app/slack/agent_reply.py` (intake wire)
- `api/app/agent/state.py`, `run.py`, `nodes/tools.py`
- `api/app/slack/routes.py` (scopes)
- `tests/slack/test_attachments.py`, `tests/agent/test_file_evidence.py`
- `docs/slack-file-actions.md`, `docs/slack-app-setup.md`, `docs/agent.md`

## Resume notes

Batch continues at Task 23.2 / 23.3 in this session.

## Open questions

- None for intake; live file download blocked on scope reinstall.
