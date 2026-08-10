# Task 16.1 journal

## Status

`completed`

## Summary

Added meeting workflow intents (`meeting_brief`, `meeting_agenda`, `meeting_notes`) to route classification. Meeting phrasing wins over summarize/status; bare “brief overview…” stays `qa`. Meeting workflows escalate to Sonnet. Stub compose prompts/hints so compose is typed for 16.2+.

## Acceptance criteria checklist

- [x] Meeting asks classify to matching workflows
- [x] Meeting workflows → Sonnet via `workflow:*` flags
- [x] Non-meeting classification unchanged
- [x] Ready for 16.2–16.4 generation

## Decision log

- Workflow names: `meeting_brief` / `meeting_agenda` / `meeting_notes` (aligns with MCP `draft_meeting_brief` + TM-10–12).
- Classify order: agenda → notes → brief → summarize → status → qa (agenda/notes more specific than brief cues).
- Avoid bare `\bbrief\b` to prevent “brief overview” false positives.
- Stub prompts in 16.1; deepen brief/agenda generation in 16.2–16.3.

## Needs human

None new (inherited Slack / Stripe / optional Anthropic).

## Files changed

- `api/app/agent/state.py`, `nodes/route.py`, `policy.py`, `prompts.py`
- `tests/agent/test_meeting_route.py`
- `docs/agent.md`
- `Sprints/Sprint 16/Task 16.1/*`

## Resume notes

Next in batch: **Task 16.2 — Brief generation (may escalate Sonnet)**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/agent/test_meeting_route.py tests/agent/test_prompts.py tests/agent/test_policy.py -q
→ 17 passed
```

## Commercial mapping

TM-10–12 (briefs / agendas / notes) — route step before produce.
