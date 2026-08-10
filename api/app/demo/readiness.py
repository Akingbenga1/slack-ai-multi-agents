"""First-org demo readiness checklist (Sprint 22.1)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.billing.plans import get_tenant_entitlements, plan_is_active
from api.app.db.models import AgentConfig, BillingCustomer, Membership, SlackInstall, Tenant, User
from api.app.membership import DEMO_ADMIN_ID, DEMO_OWNER_ID, DEMO_TENANT_ID
from api.app.reports.schedule import SCHEDULE_KEY as REPORT_SCHEDULE_KEY, get_recurring_report_schedule
from api.app.slack.schedule import DEFAULT_AGENT_NAME, SCHEDULE_KEY as SYNC_SCHEDULE_KEY
from api.app.slack.schedule import is_slack_history_sync_enabled


def demo_readiness(db: Session, *, tenant_id: UUID | str | None = None) -> dict[str, Any]:
    """
    Aggregate first-org checklist for the demo tenant (or ``tenant_id``).

    Used by ``scripts/first_org_hardening_smoke.py`` and optional operator tooling.
    Does not call Stripe / Slack / Anthropic.
    """
    tid = UUID(str(tenant_id or DEMO_TENANT_ID))
    tenant = db.get(Tenant, tid)
    owner = db.get(User, DEMO_OWNER_ID)
    admin = db.get(User, DEMO_ADMIN_ID)
    membership = None
    if admin is not None:
        membership = db.scalar(
            select(Membership).where(
                Membership.user_id == admin.id,
                Membership.tenant_id == tid,
            )
        )
    billing = db.scalar(select(BillingCustomer).where(BillingCustomer.tenant_id == tid))
    install = db.scalar(
        select(SlackInstall)
        .where(SlackInstall.tenant_id == tid)
        .order_by(SlackInstall.installed_at.desc())
        .limit(1)
    )
    agent = db.scalar(
        select(AgentConfig).where(
            AgentConfig.tenant_id == tid,
            AgentConfig.name == DEFAULT_AGENT_NAME,
        )
    )
    report = get_recurring_report_schedule(db, tid) if tenant else None
    sync_enabled = is_slack_history_sync_enabled(db, tid) if tenant else False
    ents = get_tenant_entitlements(db, tid) if billing else {}
    active = plan_is_active(db, tid) if tenant else False

    checks = {
        "tenant_exists": tenant is not None,
        "owner_user": owner is not None and owner.email == "owner@example.com",
        "admin_user": admin is not None and admin.email == "admin@example.com",
        "admin_membership": membership is not None,
        "billing_row": billing is not None,
        "plan_active": active,
        "entitlement_agent": bool(ents.get("agent")) and active,
        "entitlement_ingest": bool(ents.get("ingest")) and active,
        "entitlement_sync": bool(ents.get("sync")) and active,
        "agent_config": agent is not None,
        "sync_schedule_enabled": sync_enabled,
        "slack_install": install is not None,
        "report_channel_set": bool(report and report.get("channel_id")),
        "report_schedule_enabled": bool(report and report.get("enabled")),
    }
    return {
        "tenant_id": str(tid),
        "plan_status": (billing.plan_status if billing else None),
        "entitlements": ents,
        "slack_team_id": install.team_id if install else None,
        "sync_schedule_key": SYNC_SCHEDULE_KEY,
        "report_schedule_key": REPORT_SCHEDULE_KEY,
        "report": report,
        "checks": checks,
        "ready_for_paid_demo": all(
            [
                checks["tenant_exists"],
                checks["owner_user"],
                checks["admin_user"],
                checks["admin_membership"],
                checks["billing_row"],
                checks["plan_active"],
                checks["entitlement_agent"],
                checks["entitlement_ingest"],
                checks["entitlement_sync"],
                checks["agent_config"],
            ]
        ),
        "ready_for_slack_jobs": all(
            [
                checks["plan_active"],
                checks["entitlement_sync"],
                checks["slack_install"],
                checks["sync_schedule_enabled"],
            ]
        ),
    }


__all__ = ["demo_readiness"]
