# Task 29.1 — Generic `ingest_chunks`

## Steps

- [x] Extract `ingest_chunks(client_id, chunks, *, point_id_fn, payload_fn, …)` with shared TEI batch + Qdrant upsert
- [x] Single-source `DEFAULT_EMBED_BATCH`
- [x] Thin `ingest_messages` wrapper (Slack message Strategy for id/payload)
- [x] Thin `ingest_document_units` wrapper (document Strategy for id/payload)
- [x] Keep public point-id / payload helpers stable for existing tests
- [x] Light unit coverage for shared core (mocked TEI + upsert)

## Acceptance criteria

- [x] TEI batch + upsert lives in one place
- [x] Slack history and document upload differ only by chunking + `point_id_fn` / `payload_fn`
- [x] Existing ingest call sites and point-id tests stay green
