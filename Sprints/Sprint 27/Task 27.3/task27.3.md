# Task 27.3 — `invoke_mcp` client collapse

## Steps

- [x] Add `invoke_mcp(name, arguments, *, deps/settings) -> dict`
- [x] Collapse `draft_*` / `search_knowledge` / `start_onboarding` wrappers onto it
- [x] Prefer in-process FastMCP for API/worker; keep stdio for external / opt-in
- [x] Keep thin typed helpers for call-site clarity; tool strategies unchanged in behavior
- [x] Light smoke: agent MCP / meeting / report tool tests

## Acceptance criteria

- [x] N `*_via_mcp` wrappers replaced with generic invoke (+ thin typed helpers)
- [x] Longer-lived / in-process session preferred for API/worker; stdio for external
- [x] Tool strategies call Adapter; they do not own transport
