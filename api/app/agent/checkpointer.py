"""Postgres (and memory) checkpointers for thread continuity (Sprint 13.2)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings

logger = get_logger("api.agent.checkpointer")

_pool: ConnectionPool | None = None
_postgres_saver: PostgresSaver | None = None
_setup_done = False


def to_psycopg_conninfo(database_url: str) -> str:
    """SQLAlchemy `postgresql+psycopg://` → psycopg `postgresql://`."""
    url = (database_url or "").strip()
    if url.startswith("postgresql+psycopg://"):
        return "postgresql://" + url[len("postgresql+psycopg://") :]
    if url.startswith("postgres+psycopg://"):
        return "postgresql://" + url[len("postgres+psycopg://") :]
    return url


def thread_id_for_tenant(client_id: str, conversation_id: str | None = None) -> str:
    """
    Checkpoint thread key scoped per tenant.

    Format: `{client_id}:{conversation_id}` so threads cannot collide across tenants.
    """
    cid = str(UUID(str(client_id).strip()))
    conv = (conversation_id or "default").strip() or "default"
    if ":" in conv:
        # Avoid ambiguous nested separators from callers
        conv = conv.replace(":", "_")
    return f"{cid}:{conv}"


def get_memory_checkpointer() -> MemorySaver:
    return MemorySaver()


def _ensure_postgres_pool(settings: Settings) -> ConnectionPool:
    global _pool
    if _pool is not None:
        return _pool
    conninfo = to_psycopg_conninfo(settings.database_url)
    _pool = ConnectionPool(
        conninfo=conninfo,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        min_size=1,
        max_size=8,
        open=True,
    )
    return _pool


def get_postgres_checkpointer(
    settings: Settings | None = None,
    *,
    setup: bool = True,
) -> PostgresSaver:
    """Process-wide PostgresSaver backed by a connection pool."""
    global _postgres_saver, _setup_done
    settings = settings or get_settings()
    if _postgres_saver is None:
        pool = _ensure_postgres_pool(settings)
        _postgres_saver = PostgresSaver(pool)
    if setup and not _setup_done:
        _postgres_saver.setup()
        _setup_done = True
        logger.info("agent_checkpointer_postgres_ready")
    return _postgres_saver


def get_checkpointer(
    settings: Settings | None = None,
    *,
    backend: str | None = None,
) -> BaseCheckpointSaver:
    """
    Resolve checkpointer from settings.

    `AGENT_CHECKPOINTER=memory|postgres` (default postgres).
    Falls back to memory if postgres setup fails (logged).
    """
    settings = settings or get_settings()
    choice = (backend or settings.agent_checkpointer or "postgres").strip().lower()
    if choice == "memory":
        return get_memory_checkpointer()
    try:
        return get_postgres_checkpointer(settings)
    except Exception:
        logger.exception("agent_checkpointer_postgres_failed_fallback_memory")
        return get_memory_checkpointer()


@contextmanager
def ephemeral_postgres_checkpointer(
    conninfo: str,
) -> Iterator[PostgresSaver]:
    """Context-managed saver for scripts/tests (opens its own connection)."""
    with PostgresSaver.from_conn_string(conninfo) as saver:
        saver.setup()
        yield saver


def reset_checkpointer_singletons() -> None:
    """Test helper — close pool and clear cached saver."""
    global _pool, _postgres_saver, _setup_done
    if _pool is not None:
        try:
            _pool.close()
        except Exception:
            pass
    _pool = None
    _postgres_saver = None
    _setup_done = False
