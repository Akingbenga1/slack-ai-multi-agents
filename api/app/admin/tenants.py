"""Tenant list / detail aggregates for platform admin (Sprint 21.1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db.models import BillingCustomer, SlackInstall, Tenant
from api.app.slack.sync_status import get_slack_history_sync_status


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def tenant_summary_row(db: Session, tenant: Tenant) -> dict[str, Any]:
    """One row for the admin tenant list (plan, Slack, last sync)."""
    billing = db.scalar(
        select(BillingCustomer).where(BillingCustomer.tenant_id == tenant.id)
    )
    install = db.scalar(
        select(SlackInstall).where(SlackInstall.tenant_id == tenant.id)
    )
    sync = get_slack_history_sync_status(db, tenant.id)
    last_synced = (sync.get("watermarks") or {}).get("last_synced_at")
    last_success = sync.get("last_success") or {}
    last_failure = sync.get("last_failure") or {}

    return {
        "id": str(tenant.id),
        "slug": tenant.slug,
        "name": tenant.name,
        "status": tenant.status,
        "created_at": _iso(tenant.created_at),
        "updated_at": _iso(tenant.updated_at),
        "plan_status": (billing.plan_status if billing else "inactive") or "inactive",
        "entitlements": dict(billing.entitlements or {}) if billing else {},
        "stripe_customer_id": billing.stripe_customer_id if billing else None,
        "stripe_subscription_id": billing.stripe_subscription_id if billing else None,
        "slack_connected": install is not None,
        "slack_team_id": install.team_id if install else None,
        "slack_team_name": install.team_name if install else None,
        "slack_installed_at": _iso(install.installed_at) if install else None,
        "sync_enabled": bool(sync.get("enabled")),
        "last_synced_at": last_synced,
        "last_sync_success_at": last_success.get("finished_at"),
        "last_sync_failure_at": last_failure.get("finished_at"),
        "last_sync_failure_error": last_failure.get("error"),
        "sync_channel_count": int((sync.get("watermarks") or {}).get("channel_count") or 0),
    }


def list_tenant_summaries(db: Session) -> list[dict[str, Any]]:
    tenants = list(db.scalars(select(Tenant).order_by(Tenant.created_at.asc())).all())
    return [tenant_summary_row(db, t) for t in tenants]


def get_tenant_detail(db: Session, tenant_id: UUID) -> dict[str, Any] | None:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        return None
    summary = tenant_summary_row(db, tenant)
    sync = get_slack_history_sync_status(db, tenant_id)
    summary["sync"] = sync
    return summary
