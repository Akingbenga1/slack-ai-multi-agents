"""MCP tool: ``rename_slack_file`` — org-copy rename (+ optional Slack title)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from api.app.settings import get_settings
from api.app.slack.file_actions import rename_slack_file_or_copy

RenameFn = Callable[..., dict[str, Any]]


def rename_slack_file_tool(
    *,
    client_id: str | None,
    new_filename: str,
    stored_relative_path: str | None = None,
    file_id: str | None = None,
    bot_token: str | None = None,
    question: str | None = None,
    upload_root: Path | str | None = None,
    rename_fn: RenameFn | None = None,
) -> dict[str, Any]:
    """
    Rename a tenant-stored org copy (primary) and optionally Slack title.

    ``client_id`` is required (fail-closed). Prefer ``stored_relative_path``;
    Slack ``file_id`` + ``bot_token`` enable best-effort ``files.edit``.
    """
    root = Path(upload_root) if upload_root else Path(get_settings().upload_dir)
    fn = rename_fn or rename_slack_file_or_copy
    return fn(
        client_id=client_id or "",
        upload_root=root,
        new_filename=new_filename,
        question=question,
        file_id=file_id,
        stored_relative_path=stored_relative_path,
        bot_token=bot_token,
        attached_evidence=None,
    )


__all__ = ["rename_slack_file_tool"]
