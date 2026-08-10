# Task 25.4 — Tools node Strategy map

**Sprint:** 25 — Agent runtime + Strategy spine  
**Label:** `pattern-upgrade:strategy-spine`  
**Source:** `Project-Documents/jira-task.md` · `review.md` §5.1 P1

## Steps

- [x] Add `ToolStrategy` protocol + concrete strategies under `workflows/tool_strategies.py`
- [x] Map `workflow → ToolStrategy` (meeting / report / onboarding / RAG / attachment-aware)
- [x] Thin `make_tools_node` to dispatch via the map (no growing `if` ladder)
- [x] Quarantine/fold `retrieve` direct path as retrieve Strategy (tests / `AGENT_RETRIEVE_BACKEND=direct`)
- [x] Update registry “how to add a workflow” pointer for tool strategies
- [x] Keep existing agent / MCP tool tests green

## Acceptance criteria

- [x] Adding a tools path = register a `ToolStrategy` (not grow `nodes/tools.py` branches)
- [x] Behavior parity: onboarding / report / meeting / RAG+attachments unchanged
- [x] Direct retrieve path remains available for tests/debug only
- [x] Agent + MCP tool tests pass

## Notes

Sprint 25 exit met: new workflow = registry entry + classifier rule + tool strategy.
