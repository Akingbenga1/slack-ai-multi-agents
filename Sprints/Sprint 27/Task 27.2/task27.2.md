# Task 27.2 — Table-driven MCP tool registration

## Steps

- [x] Define tool registry table (name → description + handler wiring)
- [x] Refactor `create_mcp` to register via `add_tool` loop
- [x] Keep injectable overrides (`search_fn`, `draft_fn`, …) and public tool names
- [x] Light smoke: `tests/mcp` list_tools + call paths

## Acceptance criteria

- [x] `create_mcp` registers from a table; public tool names unchanged
- [x] New grounded draft tool ≈ outline + registry row (with 27.1)
