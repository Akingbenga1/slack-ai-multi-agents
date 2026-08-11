"""Shared ``AgentConfig.schedules`` persistence (Sprint 28.1).

Smell: twin upsert / get-block / list-due loops in ``slack.schedule`` and
``reports.schedule``. Repository-style store owns JSONB block CRUD once;
kind-specific validation lives on ``ScheduleKindStrategy`` (28.2).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db.models import AgentConfig, SlackInstall

DEFAULT_AGENT_NAME = "default"


def _load_default_config(db: Session, tenant_id: UUID) -> AgentConfig | None:
    return db.scalar(
        select(AgentConfig).where(
            AgentConfig.tenant_id == tenant_id,
            AgentConfig.name == DEFAULT_AGENT_NAME,
        )
    )


def get_block(
    db: Session,
    tenant_id: UUID,
    key: str,
    *,
    for_update: bool = False,
) -> dict[str, Any]:
    """Return a copy of ``schedules[key]`` or ``{}`` when missing/invalid."""
    stmt = select(AgentConfig).where(
        AgentConfig.tenant_id == tenant_id,
        AgentConfig.name == DEFAULT_AGENT_NAME,
    )
    if for_update:
        stmt = stmt.with_for_update()
    config = db.scalar(stmt)
    if config is None or not config.schedules:
        return {}
    block = config.schedules.get(key)
    return dict(block) if isinstance(block, dict) else {}


def upsert_block(
    db: Session,
    *,
    tenant_id: UUID,
    key: str,
    block: dict[str, Any],
    merge: bool = True,
    commit: bool = True,
) -> AgentConfig:
    """
    Write ``agent_configs.schedules[key]`` on the default agent row.

    When ``merge`` is True, patch onto any existing block; when False, replace
    the key with ``block`` as-is. Uses ``SELECT … FOR UPDATE`` when a row
    already exists to reduce lost JSONB updates under concurrency.
    """
    stmt = select(AgentConfig).where(
        AgentConfig.tenant_id == tenant_id,
        AgentConfig.name == DEFAULT_AGENT_NAME,
    )
    config = db.scalar(stmt.with_for_update())
    payload = dict(block)
    if config is None:
        config = AgentConfig(
            tenant_id=tenant_id,
            name=DEFAULT_AGENT_NAME,
            schedules={key: payload},
        )
        db.add(config)
    else:
        schedules = dict(config.schedules or {})
        if merge:
            existing = schedules.get(key)
            base = dict(existing) if isinstance(existing, dict) else {}
            base.update(payload)
            schedules[key] = base
        else:
            schedules[key] = payload
        config.schedules = schedules
        db.add(config)
    if commit:
        db.commit()
        db.refresh(config)
    return config


def list_candidate_tenant_ids(
    db: Session,
    *,
    candidate_tenant_ids: Iterable[UUID] | None = None,
) -> list[UUID]:
    """Default Beat candidates: distinct Slack install tenants."""
    if candidate_tenant_ids is not None:
        return list(candidate_tenant_ids)
    return list(db.scalars(select(SlackInstall.tenant_id).distinct()).all())


def load_blocks_for(
    db: Session,
    key: str,
    tenant_ids: Iterable[UUID],
) -> dict[UUID, dict[str, Any]]:
    """Bulk-load ``schedules[key]`` for many tenants (one AgentConfig query)."""
    ids = list(tenant_ids)
    out: dict[UUID, dict[str, Any]] = {tid: {} for tid in ids}
    if not ids:
        return out
    rows = list(
        db.scalars(
            select(AgentConfig).where(
                AgentConfig.tenant_id.in_(ids),
                AgentConfig.name == DEFAULT_AGENT_NAME,
            )
        ).all()
    )
    for row in rows:
        block = (row.schedules or {}).get(key)
        out[row.tenant_id] = dict(block) if isinstance(block, dict) else {}
    return out


def list_tenants_for(
    db: Session,
    key: str,
    predicate: Callable[[UUID, dict[str, Any]], bool],
    *,
    candidate_tenant_ids: Iterable[UUID] | None = None,
) -> list[UUID]:
    """
    Tenants whose schedule block for ``key`` passes ``predicate``.

    Default candidates: distinct ``SlackInstall.tenant_id`` (Beat jobs need Slack).
    Loads schedule blocks in one query (no per-tenant N+1).
    """
    ids = list_candidate_tenant_ids(db, candidate_tenant_ids=candidate_tenant_ids)
    blocks = load_blocks_for(db, key, ids)
    due: list[UUID] = []
    for tenant_id in ids:
        if predicate(tenant_id, blocks.get(tenant_id, {})):
            due.append(tenant_id)
    return due


__all__ = [
    "DEFAULT_AGENT_NAME",
    "get_block",
    "list_candidate_tenant_ids",
    "list_tenants_for",
    "load_blocks_for",
    "upsert_block",
]
