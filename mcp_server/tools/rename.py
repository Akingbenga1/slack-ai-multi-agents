"""MCP tool: ``rename_slack_file`` — org-copy rename (+ optional Slack title)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID

from api.app.logging_config import get_logger
from api.app.settings import get_settings
from api.app.slack.file_actions import rename_slack_file_or_copy

logger = get_logger("mcp_server.tools.rename")

RenameFn = Callable[..., dict[str, Any]]


def _bot_token_for_tenant(client_id: str) -> str | None:
    """Resolve install token server-side — never accept tokens from MCP args."""
    from api.app.db.session import SessionLocal
    from api.app.slack.store import get_bot_token, get_install_by_tenant

    try:
        tid = UUID(str(client_id).strip())
    except ValueError:
        return None
    db = SessionLocal()
    try:
        install = get_install_by_tenant(db, tid)
        if install is None:
            return None
        return get_bot_token(install, get_settings())
    except ValueError:
        # Missing/invalid crypto material — treat as no token.
        logger.warning("rename_bot_token_unavailable client_id=%s", client_id)
        return None
    except Exception:
        logger.exception("rename_bot_token_lookup_failed client_id=%s", client_id)
        raise
    finally:
        db.close()


def rename_slack_file_tool(
    *,
    client_id: str | None,
    new_filename: str,
    stored_relative_path: str | None = None,
    file_id: str | None = None,
    question: str | None = None,
    upload_root: Path | str | None = None,
    rename_fn: RenameFn | None = None,
) -> dict[str, Any]:
    """
    Rename a tenant-stored org copy (primary) and optionally Slack title.

    ``client_id`` is required (fail-closed). Prefer ``stored_relative_path``.
    Slack ``file_id`` uses the org install token from the DB (not tool args).
    """
    root = Path(upload_root) if upload_root else Path(get_settings().upload_dir)
    fn = rename_fn or rename_slack_file_or_copy
    cid = client_id or ""
    bot_token = _bot_token_for_tenant(cid) if file_id else None
    return fn(
        client_id=cid,
        upload_root=root,
        new_filename=new_filename,
        question=question,
        file_id=file_id,
        stored_relative_path=stored_relative_path,
        bot_token=bot_token,
        attached_evidence=None,
    )


__all__ = ["rename_slack_file_tool"]
