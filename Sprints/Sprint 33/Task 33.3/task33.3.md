# Task 33.3 — Generic model tiers

## Steps

- [x] Replace `ModelTier = "haiku" | "sonnet"` with vendor-neutral `fast` / `capable`
- [x] Update `choose_model_tier` / route defaults / run initial state
- [x] Anthropic adapter maps `fast` → Haiku id, `capable` → Sonnet id
- [x] Ollama adapter maps `fast` / `capable` to its own tags
- [x] Usage events record resolved model id from adapter (`result.model`), not Claude nicknames
- [x] Do not add a second Strategy map for Claude nicknames
- [x] Update tests that asserted `haiku` / `sonnet` tier names

## Acceptance criteria

- [x] Graph / policy use only `fast` / `capable`
- [x] Tier → vendor model id mapping lives inside each adapter
- [x] Usage meta keeps resolved `model` id from `LlmResult`
