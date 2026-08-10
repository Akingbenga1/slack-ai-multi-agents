# Task 2.1 — Global settings

## Steps

- [x] Add Pydantic Settings module for API/worker shared config
- [x] Fields: DATABASE_URL, Redis, Qdrant, TEI, Slack, Stripe, JWT, PUBLIC_BASE_URL (+ Anthropic)
- [x] Expand `.env.example` with placeholders (empty secrets OK)
- [x] Wire settings import from FastAPI app (smoke import)

## Acceptance criteria

- [x] `Settings` loads from env / `.env`
- [x] All required keys from jira-task / stack doc are present
- [x] `.env.example` documents the keys
