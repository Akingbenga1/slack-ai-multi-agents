# Task 16.4 — Notes from recent context

## Steps

- [x] MCP tool `draft_meeting_notes` (tenant + topic → structured notes from RAG / recent context)
- [x] Tools path: for `meeting_notes`, call the new MCP tool
- [x] Compose: deepen notes prompt; pass draft outline via `meeting_draft`
- [x] Light tests + docs

## Acceptance criteria

- [x] Notes asks classify → MCP notes draft → compose polish (Sonnet)
- [x] Hedge when no tenant evidence
- [x] Brief / agenda / non-meeting paths unchanged
