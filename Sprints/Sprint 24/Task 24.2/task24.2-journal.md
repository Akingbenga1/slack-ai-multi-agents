# Task 24.2 journal

## Status

`completed`

## Summary

Added `workflow_store` routing, Slack store action reusing attachment intake, idempotent shared persist, clear Slack confirmations, jobs-budget gate (heavy), and `workflow_store` usage events.

## Acceptance criteria checklist

- [x] Store phrasing + attachment → shared template
- [x] Idempotent re-store by hash / file_id
- [x] Success/failure confirmation
- [x] Tenant isolation

## Decision log

- Library workflows short-circuit after intake (no full RAG compose) so confirmations stay deterministic
- `workflow_store` included in `FILE_HEAVY_WORKFLOWS` (jobs budget)

## Needs human

- Same Sprint 23 Slack file scope reinstall for live channel verify

## Files changed

- `api/app/agent/nodes/route.py`, `state.py`, `prompts.py`
- `api/app/slack/workflow_actions.py`, `agent_reply.py`
- `api/app/governance/usage.py`
- `tests/workflows/test_route_and_slack.py`

## Resume notes

Task 24.3 adds list/copy/edit + portal API.

## Open questions

- None
