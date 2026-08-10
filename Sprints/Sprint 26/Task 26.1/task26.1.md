# Task 26.1 — Reply pipeline stages

**Sprint:** 26 — Slack delivery Strategies  
**Label:** `pattern-upgrade:slack-delivery`  
**Source:** `Project-Documents/jira-task.md` · `review.md` §5.4 P2

## Steps

- [x] Read `TechStack/software-developement-patterns.md` (pipeline + Strategy; no over-abstraction)
- [x] Introduce reply context + stages: Gate → Intake → RunAgent → Deliver
- [x] Keep entitlement / `jobs_daily` in Gate; denial posts stay early-return
- [x] Keep attachment intake in Intake
- [x] Keep `run_agent` invoke (and advise enrich) in RunAgent; library paths skip compose
- [x] Leave Deliver as a single stage entry (Strategy map lands in 26.2)
- [x] `process_agent_reply` becomes orchestration only
- [x] Light smoke: existing `tests/slack/test_agent_reply.py` still pass

## Acceptance criteria

- [x] `process_agent_reply` is stage orchestration, not a 260+ line god path
- [x] Gate owns entitlement / jobs budget; RunAgent owns agent invoke
- [x] No product/UX copy changes

## Notes

Stages live in `api/app/slack/reply_pipeline.py`; `agent_reply.process_agent_reply` delegates.
