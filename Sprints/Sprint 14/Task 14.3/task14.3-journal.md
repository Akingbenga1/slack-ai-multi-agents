# Task 14.3 journal

## Status

`completed`

## Summary

Slack agent path gates on active plan + `agent` entitlement + token headroom (`require_active_plan=True`). Denials post a clear Slack message and skip LangGraph. `slack_mention` usage is recorded only on successful agent replies.

## Acceptance criteria checklist

- [x] Inactive / no-agent → clear denial, no agent
- [x] Over token budget → clear denial, no agent

## Decision log

- Token pre-check uses `units=1` as “any headroom” gate (exact LLM tokens unknown until compose).
- Distinct copy for `plan_inactive`, agent flag off, `budget_exceeded`, `no_budget`.

## Needs human

- Stripe (or local `apply_plan_state`) so a demo tenant is `plan_status=active` before live Slack Q&A.
- Inherited: Slack app credentials + tunnel + Events verify.

## Files changed

- `api/app/slack/agent_reply.py` (`check_agent_entitlement`, denial messages)
- `tests/slack/test_agent_reply.py`
- `docs/governance.md`, `docs/slack-app-setup.md`, `docs/agent.md`
- `Sprints/Sprint 14/Task 14.3/*`

## Resume notes

Batch 14.1–14.3 done. Next: **Continue Sprint 14 from Task 14.4** (coordination-style prompts).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/slack/test_echo.py tests/slack/test_formatting.py tests/slack/test_agent_reply.py tests/agent -q
→ 33 passed
```
