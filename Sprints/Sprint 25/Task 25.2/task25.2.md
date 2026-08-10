# Task 25.2 — Workflow registry package

**Sprint:** 25 — Agent runtime + Strategy spine  
**Label:** `pattern-upgrade:strategy-spine`  
**Source:** `Project-Documents/jira-task.md` · `review.md` §5.1 P1

## Steps

- [x] Add `api/app/agent/workflows/` package
- [x] `registry.py` — `WorkflowMeta` + ordered registry for all `WorkflowName` values (incl. file + library)
- [x] Metadata: name, description, delivery_hint, escalate flag, prompt key
- [x] Helpers: `get_workflow_meta`, `list_workflow_names`, `iter_workflow_meta`
- [x] Document “how to add a workflow” pointer (module docstring → Sprint 30 docs)

## Acceptance criteria

- [x] Every workflow name from `state.WorkflowName` is registered
- [x] New workflow registration site is under `workflows/` (not scattered)
- [x] No behavior change yet (classify/tools still use existing nodes until 25.3/25.4)

## Notes

Tool Strategy map is Task 25.4; classifier rules are Task 25.3.
