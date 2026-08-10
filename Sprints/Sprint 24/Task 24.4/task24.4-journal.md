# Task 24.4 journal

## Status

`completed`

## Summary

Added `workflow_advise` routing, attachment/library evidence enrichment for Slack, Sonnet compose prompts that stay grounded when file text exists, and MCP `get_workflow_template` / `advise_workflow` tools (required `client_id`).

## Acceptance criteria checklist

- [x] Advice asks classify to `workflow_advise`
- [x] Guidance uses attached/stored template text when present (not empty hedge)
- [x] Cross-tenant template fetch fail-closed
- [x] MCP tools require `client_id`

## Decision log

- Advice runs full agent compose (unlike store/list/copy short-circuit) so guidance can use LLM + optional RAG
- Library template id in the question fills evidence when no attachment is present
- MCP `advise_workflow` returns a deterministic outline helper; Slack path prefers compose with enriched evidence

## Needs human

- Live Slack verify of advice phrasing after file scopes reinstall

## Files changed

- `api/app/agent/state.py`, `nodes/route.py`, `nodes/tools.py`, `policy.py`, `prompts.py`
- `api/app/workflows/library.py`
- `api/app/slack/workflow_actions.py`, `agent_reply.py`
- `mcp_server/tools/workflow.py`, `mcp_server/server.py`
- `tests/workflows/test_route_and_slack.py`, `tests/mcp/test_server.py`
- `docs/workflow-library.md`, `docs/agent.md`, `docs/mcp.md`

## Resume notes

Continue Task 24.5 (confirmations, portal visibility, J11 smoke).

## Open questions

- None
