# Task 16.3 — Agenda generation

## Steps

- [x] MCP tool `draft_meeting_agenda` (tenant + topic → structured agenda from RAG)
- [x] Tools path: for `meeting_agenda`, call the new MCP tool
- [x] Compose: deepen agenda prompt; pass draft outline via `meeting_draft`
- [x] Light tests + docs

## Acceptance criteria

- [x] Agenda asks classify → MCP agenda draft → compose polish (Sonnet)
- [x] Hedge when no tenant evidence
- [x] Brief / non-meeting paths unchanged
