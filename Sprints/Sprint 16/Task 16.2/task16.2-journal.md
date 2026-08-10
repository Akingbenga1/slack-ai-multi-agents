# Task 16.2 journal

## Status

`completed`

## Summary

`meeting_brief` tools path calls MCP `draft_meeting_brief` (citations + markdown outline). Compose polishes with a deepened brief system prompt; draft is passed as `meeting_draft` in the user prompt. Sonnet escalation from 16.1 confirmed end-to-end.

## Acceptance criteria checklist

- [x] Structured brief from tenant knowledge
- [x] MCP draft → compose; hedge when empty
- [x] Sonnet for `meeting_brief`
- [x] Non-brief path unchanged

## Decision log

- Single MCP call (`draft_meeting_brief`) instead of search + draft (draft already retrieves).
- Injected `search_fn` still uses search-only path (tests); production MCP path uses draft tool.
- `meeting_draft` on agent state + `run_agent` return for compose / callers.

## Needs human

None new (inherited Slack / Stripe / optional Anthropic).

## Files changed

- `api/app/agent/mcp_client.py`, `nodes/tools.py`, `nodes/compose.py`, `prompts.py`, `state.py`, `run.py`
- `tests/agent/test_meeting_brief.py`
- `docs/agent.md`, `docs/mcp.md`
- `Sprints/Sprint 16/Task 16.2/*`

## Resume notes

Next in batch: **Task 16.3 — Agenda generation**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/agent/test_meeting_brief.py tests/agent/test_meeting_route.py tests/agent/test_mcp_tools.py -q
→ 13 passed
```
