# Task 33.2 — Settings

## Steps

- [x] Add `LLM_PROVIDER=anthropic|ollama|stub` (demo default `anthropic`)
- [x] Add Ollama adapter settings: `OLLAMA_URL` + fast/capable model tags
- [x] Keep `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL_HAIKU`, `ANTHROPIC_MODEL_SONNET`, `ANTHROPIC_MAX_TOKENS` as Anthropic-adapter secrets (do not rename)
- [x] Offline path is `LLM_PROVIDER=stub` (not empty Anthropic key)
- [x] Update `.env.example`: selector + note that existing vendor keys stay as adapter secrets

## Acceptance criteria

- [x] Settings expose `llm_provider` and Ollama URL/model tags
- [x] Anthropic env names unchanged
- [x] `.env.example` documents the selector and adapter secrets
