"""Structured logging with optional `client_id` from tenant context."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

from api.app.tenant import get_client_id

# Project root: api/app/logging_config.py → parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]
DRY_RUN_LOG_PATH = REPO_ROOT / "app.log"

_dry_run_file_logger: logging.Logger | None = None


class ClientIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.client_id = get_client_id() or "-"
        return True


class JsonLikeFormatter(logging.Formatter):
    """Compact key=value lines (readable without a JSON dependency)."""

    def format(self, record: logging.LogRecord) -> str:
        client_id = getattr(record, "client_id", "-")
        base = super().format(record)
        return f"{base} client_id={client_id}"


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if getattr(root, "_csa_configured", False):
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonLikeFormatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    handler.addFilter(ClientIdFilter())

    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    root._csa_configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def get_dry_run_file_logger() -> logging.Logger:
    """Logger that writes only dry-run activity to project-root ``app.log``.

    Does not attach to the root logger, so normal API logs stay on stdout.
    Dry-run HTTP handlers are sync in-process today (no Celery enqueue).
    """
    global _dry_run_file_logger
    if _dry_run_file_logger is not None:
        return _dry_run_file_logger

    log_path = DRY_RUN_LOG_PATH.resolve()
    log = logging.getLogger("api.dry_run.file")
    log.setLevel(logging.INFO)
    log.propagate = False
    target = str(log_path)
    if not any(
        isinstance(h, logging.FileHandler)
        and getattr(h, "baseFilename", None) == target
        for h in log.handlers
    ):
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(
            JsonLikeFormatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
        handler.addFilter(ClientIdFilter())
        log.addHandler(handler)
    _dry_run_file_logger = log
    return log


def log_dry_run_activity(
    *,
    endpoint: str,
    phase: str,
    client_id: str | None = None,
    request: Any = None,
    response: Any = None,
    error: Any = None,
    celery: Any = None,
) -> None:
    """Append one dry-run activity line (request/response JSON) to ``app.log``."""
    payload: dict[str, Any] = {
        "endpoint": endpoint,
        "phase": phase,
        "client_id": str(client_id or get_client_id() or "-"),
    }
    if request is not None:
        payload["request"] = request
    if response is not None:
        payload["response"] = response
    if error is not None:
        payload["error"] = error
    # Explicit: dry-run paths do not enqueue Celery; keep field for clarity.
    payload["celery"] = celery if celery is not None else None
    log = get_dry_run_file_logger()
    log.info("%s", json.dumps(payload, default=str))
    for handler in log.handlers:
        handler.flush()


def log_agent_prompts(
    *,
    role: str,
    system: str,
    messages: list[dict[str, Any]] | None = None,
    client_id: str | None = None,
    model_tier: str | None = None,
) -> None:
    """Append orchestrator/executor LLM system + user prompts to ``app.log``."""
    user_parts: list[str] = []
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        if (msg.get("role") or "").strip().lower() != "user":
            continue
        content = msg.get("content")
        if content is None:
            continue
        user_parts.append(content if isinstance(content, str) else str(content))
    payload: dict[str, Any] = {
        "kind": "agent_prompts",
        "role": (role or "").strip() or "unknown",
        "client_id": str(client_id or get_client_id() or "-"),
        "system": system or "",
        "user": "\n\n".join(user_parts),
        "messages": messages or [],
    }
    if model_tier is not None:
        payload["model_tier"] = model_tier
    log = get_dry_run_file_logger()
    log.info("%s", json.dumps(payload, default=str))
    for handler in log.handlers:
        handler.flush()


def log_tool_rag_activity(
    *,
    phase: str,
    client_id: str | None = None,
    **fields: Any,
) -> None:
    """Append one Tool RAG pipeline event to project-root ``app.log``.

    Phases follow filter → retrieve → shortlist → plan → lazy_load.
    """
    payload: dict[str, Any] = {
        "kind": "tool_rag",
        "phase": (phase or "").strip() or "unknown",
        "client_id": str(client_id or get_client_id() or "-"),
    }
    reserved = {"kind", "phase", "client_id"}
    for key, value in fields.items():
        if value is None:
            continue
        # Avoid clobbering the event kind with tool kind=mcp|cli|code.
        field_key = "tool_kind" if key == "kind" else key
        if field_key in reserved:
            continue
        payload[field_key] = value
    log = get_dry_run_file_logger()
    log.info("%s", json.dumps(payload, default=str))
    for handler in log.handlers:
        handler.flush()
