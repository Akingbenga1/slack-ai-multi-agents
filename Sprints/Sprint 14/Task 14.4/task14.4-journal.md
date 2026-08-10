# Task 14.4 journal

## Status

`completed`

## Summary

Coordination asks (status, who-said-what, thread summarize) still use RAG retrieve → compose, but compose now picks workflow-specific system/user prompts. Route patterns cover more coordination phrasing; evidence blocks include Slack `user=` so attribution is possible.

## Acceptance criteria checklist

- [x] Status / who-said-what / summarize classify to coordination workflows
- [x] Compose uses workflow-specific prompts (RAG-grounded)
- [x] Evidence exposes speaker ids for attribution

## Decision log

- Kept workflows as `qa` | `status` | `summarize` (who-said-what maps to `status`).
- Prompts live in `api/app/agent/prompts.py`; compose falls back to fixed `system_prompt=` only when injected (tests).
- Summarize wins over status when both keywords appear (existing order).

## Needs human

- Inherited: Slack live Events/OAuth + active plan + synced corpus for live coordination Q&A.
- Optional: `ANTHROPIC_API_KEY` for non-stub compose.

## Files changed

- `api/app/agent/prompts.py` (new)
- `api/app/agent/nodes/compose.py`, `nodes/route.py`, `chunks.py`
- `tests/agent/test_prompts.py`, `tests/agent/test_policy.py`
- `docs/agent.md`, `docs/slack-app-setup.md`
- `Sprints/Sprint 14/Task 14.4/*`

## Resume notes

Sprint 14 complete. Next: **Continue Sprint 15 from Task 15.1** (MCP server process / stdio).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/agent tests/slack/test_echo.py tests/slack/test_formatting.py tests/slack/test_agent_reply.py -q
→ 39 passed
```
