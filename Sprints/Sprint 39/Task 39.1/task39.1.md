# Task 39.1 — `AgentRuntime` adapter

**Source:** `Project-Documents/jira-task.md` · `review.md` architecture gap — agent-runtime

## Steps

- [x] Define `AgentRuntime` Adapter contract: `run` / `run_report` (thread-scoped product API)
- [x] Implement `LangGraphAgentRuntime` (owns `StateGraph` + checkpointer invoke)
- [x] `run_agent` / `run_report` remain product facades → `default_agent_runtime()`
- [x] LangGraph is the first implementation; no Factory / `AGENT_RUNTIME` env
- [x] Keep `AGENT_CHECKPOINTER` as the existing small saver factory (not a vendor Strategy)
- [x] Light smoke: default runtime name + facade delegates to runtime

## Acceptance criteria

- [x] Product invoke talks to `AgentRuntime`; LangGraph is the first adapter
- [x] StateGraph + checkpointer invoke live in the adapter
- [x] No `AGENT_RUNTIME` env this sprint (single runtime)
