# Task 6.2 — TEI HTTP client

## Steps

- [x] Add `embedding_model_id` (and related) to settings
- [x] Implement HTTP client: `POST /embed` against `TEI_URL`
- [x] Return float vectors for one or many texts (truncate on)

## Acceptance criteria

- [x] Settings expose configured model id
- [x] Client embeds text(s) via Compose TEI
- [x] Vector length matches configured embedding dim
