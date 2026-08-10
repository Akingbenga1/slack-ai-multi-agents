# Task 25.1 journal

## Status

`completed`

## Summary

Introduced `AgentRuntimeDeps` + `build_agent_deps` Factory merge helper. `build_agent_graph`, `build_report_graph`, `run_agent`, and `run_report` take an optional `deps` bag; kwargs remain for back-compat. Behavior unchanged.

## Acceptance criteria checklist

- [x] One deps object can drive graph + run without repeating injectables
- [x] Behavior identical for Slack / dry-run / scripts (kwargs still work)
- [x] No new product features

## Decision log

- **Factory (not Abstract Factory):** single deps dataclass + merge helper is enough; no product families yet (`software-developement-patterns.md`).
- Kept kwargs alongside `deps=` so existing tests/scripts do not need a big-bang rewrite; preferred path documented on signatures.

## Needs human

(none)

## Files changed

- `api/app/agent/deps.py` (new)
- `api/app/agent/graph.py`
- `api/app/agent/run.py`
- `api/app/agent/__init__.py`
- `tests/agent/test_deps.py` (new)
- `Sprints/Sprint 25/Task 25.1/task25.1.md`

## Resume notes

Task done. Next in batch was 25.2 (registry) — also completed this session.

## Open questions

(none)
