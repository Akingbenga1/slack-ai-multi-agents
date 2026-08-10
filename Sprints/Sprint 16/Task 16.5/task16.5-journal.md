# Task 16.5 journal

## Status

`completed`

## Summary

Extended Slack reply formatting: `markdown_to_mrkdwn` converts ATX headings, `**bold**`/`__bold__`, and `-`/`*` bullets to Slack mrkdwn. Applied in `format_slack_reply` for non-hedged answers so meeting briefs/agendas/notes (and any Markdown-ish compose output) render as scannable Slack text with Sources intact.

## Acceptance criteria checklist

- [x] Structured mrkdwn for meeting-style answers
- [x] Hedge path skips conversion + Sources
- [x] Sources footer unchanged when grounded

## Decision log

- Post-compose normalisation in `formatting.py` rather than prompting alone (LLM may still emit `#` / `-`).
- Hedge returns raw body (no polish) so fixed hedge copy stays plain.
- Shared for all workflows (not meeting-only) — harmless for plain Q&A.

## Needs human

None new (inherited Slack live verify still needed to confirm end-to-end meeting asks in Slack).

## Files changed

- `api/app/slack/formatting.py`
- `tests/slack/test_formatting.py`
- `docs/agent.md`
- `Sprints/Sprint 16/Task 16.5/*`

## Resume notes

Sprint 16 complete. Next: **Continue Sprint 17 from Task 17.1**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/slack/test_formatting.py tests/slack/test_agent_reply.py tests/agent/test_meeting_*.py -q
→ 29 passed
```
