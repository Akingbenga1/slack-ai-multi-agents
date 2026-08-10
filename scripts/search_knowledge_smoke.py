"""Sprint 10.3 — smoke search_knowledge on sample Slack + document corpus.

Requires Compose Qdrant + TEI. Ingests fixtures for one tenant, runs documented
queries, and asserts citation cues.

Example:
  uv run python scripts/search_knowledge_smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from api.app.ingest import ingest_extracted_document, ingest_messages
from api.app.ingest.documents import extract_document
from api.app.ingest.parsers import iter_json_messages
from api.app.retrieval import search_knowledge
from api.app.settings import get_settings

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "knowledge"
SLACK_PATH = FIXTURES / "sample_slack.json"
DOC_PATH = FIXTURES / "sample_doc.csv"
TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

# Documented expected citations (query → cues that must appear in top hits).
EXPECTED = [
    {
        "query": "onboarding checklist for new hires",
        "kind": "slack_message",
        "text_cue": "onboarding checklist",
        "channel": "C_KNOWLEDGE",
    },
    {
        "query": "refund policy within 30 days",
        "kind": "document",
        "text_cue": "refund",
        "filename": "sample_doc.csv",
    },
    {
        "query": "Qdrant tenant isolation",
        "kind": "slack_message",
        "text_cue": "tenant isolation",
        "channel": "C_KNOWLEDGE",
    },
]


def main() -> int:
    if not SLACK_PATH.is_file() or not DOC_PATH.is_file():
        print(f"fixtures missing under {FIXTURES}", file=sys.stderr)
        return 2

    settings = get_settings()
    messages = list(iter_json_messages(SLACK_PATH))
    slack = ingest_messages(client_id=TENANT, messages=messages, settings=settings)
    print(
        f"ingested_slack messages={slack.message_count} "
        f"chunks={slack.chunk_count} points={len(slack.point_ids)}"
    )

    doc = extract_document(DOC_PATH, filename=DOC_PATH.name)
    docs = ingest_extracted_document(client_id=TENANT, document=doc, settings=settings)
    print(
        f"ingested_doc units={docs.unit_count} "
        f"chunks={docs.chunk_count} points={len(docs.point_ids)}"
    )

    for case in EXPECTED:
        result = search_knowledge(
            client_id=TENANT,
            query=case["query"],
            limit=5,
            settings=settings,
        )
        print(f"\nquery={case['query']!r} hits={len(result.hits)}")
        for h in result.hits:
            print(
                f"  score={h.score:.4f} kind={h.kind} "
                f"label={h.short_label()!r} text={h.text[:90]!r}"
            )
            if h.client_id != TENANT:
                print("tenant_mismatch", file=sys.stderr)
                return 1

        if not result.hits:
            print(f"no_hits for {case['query']!r}", file=sys.stderr)
            return 1

        top = result.hits[0]
        if top.kind != case["kind"]:
            print(
                f"expected kind={case['kind']} got={top.kind}",
                file=sys.stderr,
            )
            return 1
        if case["text_cue"].lower() not in top.text.lower():
            # Accept cue anywhere in top-k (embedding may rank a sibling chunk first)
            if not any(case["text_cue"].lower() in h.text.lower() for h in result.hits):
                print(f"missing text cue {case['text_cue']!r}", file=sys.stderr)
                return 1
        if "channel" in case and not any(
            h.channel == case["channel"] for h in result.hits
        ):
            print(f"missing channel {case['channel']!r}", file=sys.stderr)
            return 1
        if "filename" in case and not any(
            h.filename == case["filename"] for h in result.hits
        ):
            print(f"missing filename {case['filename']!r}", file=sys.stderr)
            return 1

        print(f"citation_ok kind={case['kind']} cue={case['text_cue']!r}")

    print("\nsearch_knowledge_smoke_ok")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"search_knowledge_smoke_FAILED: {exc}", file=sys.stderr)
        raise
