# Task 39.1 journal

## Status

`completed`

## Summary

Introduced `AgentRuntime` Protocol + `LangGraphAgentRuntime` Adapter. Product facades `run_agent` / `run_report` call `default_agent_runtime()`; StateGraph compile + HumanMessage invoke live in the adapter. No `AGENT_RUNTIME` env (single runtime).

## Acceptance criteria checklist

- [x] Product invoke talks to `AgentRuntime`; LangGraph is the first adapter
- [x] StateGraph + checkpointer invoke live in the adapter
- [x] No `AGENT_RUNTIME` env this sprint (single runtime)

## Decision log

- **Patterns:** Adapter (`AgentRuntime` / `LangGraphAgentRuntime`). No Strategy/Factory (per review — only when two runtimes are swapped).
- **`graph.py`:** thin re-export of builders for unit tests that compile the graph directly.
- **Facade** accepts optional `runtime=` for tests (mirrors PdfRenderer `renderer=`).

## Needs human

None new.

## Files changed

- `api/app/agent/runtime.py` (new)
- `api/app/agent/langgraph_adapter.py` (new)
- `api/app/agent/run.py` (facade)
- `api/app/agent/graph.py` (re-export)
- `api/app/agent/__init__.py`
- `tests/agent/test_agent_runtime.py` (partial — completed with 39.3)

## Smoke test results

Covered with Task 39.3 suite.

## Resume notes

Continue Task 39.2 — keep product contracts (same batch).

## Open questions

None.
