# Task 33.1 journal

## Status

`completed`

## Summary

Introduced Strategy adapters + Factory for chat models. Kept `ChatModel.complete` / `StubChatModel` / `AnthropicChatModel`; added `OllamaChatModel` (OpenAI-compatible HTTP). `get_chat_model` selects by `LLM_PROVIDER` — empty Anthropic key no longer auto-selects stub.

## Acceptance criteria checklist

- [x] Compose receives a `ChatModel`; factory chooses adapter by env
- [x] Stub remains for tests / offline without relying solely on empty Anthropic key
- [x] Anthropic + Ollama adapters both implement `complete(..., model_tier=...)`

## Decision log

- **Patterns:** Strategy (`ChatModel`) + Factory (`get_chat_model` / `LLM_PROVIDER`) + Adapter (Anthropic SDK, Ollama HTTP). Stub is a Strategy for tests/offline.
- **Ollama via OpenAI-compatible** `POST {OLLAMA_URL}/v1/chat/completions` so any OpenAI-compatible base URL works without a second adapter.
- **No silent Anthropic→stub fallback** when provider is `anthropic` and key is empty — raises `ValueError` pointing operators to `LLM_PROVIDER=stub`.
- Kept adapters in `api/app/agent/llm.py` (single module) rather than a package split — smell was selection/hardcoding, not file size.

## Needs human

None for this task. Live Anthropic/Ollama still optional (see project progress rollup).

## Files changed

- `api/app/agent/llm.py`
- `tests/agent/test_llm_factory.py` (new)
- `Sprints/Sprint 33/Task 33.1/task33.1.md`

## Resume notes

Done. Continue with Task 33.4 (isolation + remaining test polish) after 33.2/33.3 in this batch.

## Open questions

None.
