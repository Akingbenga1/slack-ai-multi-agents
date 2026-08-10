# Task 27.1 journal

## Status

`completed`

## Summary

Extracted `run_grounded_draft` Template Method + shared `hit_as_citation` / `excerpt` into `mcp_server/tools/grounded.py`. Brief, agenda, notes, and report tools now supply only an `outline_fn` Strategy; search → citations → hedge → payload is shared. Payload shapes and public tool names unchanged.

## Acceptance criteria checklist

- [x] Shared search → citations → hedge → payload; Strategy = `outline_fn`
- [x] `_hit_as_citation` deduped; brief/agenda/notes/report refactored
- [x] Public tool names and payload shapes unchanged

## Decision log

- **Template Method + Strategy (not inheritance hierarchy):** function-level template with injectable `outline_fn` matches existing functional MCP tools and avoids AbstractClass boilerplate (`software-developement-patterns.md` / Template Method + Strategy note).
- **`prefer_kind` hook** on the template preserves notes/report Slack-first then widen behavior without duplicating search loops.
- Outline Strategy returns a mapping merged into the payload (sections *or* items) so agenda stays item-shaped.

## Needs human

(none)

## Files changed

- `mcp_server/tools/grounded.py` (new)
- `mcp_server/tools/draft.py`
- `mcp_server/tools/agenda.py`
- `mcp_server/tools/notes.py`
- `mcp_server/tools/report.py`
- `Sprints/Sprint 27/Task 27.1/task27.1.md`

## Resume notes

Next: Task 27.2 — table-driven `create_mcp` registration.

## Open questions

(none)

## Smoke test results

- `tests/mcp` + meeting brief/agenda/notes + report — 38 passed
