# Task 39.2 — Keep product contracts

**Source:** `Project-Documents/jira-task.md` · Sprint 39

## Steps

- [x] Registry, rules, ToolStrategy, compose prompts, DeliveryStrategy stay product-side
- [x] Do not leak `StateGraph` / `AIMessage` into Slack delivery or billing
- [x] `run_agent` facade has no `StateGraph` / `HumanMessage` imports
- [x] Docs: `AgentRuntime` + LangGraph as first adapter; no new env key
- [x] `review.md` agent-runtime gap → Implemented

## Acceptance criteria

- [x] Workflow / delivery Strategies unchanged as product contracts
- [x] Slack delivery / billing / reports do not import LangGraph graph types
- [x] Swapping frameworks later touches the runtime adapter, not Slack/billing/workflow modules
