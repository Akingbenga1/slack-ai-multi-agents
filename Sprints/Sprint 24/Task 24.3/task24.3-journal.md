# Task 24.3 journal

## Status

`completed`

## Summary

Added Slack list/copy/edit intents, tenant-scoped `/workflows` API, personal draft copy/edit that leaves shared originals immutable, and org portal `/app/workflows` page.

## Acceptance criteria checklist

- [x] Tenant-only list/search
- [x] Copy → personal draft
- [x] Edit copy does not mutate original
- [x] Cross-tenant fail-closed

## Decision log

- Portal copy requires an explicit `owner_slack_user_id` (Slack identity for draft ownership)
- Personal drafts visible in list only when `include_personal_for` matches owner

## Needs human

- Live Slack verify of list/copy phrasing with real workspace users

## Files changed

- `api/app/workflows/routes.py`, `library.py` (list/copy/edit)
- `api/app/slack/workflow_actions.py`, `agent_reply.py`
- `api/app/main.py`
- `web/app/app/workflows/page.tsx`, `web/components/WorkflowsPanel.tsx`, `OrgNav.tsx`, `web/app/app/page.tsx`
- `tests/workflows/test_library.py`, `test_route_and_slack.py`, `test_api.py`
- `docs/workflow-library.md`

## Resume notes

Next batch: **Continue Sprint 24 from Task 24.4** (file-grounded workflow advice + 24.5 confirmations/smoke).

## Open questions

- None
