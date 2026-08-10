# Task 7.5 — Chunk → TEI → Qdrant pipeline

## Steps

- [x] Chunk normalized messages into embeddable text units
- [x] Embed chunks via TEI; upsert to Qdrant with tenant `client_id`
- [x] Idempotent point ids by channel+ts (+ chunk index) / content hash
- [x] CLI (or thin API job) to ingest a sample dump for one tenant
- [x] Light smoke: upsert + tenant-scoped search returns the sample

## Acceptance criteria

- [x] Sample dump → searchable in Qdrant for that tenant only
- [x] Re-running ingest does not duplicate points (idempotent ids)
- [x] Missing `client_id` rejected by existing fail-closed helpers
