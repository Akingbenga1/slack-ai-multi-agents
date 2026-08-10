# Task 25.3 — Classifier rules replace route regex ladder

**Sprint:** 25 — Agent runtime + Strategy spine  
**Label:** `pattern-upgrade:strategy-spine`  
**Source:** `Project-Documents/jira-task.md` · `review.md` §5.1 P1

## Steps

- [x] Add rule protocol + ordered rule list in `workflows/rules.py`
- [x] Move regex/predicates out of monolithic `route.py` ladder into registered rules
- [x] Share file rename/PDF (+ advise) intents under `workflows/intents.py`; wire `file_actions` / advice helpers
- [x] Thin `route_node` — call `classify_workflow` from registry rules
- [x] Re-export `classify_workflow` from `route` for back-compat imports
- [x] Parametrize classification tests over the registry (plus keep existing case tests green)

## Acceptance criteria

- [x] Adding a classifier = register a rule (not grow a 200-line `if` chain in `route.py`)
- [x] Existing classification behavior preserved (meeting / file / library / report / qa)
- [x] Shared intents used by Slack file helpers where duplicated

## Notes

Tools Strategy map remains Task 25.4 (next batch).
