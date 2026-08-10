# Task 14.1 journal

## Status

`completed`

## Summary

Wired Slack `@mention` / DM events to LangGraph: install-store token → `run_agent` → `chat.postMessage`. Mentions reply in-thread; DMs top-level. Agent work runs in a FastAPI `BackgroundTask` so Slack gets a fast 200 ack.

## Acceptance criteria checklist

- [x] Mention/DM → LangGraph for install `client_id`
- [x] Install-store token posts in-thread for mentions
- [x] Live path no longer posts `Echo:`

## Decision log

- Background task for agent+post (Slack ~3s ack window; retries still skipped via `X-Slack-Retry-Num`).
- `conversation_id`: `{channel}:{thread_root}` for mentions; DM channel id for DMs.
- Kept `should_echo` as alias of `should_reply`; `post_echo` → `post_message`.

## Needs human

- Live Slack verify (tunnel + Events + OAuth) with knowledge synced — still open from Sprint 4/9.
- Tenant must have **active** plan for a non-denial reply (see 14.3).

## Files changed

- `api/app/slack/echo.py`, `agent_reply.py`, `routes.py`
- `tests/slack/test_echo.py`, `test_agent_reply.py`
- `docs/agent.md`, `docs/slack-app-setup.md`
- `Sprints/Sprint 14/Task 14.1/*`

## Resume notes

Next in batch: **Task 14.2 — Citations / source hints**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/slack/test_echo.py tests/slack/test_agent_reply.py tests/agent -q
→ passed (with 14.2/14.3 tests in same run: 33 total)
```
