# Task 25.1 — `AgentRuntimeDeps` + graph/run injection

**Sprint:** 25 — Agent runtime + Strategy spine  
**Label:** `pattern-upgrade:strategy-spine`  
**Source:** `Project-Documents/jira-task.md` · `review.md` §5.1 P0

## Steps

- [x] Read `TechStack/software-developement-patterns.md` (Factory for deps; no over-abstraction)
- [x] Introduce `AgentRuntimeDeps` dataclass (settings, checkpointer, MCP invoke, search, chat model, db_factory, system_prompt)
- [x] Add `build_agent_deps` merge/factory helper
- [x] Wire `build_agent_graph` / `build_report_graph` to accept deps once (kwargs remain for back-compat)
- [x] Wire `run_agent` / `run_report` to accept deps; resolve defaults inside
- [x] Export deps from `api.app.agent`
- [x] Light smoke: existing agent graph tests still pass via kwargs path



## Acceptance criteria

- [x] One deps object can drive graph + run without repeating injectables
- [x] Behavior identical for Slack / dry-run / scripts (call sites still work with kwargs)
- [x] No new product features



## Notes

Kwargs remain so tests and `scripts/agent_dry_run.py` do not need a big-bang rewrite; preferred path is `deps=AgentRuntimeDeps(...)`.