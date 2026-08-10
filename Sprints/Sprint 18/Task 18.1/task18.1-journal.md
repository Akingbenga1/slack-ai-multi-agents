# Task 18.1 journal

## Status

`completed`

## Summary

Added MCP `start_onboarding` stub and LangGraph `onboarding` workflow. Explicit start/process phrasing returns a clear “not configured” message (no RAG, no LLM, no invented checklist). Knowledge asks about onboarding content stay `qa`.

## Acceptance criteria checklist

- [x] Explicit start → `onboarding`
- [x] Clear “not configured” via MCP / graph
- [x] No fabricated process
- [x] Ready for 18.2 docs

## Decision log

- Workflow name: `onboarding`; MCP tool: `start_onboarding` (matches jira-task.md).
- Classify only explicit cues (`start/begin/kick off/run` + onboarding, or `onboarding process/workflow`) so “onboarding checklist for new hires” stays RAG `qa`.
- Compose short-circuits before hedge — stub must not look like a retrieval miss.
- Do not escalate to Sonnet (`workflow:onboarding` not in `_ESCALATE_WORKFLOWS`).

## Needs human

Live Slack/MCP verify of stub reply still needed for Sprint 18 exit (optional if unit path accepted; prefer one Slack mention of “start onboarding”).

## Files changed

- `mcp_server/tools/onboarding.py`, `mcp_server/server.py`
- `api/app/agent/mcp_client.py`, `state.py`, `nodes/route.py`, `nodes/tools.py`, `nodes/compose.py`, `prompts.py`
- `tests/mcp/test_server.py`, `tests/agent/test_onboarding.py`
- `docs/mcp.md`, `docs/agent.md`
- `Sprints/Sprint 18/Task 18.1/*`

## Resume notes

Next in batch: **Task 18.2 — Document extension point for future checklist state machine**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/mcp/test_server.py tests/agent/test_onboarding.py tests/agent/test_meeting_route.py tests/agent/test_report.py -q
→ 33 passed
```

## Commercial mapping

PO-15 / TM-16 — onboarding process stub (honest deferral).
