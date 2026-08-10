# Task 25.2 journal

## Status

`completed`

## Summary

Added `api/app/agent/workflows/` with `WorkflowMeta` registry covering every `WorkflowName` (incl. file + library). Helpers: `get_workflow_meta`, `list_workflow_names`, `iter_workflow_meta`. Module docstring documents how to add a workflow (pointer for Sprint 30 docs).

## Acceptance criteria checklist

- [x] Every workflow name from `state.WorkflowName` is registered
- [x] New workflow registration site is under `workflows/`
- [x] No behavior change from registry alone (classify wired in 25.3)

## Decision log

- **Strategy metadata first:** registry holds name / prompt_key / escalate / delivery_hint so Sprint 26 delivery Strategies can key off `delivery_hint` without inventing a second map.
- Tool Strategy map deferred to Task 25.4 (planned).

## Needs human

(none)

## Files changed

- `api/app/agent/workflows/__init__.py`
- `api/app/agent/workflows/registry.py`
- `api/app/agent/workflows/intents.py` (shared with 25.3)
- `api/app/agent/workflows/rules.py` (shared with 25.3)
- `tests/agent/test_workflows_registry.py`
- `Sprints/Sprint 25/Task 25.2/task25.2.md`

## Resume notes

Task done. Classifier rules (25.3) consume this registry’s naming; tools map is 25.4.

## Open questions

(none)
