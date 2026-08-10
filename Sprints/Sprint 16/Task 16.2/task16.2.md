# Task 16.2 — Brief generation (may escalate Sonnet)

## Steps

- [x] Tools path: for `meeting_brief`, call MCP `draft_meeting_brief` (plus RAG evidence)
- [x] Compose: deepen brief prompt; use draft outline when present
- [x] Confirm Sonnet escalation for `meeting_brief` (from 16.1 policy)
- [x] Light tests (MCP inject / stub compose) + docs

## Acceptance criteria

- [x] Meeting-brief asks retrieve tenant knowledge and produce a structured brief
- [x] MCP draft helper feeds compose when available; hedge still when no evidence
- [x] `meeting_brief` uses Sonnet tier
- [x] Non-brief workflows unchanged
