# Task 15.4 — LangGraph tool node → MCP client

## Steps

- [x] MCP client helper (stdio subprocess → `call_tool`)
- [x] LangGraph tool node invokes `search_knowledge` via MCP (not in-process duplicate)
- [x] Wire agent graph / `run_agent` default path through MCP client
- [x] Setting / docs for MCP command + retrieve backend
- [x] Light tests (injectable MCP call + graph path)

## Acceptance criteria

- [x] Agent path invokes MCP successfully (tool node → client → server tools)
- [x] Tenant `client_id` still required / fail-closed
- [x] Existing dry-run / Slack path still works (tests inject search or use MCP)
- [x] Docs updated (`docs/mcp.md`, `docs/agent.md`)
