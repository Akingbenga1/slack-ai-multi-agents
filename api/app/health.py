"""Dependency health probes for `/health`."""

from __future__ import annotations

from typing import Any

import httpx
from redis import Redis
from sqlalchemy import text

from api.app.db.session import engine
from api.app.settings import Settings


def check_postgres() -> dict[str, Any]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001 — surface probe errors
        return {"status": "error", "detail": str(exc)}


def check_redis(settings: Settings) -> dict[str, Any]:
    try:
        client = Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        pong = client.ping()
        client.close()
        if pong:
            return {"status": "ok"}
        return {"status": "error", "detail": "ping failed"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


def check_qdrant(settings: Settings) -> dict[str, Any]:
    """Qdrant-adapter probe (only used when ``VECTOR_STORE=qdrant``)."""
    try:
        with httpx.Client(timeout=3.0) as client:
            r = client.get(f"{settings.qdrant_url.rstrip('/')}/readyz")
            if r.status_code == 200:
                return {"status": "ok"}
            return {"status": "error", "detail": f"HTTP {r.status_code}"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


def check_tei(settings: Settings) -> dict[str, Any]:
    """TEI-adapter probe (only used when ``EMBEDDING_PROVIDER=tei``)."""
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{settings.tei_url.rstrip('/')}/health")
            if r.status_code == 200:
                return {"status": "ok"}
            return {"status": "error", "detail": f"HTTP {r.status_code}"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


def check_vector_store(settings: Settings) -> dict[str, Any]:
    """Probe the selected ``VECTOR_STORE`` adapter (not every vendor)."""
    name = (settings.vector_store or "qdrant").strip().lower()
    if name == "qdrant":
        return {"adapter": "qdrant", **check_qdrant(settings)}
    if name == "pgvector":
        return {
            "adapter": "pgvector",
            "status": "error",
            "detail": "pgvector adapter not implemented",
        }
    return {
        "adapter": name,
        "status": "error",
        "detail": f"Unknown VECTOR_STORE={name!r}",
    }


def check_embedding(settings: Settings) -> dict[str, Any]:
    """Probe the selected ``EMBEDDING_PROVIDER`` adapter (not every vendor)."""
    name = (settings.embedding_provider or "tei").strip().lower()
    if name == "tei":
        return {"adapter": "tei", **check_tei(settings)}
    if name in {"ollama", "openai"}:
        return {
            "adapter": name,
            "status": "error",
            "detail": f"{name} embedding adapter not implemented",
        }
    return {
        "adapter": name,
        "status": "error",
        "detail": f"Unknown EMBEDDING_PROVIDER={name!r}",
    }


def run_deep_health(settings: Settings) -> dict[str, Any]:
    checks = {
        "postgres": check_postgres(),
        "redis": check_redis(settings),
        "vector_store": check_vector_store(settings),
        "embedding": check_embedding(settings),
    }
    ok = all(c.get("status") == "ok" for c in checks.values())
    return {"status": "ok" if ok else "degraded", "checks": checks}
