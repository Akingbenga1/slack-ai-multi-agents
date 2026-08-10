# Task 16.1 — Intent routing for meeting asks

## Steps

- [x] Extend `WorkflowName` with meeting workflows (`meeting_brief`, `meeting_agenda`, `meeting_notes`)
- [x] Classify meeting phrasing in `route` (before generic qa; ordered vs summarize/status)
- [x] Escalate meeting workflows to Sonnet via complexity policy
- [x] Stub compose prompts / user hints so classified meeting asks don't fall through to qa silently
- [x] Light unit tests + docs pointer

## Acceptance criteria

- [x] “Brief me for…”, agenda, and meeting-notes asks classify to the matching meeting workflow
- [x] Meeting workflows set `workflow:*` complexity flags → Sonnet tier
- [x] Non-meeting Q&A / status / summarize classification unchanged
- [x] Ready for 16.2–16.4 compose / generation to key off `workflow`
