# Task 13.1 — Graph state & nodes

## Steps

- [x] `AgentState`: `client_id`, messages, retrieved_chunks, workflow, model_tier
- [x] Nodes: `route` → `retrieve` → `compose`
- [x] Wire `search_knowledge` in retrieve (mandatory tenant filter)
- [x] Compose via Anthropic (stub when no API key) using retrieved evidence
- [x] Compile graph helper + dry-run invoke entrypoint
- [x] Light unit tests + docs

## Acceptance criteria

- [x] State carries tenant + RAG fields end-to-end
- [x] Graph path is route → retrieve → compose
- [x] Offline dry-run works with stub LLM (no Slack post)
