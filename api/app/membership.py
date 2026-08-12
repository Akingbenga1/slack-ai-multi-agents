from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from api.app.auth.tokens import RoleName
from api.app.billing.customers import ensure_billing_customer
from api.app.billing.plans import apply_plan_state
from api.app.db.models import AgentConfig, Membership, Role, Tenant, User
from api.app.settings import get_settings
from api.app.slack.schedule import DEFAULT_AGENT_NAME, SCHEDULE_KEY
from api.app.slack.store import upsert_install
from api.app.reports.schedule import (
    DEFAULT_CADENCE as REPORT_DEFAULT_CADENCE,
    DEFAULT_ENABLED as REPORT_DEFAULT_ENABLED,
    SCHEDULE_KEY as REPORT_SCHEDULE_KEY,
    window_label_for_cadence,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Stable demo IDs (aligned with Next.js demo tenant)
DEMO_TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
DEMO_OWNER_ID = UUID("22222222-2222-2222-2222-222222222222")
DEMO_ADMIN_ID = UUID("33333333-3333-3333-3333-333333333333")
# Internal RBAC tenant for platform_owner memberships (not an org portal tenant)
PLATFORM_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


@dataclass
class LoginPrincipal:
    sub: str
    email: str
    role: RoleName
    tenant_id: Optional[str]
    all_access: bool


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    return pwd_context.verify(password, hashed)


def resolve_login_principal(db: Session, *, email: str, password: str) -> LoginPrincipal | None:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None

    memberships = db.scalars(
        select(Membership)
        .options(joinedload(Membership.role), joinedload(Membership.tenant))
        .where(Membership.user_id == user.id)
    ).all()

    platform_roles = [m for m in memberships if m.role.name == "platform_owner"]
    if platform_roles:
        return LoginPrincipal(
            sub=str(user.id),
            email=user.email,
            role="platform_owner",
            tenant_id=None,
            all_access=True,
        )

    org_roles = [m for m in memberships if m.role.name == "org_admin"]
    # MVP: org user belongs to exactly one tenant
    if len(org_roles) != 1:
        return None

    m = org_roles[0]
    return LoginPrincipal(
        sub=str(user.id),
        email=user.email,
        role="org_admin",
        tenant_id=str(m.tenant_id),
        all_access=False,
    )


def ensure_demo_memberships(db: Session) -> None:
    """Idempotent seed: roles, demo tenant, owner (all-access), org admin (one tenant)."""
    roles = {
        "platform_owner": "Platform owner — all-tenant access",
        "org_admin": "Organisation admin — single tenant",
    }
    role_rows: dict[str, Role] = {}
    for name, desc in roles.items():
        row = db.scalar(select(Role).where(Role.name == name))
        if row is None:
            row = Role(name=name, description=desc)
            db.add(row)
            db.flush()
        role_rows[name] = row

    tenant = db.get(Tenant, DEMO_TENANT_ID)
    if tenant is None:
        tenant = Tenant(
            id=DEMO_TENANT_ID,
            slug="demo-org",
            name="Demo Organisation",
            status="active",
        )
        db.add(tenant)
        db.flush()

    platform_tenant = db.get(Tenant, PLATFORM_TENANT_ID)
    if platform_tenant is None:
        platform_tenant = Tenant(
            id=PLATFORM_TENANT_ID,
            slug="__platform__",
            name="Platform (internal)",
            status="active",
        )
        db.add(platform_tenant)
        db.flush()

    owner = db.get(User, DEMO_OWNER_ID)
    if owner is None:
        owner = User(
            id=DEMO_OWNER_ID,
            email="owner@example.com",
            display_name="Platform Owner",
            hashed_password=hash_password("owner123"),
            is_active=True,
        )
        db.add(owner)
        db.flush()

    owner_membership = db.scalar(
        select(Membership).where(
            Membership.user_id == owner.id,
            Membership.tenant_id == platform_tenant.id,
        )
    )
    if owner_membership is None:
        db.add(
            Membership(
                tenant_id=platform_tenant.id,
                user_id=owner.id,
                role_id=role_rows["platform_owner"].id,
            )
        )
    elif owner_membership.role_id != role_rows["platform_owner"].id:
        owner_membership.role_id = role_rows["platform_owner"].id

    admin = db.get(User, DEMO_ADMIN_ID)
    if admin is None:
        admin = User(
            id=DEMO_ADMIN_ID,
            email="admin@example.com",
            display_name="Org Admin",
            hashed_password=hash_password("admin123"),
            is_active=True,
        )
        db.add(admin)
        db.flush()

    membership = db.scalar(
        select(Membership).where(
            Membership.user_id == admin.id,
            Membership.tenant_id == tenant.id,
        )
    )
    if membership is None:
        db.add(
            Membership(
                tenant_id=tenant.id,
                user_id=admin.id,
                role_id=role_rows["org_admin"].id,
            )
        )
    elif membership.role_id != role_rows["org_admin"].id:
        membership.role_id = role_rows["org_admin"].id

    agent = db.scalar(
        select(AgentConfig).where(
            AgentConfig.tenant_id == tenant.id,
            AgentConfig.name == DEFAULT_AGENT_NAME,
        )
    )
    settings = get_settings()
    report_channel = (settings.demo_report_channel_id or "").strip() or None
    report_enabled = REPORT_DEFAULT_ENABLED
    if report_channel:
        report_enabled = True
    default_schedules = {
        SCHEDULE_KEY: {"enabled": True},
        REPORT_SCHEDULE_KEY: {
            "enabled": report_enabled,
            "cadence": REPORT_DEFAULT_CADENCE,
            "channel_id": report_channel,
            "window_label": window_label_for_cadence(REPORT_DEFAULT_CADENCE),
        },
    }
    if agent is None:
        db.add(
            AgentConfig(
                tenant_id=tenant.id,
                name=DEFAULT_AGENT_NAME,
                schedules=default_schedules,
            )
        )
    else:
        schedules = dict(agent.schedules or {})
        sync_block = (
            dict(schedules.get(SCHEDULE_KEY) or {})
            if isinstance(schedules.get(SCHEDULE_KEY), dict)
            else {}
        )
        sync_block.setdefault("enabled", True)
        schedules[SCHEDULE_KEY] = sync_block

        report_block = (
            dict(schedules.get(REPORT_SCHEDULE_KEY) or {})
            if isinstance(schedules.get(REPORT_SCHEDULE_KEY), dict)
            else {}
        )
        report_block.setdefault("enabled", REPORT_DEFAULT_ENABLED)
        report_block.setdefault("cadence", REPORT_DEFAULT_CADENCE)
        report_block.setdefault("channel_id", None)
        if report_channel:
            report_block["enabled"] = True
            report_block["channel_id"] = report_channel
        report_block.setdefault(
            "window_label",
            window_label_for_cadence(
                str(report_block.get("cadence") or REPORT_DEFAULT_CADENCE)
            ),
        )
        schedules[REPORT_SCHEDULE_KEY] = report_block
        agent.schedules = schedules
        db.add(agent)

    # Sprint 11.1 — local billing_customers row (Stripe id when STRIPE_SECRET_KEY set)
    billing = ensure_billing_customer(
        db,
        tenant_id=tenant.id,
        email=admin.email,
        create_stripe=True,
        settings=settings,
    )
    # Sprint 22.1 — optional local plan activation without Checkout
    if settings.demo_activate_plan:
        apply_plan_state(
            db,
            billing,
            plan_status="active",
            plan_source="admin",
            override_reason="demo_seed",
            extra_meta={"source": "demo_seed"},
        )

    team_id = (settings.demo_slack_team_id or "").strip()
    bot_token = (settings.demo_slack_bot_token or "").strip()
    if team_id and bot_token:
        upsert_install(
            db,
            settings=settings,
            tenant_id=tenant.id,
            team_id=team_id,
            team_name="Demo Workspace",
            bot_token=bot_token,
            authed_user_id=None,
            scopes="demo",
            raw={"source": "demo_seed"},
            commit=False,
        )

    db.commit()
