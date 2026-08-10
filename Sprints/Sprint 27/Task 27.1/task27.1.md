# Task 27.1 — `run_grounded_draft` Template Method

## Steps

- [x] Add shared `hit_as_citation` helper (dedupe four copies)
- [x] Extract `run_grounded_draft(client_id, query, outline_fn, …)` — search → citations → hedge → payload
- [x] Strategy = `outline_fn` for brief / agenda / notes / report outline shape
- [x] Refactor `draft.py`, `agenda.py`, `notes.py`, `report.py` to use the template
- [x] Light smoke: existing MCP draft tests still pass

## Acceptance criteria

- [x] Shared search → citations → hedge → payload; Strategy = `outline_fn`
- [x] `_hit_as_citation` deduped; brief/agenda/notes/report refactored
- [x] Public tool names and payload shapes unchanged
