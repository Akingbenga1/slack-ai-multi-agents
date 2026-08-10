# Task 25.3 journal

## Status

`completed`

## Summary

Replaced the monolithic `route.py` regex ladder with ordered `ClassifierRule` Strategies (`RegexRule` / `PredicateRule`) in `workflows/rules.py`. Shared file rename/PDF/advise intents live in `workflows/intents.py`; Slack `file_actions.question_requests_rename` and `agent_reply` use the shared helpers. `route_node` is thin; `classify_workflow` re-exported from `route` for back-compat. Classification tests parametrized over registry examples.

## Acceptance criteria checklist

- [x] Adding a classifier = register a rule (not grow a 200-line `if` chain)
- [x] Existing classification behavior preserved
- [x] Shared intents used by Slack file helpers

## Decision log

- **Chain of Strategy rules** (ordered CoR): matches `review.md` without introducing a separate CoR framework.
- Kept broader `FILE_RENAME_BROAD_RE` for Slack combined-ask rename detection vs specific `FILE_RENAME_RE` for classification — same module, two intentional widths (prior behavior).

## Needs human

(none)

## Files changed

- `api/app/agent/nodes/route.py` (thinned)
- `api/app/agent/workflows/rules.py`
- `api/app/agent/workflows/intents.py`
- `api/app/slack/file_actions.py`
- `api/app/slack/agent_reply.py`
- `tests/agent/test_workflows_registry.py`
- `Sprints/Sprint 25/Task 25.3/task25.3.md`

## Smoke test results

- `tests/agent/` + `tests/slack/test_agent_reply.py` + `tests/workflows/`: **116 passed**

## Resume notes

**Next batch:** Task **25.4** — Tools node Strategy map (`workflow → ToolStrategy`). Sprint 25 exit still needs 25.4.

Resume prompt: `Continue Sprint 25 from Task 25.4`

## Open questions

(none)
