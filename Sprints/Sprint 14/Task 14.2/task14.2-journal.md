# Task 14.2 journal

## Status

`completed`

## Summary

Added Slack mrkdwn formatting that appends a capped `*Sources:*` list from retrieval chunk labels. Hedged answers omit Sources.

## Acceptance criteria checklist

- [x] Grounded replies include source hints when chunks exist
- [x] Hedge replies omit Sources

## Decision log

- Max 5 unique source lines; reuse `chunk["label"]` from agent serialization.
- Plain bullet list (mrkdwn) — no Block Kit in MVP.

## Needs human

None beyond inherited live Slack verify.

## Files changed

- `api/app/slack/formatting.py`
- `tests/slack/test_formatting.py`
- `docs/agent.md`
- `Sprints/Sprint 14/Task 14.2/*`

## Resume notes

Next in batch: **Task 14.3 — Inactive plan / over-budget messaging**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/slack/test_formatting.py -q  → passed
```
