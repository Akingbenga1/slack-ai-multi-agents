# Task 14.4 — Coordination-style prompts

## Steps

- [x] Dedicated compose prompts for `status` / `summarize` (vs default `qa`)
- [x] Expand route patterns for status / who-said-what / thread summary intents
- [x] Evidence metadata includes Slack `user` / channel / ts for attribution
- [x] Light tests + docs

## Acceptance criteria

- [x] Status / who-said-what / summarize classify to coordination workflows
- [x] Compose uses workflow-specific prompts while remaining RAG-grounded
- [x] Evidence exposes speaker ids so attribution is possible
