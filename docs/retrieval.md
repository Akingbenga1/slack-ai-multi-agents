# Knowledge retrieval (Sprint 10 / 35)

`search_knowledge` embeds a query via ``EmbeddingProvider`` and retrieves top-k chunks from ``VectorStore`` with a **mandatory** `client_id` filter (fail-closed). Demo default adapters are TEI + Qdrant (`EMBEDDING_PROVIDER=tei`, `VECTOR_STORE=qdrant`). Hits include citation metadata for grounded agent replies and the bundled MCP tool of the same name (`docs/mcp.md`).

## API

```python
from api.app.retrieval import search_knowledge, KnowledgeSearchFilters

result = search_knowledge(
    client_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    query="onboarding checklist",
    limit=8,  # top-k
    filters=KnowledgeSearchFilters(kind="slack_message"),  # optional
)

for hit in result.hits:
    print(hit.score, hit.short_label(), hit.text[:80])
    # Slack: channel / ts / user
    # Document: filename / locator / title
```

### Filters (optional, AND'd with tenant)

| Field | Matches payload |
| ----- | --------------- |
| `kind` | `slack_message` or `document` |
| `channel` | Slack channel id |
| `filename` | Document filename |

Missing / empty `client_id` raises `TenantFilterRequired` (fail-closed on every adapter).

## Modules

- `api/app/retrieval/search.py` — `search_knowledge` (calls `EmbeddingProvider` + `VectorStore`)
- `api/app/retrieval/types.py` — `KnowledgeCitation`, `KnowledgeSearchFilters`, `KnowledgeSearchResult`
- `api/app/retrieval/citations.py` — `VectorHit` payload → citation mapping
- `api/app/vector_store/` — Strategy + Factory (`VECTOR_STORE`); Qdrant is the first adapter
- `api/app/embedding/` — Strategy + Factory (`EMBEDDING_PROVIDER`); TEI is the first adapter
- Adapter helpers: `api/app/qdrant/`, `api/app/tei/` — see `docs/qdrant-tei.md`

## Isolation tests (CI-friendly)

In-memory Qdrant adapter + stub embeddings (no Compose required):

```bash
uv run pytest tests/retrieval -q
```

Asserts tenant A query never returns tenant B points; missing `client_id` fail-closed; ingest/retrieve modules do not name Qdrant/TEI.

## Corpus smoke (Compose Qdrant + TEI)

Fixtures: `tests/fixtures/knowledge/sample_slack.json`, `sample_doc.csv`.

| Query | Expected citation |
| ----- | ----------------- |
| `onboarding checklist for new hires` | Slack `C_KNOWLEDGE` — onboarding checklist |
| `refund policy within 30 days` | Document `sample_doc.csv` — refund |
| `Qdrant tenant isolation` | Slack `C_KNOWLEDGE` — tenant isolation |

```bash
uv run python scripts/search_knowledge_smoke.py
```

Expect `search_knowledge_smoke_ok` and `citation_ok` lines per query.
