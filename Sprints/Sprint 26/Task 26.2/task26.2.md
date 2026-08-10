# Task 26.2 — Delivery Strategy map

**Sprint:** 26 — Slack delivery Strategies  
**Label:** `pattern-upgrade:slack-delivery`  
**Source:** `Project-Documents/jira-task.md` · `review.md` §5.4 P2

## Steps

- [x] Read patterns guidance (Strategy for swappable Slack side effects)
- [x] Introduce `DeliveryStrategy` protocol + `DeliveryContext`
- [x] Implement Strategies: default post, PDF upload, rename, library confirm, advise
- [x] Key by workflow / `WorkflowMeta.delivery_hint`; register in `DELIVERY_STRATEGIES`
- [x] Wire Deliver stage to `get_delivery_strategy`
- [x] Light smoke: Slack suite still green

## Acceptance criteria

- [x] PDF / rename / library confirmations are replaceable Strategies
- [x] No god-function branches for file I/O inside `process_agent_reply`
- [x] UX copy/behavior unchanged

## Notes

`AdviseDeliveryStrategy` covers early no-evidence posts + default compose post.
