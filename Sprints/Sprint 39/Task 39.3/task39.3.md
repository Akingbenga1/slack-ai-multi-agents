# Task 39.3 — Tests

**Source:** `Project-Documents/jira-task.md` · Sprint 39 exit

## Steps

- [x] Dry-run, Slack mention/DM, meeting/report paths still pass
- [x] Checkpointer memory vs postgres setting still works (`AGENT_CHECKPOINTER` unchanged)
- [x] No new env key this sprint (`AGENT_RUNTIME` only if a second runtime later)
- [x] Isolation: Slack/billing/reports free of `StateGraph` / `AIMessage`; adapter owns StateGraph
- [x] Sprint 39 exit: swapping agent framework later touches the runtime adapter, not Slack/billing/workflow modules

## Acceptance criteria

- [x] Dry-run, Slack mention/DM, meeting/report paths still pass
- [x] `AGENT_CHECKPOINTER` memory|postgres still works; not re-abstracted as a vendor Strategy
- [x] Sprint 39 exit met: new agent framework = new adapter; product contracts unchanged
