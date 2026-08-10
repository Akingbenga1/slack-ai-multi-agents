# Task 26.4 — Slack smoke / regression

**Sprint:** 26 — Slack delivery Strategies *(pattern upgrade)*  
**Label:** `pattern-upgrade:slack-delivery`  
**Source:** `Project-Documents/jira-task.md` · `review.md` §5.4 P2

## Steps

- [x] Confirm DeliveryStrategy map resolves default / PDF / rename / library / advise
- [x] Offline smoke: mention/DM grounded reply via `process_agent_reply` (DefaultPost)
- [x] Offline smoke: PDF (+ optional rename) and rename-only delivery paths
- [x] Offline smoke: workflow-library confirm path (list/store) without agent compose
- [x] Regression: existing `tests/slack/` + delivery-related agent/workflow tests still pass
- [x] Light assert: files facade + store client factories still importable

## Acceptance criteria

- [x] Mention/DM grounded reply, file PDF/rename, library confirm paths still pass existing tests
- [x] Sprint exit: Slack deliverables are swappable strategies; `agent_reply` is orchestration only

## Notes

Live Slack verify remains Needs-human (prior scope reinstall). This task is offline regression only.
