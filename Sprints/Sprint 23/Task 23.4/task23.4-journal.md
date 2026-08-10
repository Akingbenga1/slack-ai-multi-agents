# Task 23.4 journal

## Status

`completed`

## Summary

Implemented Slack file rename: org-stored copy rename is primary (fail-closed tenant paths); best-effort Slack `files.edit` title update; MCP `rename_slack_file`; wired into `file_rename` and J10 combined PDF+rename asks with TM-23 confirmation copy and `file_rename` usage events.

## Acceptance criteria checklist

- [x] Clear success/failure message
- [x] Org copy renamed when present
- [x] Slack title best-effort + docs on API limits
- [x] Scopes / reinstall documented (Needs human)
- [x] J10 PDF+rename also renames

## Decision log

- Slack has no reliable filename rename API → primary path is tenant upload rename; `files.edit` only updates title
- MCP tool mirrors in-process helper; agent path uses in-process (same as PDF)
- Combined J10 asks: after PDF export, also rename when question contains rename intent

## Needs human

- Reinstall Slack app so bot token includes `files:write` (for `files.edit` title updates) — same as PDF upload reinstall in 23.3

## Files changed

- `api/app/slack/file_actions.py` (rename helpers + messages)
- `api/app/slack/client.py` (`files_edit`)
- `api/app/slack/agent_reply.py`
- `mcp_server/tools/rename.py`, `mcp_server/server.py`
- `tests/slack/test_file_rename.py`
- `tests/mcp/test_server.py`
- `docs/slack-file-actions.md`, `docs/agent.md`, `docs/mcp.md`, `docs/slack-app-setup.md`, `docs/slack-web-api.md`, `README.md`

## Resume notes

Continue with Task 23.5 in the same batch (isolation / usage / J10 smoke).

## Open questions

- None for offline path; live Slack title edit depends on workspace + scopes.
