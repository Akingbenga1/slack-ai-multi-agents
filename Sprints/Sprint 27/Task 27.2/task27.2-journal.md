# Task 27.2 journal

## Status

`completed`

## Summary

Refactored `create_mcp` to register tools from a `_ToolSpec` table via `FastMCP.add_tool`. Public tool names, descriptions, injectable overrides, and schemas unchanged.

## Acceptance criteria checklist

- [x] `create_mcp` registers from a table; public tool names unchanged
- [x] New grounded draft tool ≈ outline + registry row (with 27.1)

## Decision log

- **Table + thin signature adapters** (not dynamic `**kwargs` tools): FastMCP needs real call signatures for JSON schema; adapters close over injectable handlers, registry is the single place to add a name/description row.
- Kept create_mcp kwargs (`search_fn`, `draft_fn`, …) for test injectability.

## Needs human

(none)

## Files changed

- `mcp_server/server.py`
- `docs/mcp.md`
- `Sprints/Sprint 27/Task 27.2/task27.2.md`

## Resume notes

Next: Task 27.3 — `invoke_mcp` client collapse.

## Open questions

(none)

## Smoke test results

- `tests/mcp` — 21 passed
