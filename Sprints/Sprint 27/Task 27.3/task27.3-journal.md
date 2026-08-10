# Task 27.3 journal

## Status

`completed`

## Summary

Collapsed MCP client into one `invoke_mcp` Adapter. Typed `*_via_mcp` helpers now build args and call `invoke_mcp`. Default transport is cached in-process FastMCP (`AGENT_MCP_TRANSPORT=in_process`); `stdio` remains for external/Inspector. `tool_result_payload` accepts in-process `(content, structured)` tuples.

## Acceptance criteria checklist

- [x] N `*_via_mcp` wrappers replaced with generic invoke (+ thin typed helpers)
- [x] Longer-lived / in-process session preferred for API/worker; stdio for external
- [x] Tool strategies call Adapter; they do not own transport

## Decision log

- **Adapter/Facade, not MCP Strategy hierarchy** (`review.md` §5.3 / patterns doc): one transport Adapter; agent-layer ToolStrategy stays separate.
- **Default `in_process`:** process-local cached `create_mcp()` avoids stdio spawn-per-call; external clients still use `python -m mcp_server` stdio.
- Kept thin typed helpers so `tool_strategies` / `SearchFn` call sites stay readable without a big-bang rewrite.

## Needs human

(none)

## Files changed

- `api/app/agent/mcp_client.py`
- `api/app/settings.py` (`agent_mcp_transport`)
- `docs/mcp.md`
- `tests/agent/test_mcp_tools.py`
- `Sprints/Sprint 27/Task 27.3/task27.3.md`

## Resume notes

Batch 27.1–27.3 done. Next: **Continue Sprint 27 from Task 27.4** (MCP / agent regression tests).

## Open questions

(none)

## Smoke test results

- `tests/mcp` + agent MCP/meeting/report/deps — 44+ passed; `test_invoke_mcp_adapter_inject` added
