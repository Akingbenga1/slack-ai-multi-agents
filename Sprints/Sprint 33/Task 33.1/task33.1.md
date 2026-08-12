# Task 33.1 — Adapters + factory

## Steps

- [x] Keep `ChatModel.complete` protocol + `LlmResult`
- [x] Keep `StubChatModel` as offline / test Strategy
- [x] Keep Anthropic adapter (`AnthropicChatModel`); map tiers inside adapter
- [x] Add Ollama / OpenAI-compatible HTTP adapter (`OllamaChatModel`)
- [x] Factory `get_chat_model` selects by `LLM_PROVIDER=anthropic|ollama|stub`
- [x] Empty `ANTHROPIC_API_KEY` is no longer the only offline path (use `LLM_PROVIDER=stub`)
- [x] Light smoke: stub factory + Anthropic requires key when selected

## Acceptance criteria

- [x] Compose receives a `ChatModel`; factory chooses adapter by env
- [x] Stub remains for tests / offline without relying solely on empty Anthropic key
- [x] Anthropic + Ollama adapters both implement `complete(..., model_tier=...)`
