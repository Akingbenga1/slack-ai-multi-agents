"""Structured logging with optional `client_id` from tenant context."""

from __future__ import annotations

import logging
import sys

from api.app.tenant import get_client_id


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
