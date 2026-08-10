# Task 25.4 journal

## Status

`completed`

## Summary

Replaced the monolithic tools-node `if` ladder with a `workflow → ToolStrategy` map in `workflows/tool_strategies.py`. `make_tools_node` resolves inject/direct/MCP once via `resolve_tools_context`, then dispatches. Meeting/report/onboarding/RAG (+ attachment-primary file workflows) share one interface. `make_retrieve_node` is quarantined behind `DirectRetrieveStrategy` for tests/debug only.

## Acceptance criteria checklist

- [x] Adding a tools path = register a `ToolStrategy`
- [x] Behavior parity preserved
- [x] Direct retrieve path for tests/debug only
- [x] Agent + MCP tool tests green

## Decision log

- **Strategy map (not State):** one `ToolStrategy.run(state, ToolsContext)` per workflow; meeting/report fall through to RAG when `search` is injected (prior test behavior).
- **`ToolsContext` instead of full `AgentRuntimeDeps`:** tools need the *resolved* search backend (`inject` / `direct` / `mcp`), which deps alone does not encode.
- **`DirectRetrieveStrategy`:** keeps standalone retrieve node without duplicating tenant filter / hedge logic in `retrieve.py`.

## Needs human

(none)

## Files changed

- `api/app/agent/workflows/tool_strategies.py` (new)
- `api/app/agent/workflows/__init__.py`
- `api/app/agent/workflows/registry.py` (how-to-add pointer)
- `api/app/agent/nodes/tools.py` (thinned)
- `api/app/agent/nodes/retrieve.py` (quarantined wrapper)
- `tests/agent/test_workflows_registry.py`
- `Sprints/Sprint 25/Task 25.4/task25.4.md`

## Smoke test results

- `tests/agent/` + `tests/slack/test_agent_reply.py` + `tests/workflows/`: **118 passed**

## Resume notes

**Sprint 25 complete.** Next sprint: Task **26.1** — Slack delivery Strategies (`process_agent_reply` Gate → Intake → RunAgent → Deliver).

Resume prompt: `Continue Sprint 26 from Task 26.1`

## Open questions

(none)
