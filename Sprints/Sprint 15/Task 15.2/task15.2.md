# Task 15.2 — Tools: `search_knowledge` (tenant required)

## Steps

- [x] MCP tool `search_knowledge` wrapping API retrieval
- [x] `client_id` required (fail-closed)
- [x] Optional filters: kind / channel / filename
- [x] JSON-friendly citation payload
- [x] Light tests (in-memory MCP + stub)

## Acceptance criteria

- [x] Tool listed on the stdio server
- [x] Missing `client_id` fails closed
- [x] Successful call returns tenant-scoped hits only
