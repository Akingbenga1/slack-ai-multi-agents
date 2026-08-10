# Task 27.4 journal

## Status

`completed`

## Summary

Parametrized MCP grounded-draft success + hedge tests and agent tools-node → MCP draft regression over brief / agenda / notes / report. Confirms Template Method + registry row + `invoke_mcp` Adapter stay green. Sprint 27 exit met.

## Acceptance criteria checklist

- [x] Draft-tool tests parametrized (not four copy-pasted bodies)
- [x] Agent tools node still green for meeting/report MCP drafts
- [x] Sprint 27 exit: new grounded draft tool ≈ outline + registry row; transport is one Adapter

## Decision log

- **Parametrize over local tables** (`_GROUNDED_DRAFT_OK` / `_AGENT_DRAFT_CASES`) rather than importing private `create_mcp` registry: tests document the public contract; adding a tool = outline + server registry row + one test row (matches `review.md` §5.2 / §5.10).
- Kept per-workflow prompt/compose tests in `test_meeting_*.py` / `test_report.py`; parametrized suite covers the shared tools → MCP Adapter path only.

## Needs human

(none)

## Files changed

- `tests/mcp/test_server.py`
- `tests/agent/test_mcp_tools.py`
- `Sprints/Sprint 27/Task 27.4/task27.4.md`

## Resume notes

Sprint 27 complete. Next: **Continue Sprint 28 from Task 28.1** (shared `ScheduleStore` on `AgentConfig.schedules`).

## Open questions

(none)

## Smoke test results

- `tests/mcp` + agent MCP/meeting/report/registry — 70 passed
