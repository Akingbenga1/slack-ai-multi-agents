"""CLI: ingest a Slack history dump for one tenant → TEI → Qdrant.

Example:
  uv run python scripts/ingest_slack_history.py \\
    --client-id aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa \\
    --format json --path sample.json --query \"hello\"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from api.app.ingest.parsers import (
    iter_csv_messages,
    iter_json_messages,
    iter_ndjson_messages,
    iter_slack_export_zip,
    iter_xlsx_messages,
)
from api.app.ingest.pipeline import ingest_messages
from api.app.qdrant import search_vectors
from api.app.settings import get_settings
from api.app.tei import TeiClient


def _load_messages(fmt: str, path: Path, channel: str | None):
    if fmt == "zip":
        return list(iter_slack_export_zip(path))
    if fmt == "json":
        return list(iter_json_messages(path, channel=channel))
    if fmt == "ndjson":
        return list(iter_ndjson_messages(path, channel=channel))
    if fmt == "csv":
        return list(iter_csv_messages(path, channel=channel))
    if fmt == "xlsx":
        return list(iter_xlsx_messages(path, channel=channel))
    raise ValueError(f"unsupported format: {fmt}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest Slack history dump for one tenant")
    parser.add_argument("--client-id", required=True, help="Tenant UUID (required)")
    parser.add_argument(
        "--format",
        required=True,
        choices=("zip", "json", "ndjson", "csv", "xlsx"),
    )
    parser.add_argument("--path", required=True, type=Path, help="Dump file path")
    parser.add_argument(
        "--channel",
        default=None,
        help="Channel override when dump rows lack channel",
    )
    parser.add_argument(
        "--query",
        default=None,
        help="Optional smoke search text after ingest",
    )
    parser.add_argument("--limit", type=int, default=5, help="Search hit limit")
    args = parser.parse_args(argv)

    if not args.path.is_file():
        print(f"file not found: {args.path}", file=sys.stderr)
        return 2

    settings = get_settings()
    messages = _load_messages(args.format, args.path, args.channel)
    print(f"parsed messages={len(messages)} format={args.format}")

    result = ingest_messages(
        client_id=args.client_id,
        messages=messages,
        settings=settings,
    )
    print(
        f"ingested client_id={result.client_id} "
        f"messages={result.message_count} chunks={result.chunk_count} "
        f"points={len(result.point_ids)}"
    )

    if args.query:
        tei = TeiClient(settings)
        qvec = tei.embed(args.query)[0]
        hits = search_vectors(
            client_id=args.client_id,
            query_vector=qvec,
            limit=args.limit,
            settings=settings,
        )
        print(f"search hits={len(hits)} query={args.query!r}")
        for h in hits:
            payload = h.payload or {}
            print(
                f"  score={h.score:.4f} channel={payload.get('channel')} "
                f"ts={payload.get('ts')} text={str(payload.get('message_text') or '')[:80]!r}"
            )
            if payload.get("client_id") != args.client_id:
                print("tenant_mismatch", file=sys.stderr)
                return 1

    print("ingest_ok")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ingest_FAILED: {exc}", file=sys.stderr)
        raise
