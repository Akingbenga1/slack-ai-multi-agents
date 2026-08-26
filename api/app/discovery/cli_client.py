"""CLI discovery backend — searches the local portable CLI SQLite DB."""

from __future__ import annotations

from pathlib import Path

from api.app.discovery.base import (
    DiscoveredTool,
    DiscoveryNotConfiguredError,
    DiscoveryUpstreamError,
    ToolKind,
)
from api.app.discovery.cli_normalize import normalize_cli_discovered_tool, parse_tldr_examples
from api.app.discovery.tldr_store import search_db
from api.app.logging_config import get_logger
from api.app.settings import Settings

logger = get_logger("api.discovery.cli_client")


class CliDiscoveryClient:
    """In-process CLI discovery against the portable SQLite DB (no HTTP upstream)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def search(self, kind: ToolKind, query: str) -> list[DiscoveredTool]:
        if kind != "cli":
            raise DiscoveryNotConfiguredError(kind)

        q = (query or "").strip()
        if not q:
            return []

        db_path = self._settings.discovery_cli_db_path_resolved
        if not db_path.is_file():
            raise DiscoveryNotConfiguredError("cli")

        limit = max(1, int(self._settings.discovery_cli_search_limit))
        logger.info(
            "discovery_cli_search query_len=%s db=%s limit=%s",
            len(q),
            db_path,
            limit,
        )
        try:
            hits = search_db(q, db_path=db_path, limit=limit)
        except FileNotFoundError as exc:
            raise DiscoveryNotConfiguredError("cli") from exc
        except Exception as exc:  # noqa: BLE001
            raise DiscoveryUpstreamError(
                f"CLI SQLite search failed: {exc}",
                code="discovery_cli_db_error",
                status_code=502,
            ) from exc

        tools: list[DiscoveredTool] = []
        for hit in hits:
            examples = parse_tldr_examples(hit.body)
            tool = DiscoveredTool(
                id=f"cli:{hit.platform}:{hit.command}",
                name=hit.command,
                summary=hit.description,
                source="tldr",
                kind="cli",
                metadata={
                    "platform": hit.platform,
                    "score": hit.score,
                    "examples": examples,
                },
            )
            tools.append(normalize_cli_discovered_tool(tool))
        return tools


def cli_db_configured(settings: Settings) -> bool:
    """True when the portable CLI discovery SQLite file is present."""
    return Path(settings.discovery_cli_db_path_resolved).is_file()
