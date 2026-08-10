# Task 6.1 — Qdrant collection + tenant payload index

## Steps

- [x] Add settings for collection name + embedding vector size (match TEI model)
- [x] Ensure knowledge collection exists (create if missing)
- [x] Create keyword payload index on `client_id`
- [x] Add fail-closed helpers: upsert/search require `client_id` filter (reject missing)

## Acceptance criteria

- [x] Collection exists with `client_id` payload index
- [x] Search/upsert helpers raise when `client_id` is missing (fail closed)
- [x] Helpers always attach tenant filter / payload `client_id`
