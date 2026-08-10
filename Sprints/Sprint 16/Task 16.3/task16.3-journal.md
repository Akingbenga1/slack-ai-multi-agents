# Task 16.3 journal

## Status

`completed`

## Summary

Added MCP `draft_meeting_agenda` (numbered items from tenant RAG). Agent tools node calls it for `meeting_agenda`; compose polishes with agenda-specific prompts + `meeting_draft` outline on Sonnet.

## Acceptance criteria checklist

- [x] Agenda path: classify → MCP draft → compose
- [x] Hedge when empty evidence
- [x] Brief / other workflows unchanged

## Decision log

- Parallel tool to `draft_meeting_brief` (`mcp_server/tools/agenda.py`) rather than overloading brief.
- Shared tools-node branch for `meeting_brief` | `meeting_agenda` via `_MEETING_DRAFT_TOOLS`.
- Notes (`meeting_notes`) still RAG-only until 16.4.

## Needs human

None new (inherited Slack / Stripe / optional Anthropic).

## Files changed

- `mcp_server/tools/agenda.py`, `mcp_server/server.py`
- `api/app/agent/mcp_client.py`, `nodes/tools.py`, `prompts.py`
- `tests/agent/test_meeting_agenda.py`, `tests/mcp/test_server.py`
- `docs/mcp.md`, `docs/agent.md`, `README.md`
- `Sprints/Sprint 16/Task 16.3/*`

## Resume notes

Batch 16.1–16.3 done. Next: **Continue Sprint 16 from Task 16.4** (notes from recent context, then 16.5 Slack formatting).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/agent/test_meeting_*.py tests/agent/test_mcp_tools.py tests/mcp -q
→ 24 passed
```
