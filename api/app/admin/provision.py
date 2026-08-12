"""Create a second (or Nth) organisation via platform admin (Sprint 22.4 / PO-04)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.admin.actions import write_audit_log
from api.app.billing.customers import ensure_billing_customer
from api.app.billing.plans import apply_plan_state
from api.app.db.models import AgentConfig, Membership, Role, Tenant, User
from api.app.logging_config import get_logger
from api.app.membership import hash_password
from api.app.settings import Settings, get_settings
from api.app.slack.schedule import DEFAULT_AGENT_NAME

logger = get_logger("api.admin.provision")

SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$")


class OrganisationError(ValueError):
    """Invalid create-org input or conflict."""


@dataclass
class CreatedOrganisation:
    tenant: Tenant
    admin: User
    created: bool
    admin_password: Optional[str] = None  # only set when newly generated


def normalize_slug(raw: str) -> str:
    slug = (raw or "").strip().lower()
    if not slug or not SLUG_RE.match(slug):
        raise OrganisationError(
            "slug must be 1–64 chars: lowercase letters, digits, hyphens "
            "(no leading/trailing hyphen)"
        )
    return slug


def slug_from_name(name: str) -> str:
    """Derive a URL slug from an organisation name (self-signup)."""
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    slug = slug[:64].strip("-")
    return normalize_slug(slug)


def allocate_unique_slug(db: Session, base: str) -> str:
    """Return `base` or `base-<hex>` if the slug is already taken."""
    slug_n = normalize_slug(base)
    if db.scalar(select(Tenant).where(Tenant.slug == slug_n)) is None:
        return slug_n
    stem = slug_n[:57].rstrip("-") or "org"
    for _ in range(8):
        candidate = f"{stem}-{uuid4().hex[:6]}"
        if db.scalar(select(Tenant).where(Tenant.slug == candidate)) is None:
            return candidate
    raise OrganisationError("could not allocate a unique slug")


def _ensure_org_admin_role(db: Session) -> Role:
    role = db.scalar(select(Role).where(Role.name == "org_admin"))
    if role is None:
        role = Role(name="org_admin", description="Organisation admin — single tenant")
        db.add(role)
        db.flush()
    return role


def _ensure_default_agent_config(db: Session, tenant_id: UUID) -> AgentConfig:
    config = db.scalar(
        select(AgentConfig).where(
            AgentConfig.tenant_id == tenant_id,
            AgentConfig.name == DEFAULT_AGENT_NAME,
        )
    )
    if config is not None:
        return config
    config = AgentConfig(
        tenant_id=tenant_id,
        name=DEFAULT_AGENT_NAME,
        extra={"display_name": "Workspace agent"},
    )
    db.add(config)
    db.flush()
    return config


def create_organisation(
    db: Session,
    *,
    name: str,
    slug: str,
    admin_email: str,
    admin_password: str | None = None,
    admin_display_name: str | None = None,
    activate_plan: bool = False,
    actor_user_id: UUID | str | None = None,
    actor_email: str | None = None,
    settings: Settings | None = None,
    commit: bool = True,
    audit_source: str = "admin_provision",
) -> CreatedOrganisation:
    """
    Stand up a new tenant + org admin + billing row + default agent config.

    Raises OrganisationError on validation / unique conflicts.
    """
    settings = settings or get_settings()
    name_n = (name or "").strip()
    if not name_n or len(name_n) > 255:
        raise OrganisationError("name is required (max 255 chars)")

    slug_n = normalize_slug(slug)
    email_n = (admin_email or "").strip().lower()
    if not email_n or "@" not in email_n or len(email_n) > 320:
        raise OrganisationError("admin_email must be a valid email")

    if db.scalar(select(Tenant).where(Tenant.slug == slug_n)) is not None:
        raise OrganisationError(f"slug already exists: {slug_n}")

    if db.scalar(select(User).where(User.email == email_n)) is not None:
        raise OrganisationError(f"admin email already exists: {email_n}")

    password = (admin_password or "").strip() or None
    generated: str | None = None
    if not password:
        generated = uuid4().hex[:12]
        password = generated
    if len(password) < 8:
        raise OrganisationError("admin_password must be at least 8 characters")

    role = _ensure_org_admin_role(db)
    tenant = Tenant(slug=slug_n, name=name_n, status="active")
    db.add(tenant)
    db.flush()

    admin = User(
        email=email_n,
        display_name=(admin_display_name or f"{name_n} Admin").strip()[:255],
        hashed_password=hash_password(password),
        is_active=True,
    )
    db.add(admin)
    db.flush()

    db.add(
        Membership(
            tenant_id=tenant.id,
            user_id=admin.id,
            role_id=role.id,
        )
    )
    db.flush()

    _ensure_default_agent_config(db, tenant.id)

    billing = ensure_billing_customer(
        db,
        tenant_id=tenant.id,
        email=email_n,
        create_stripe=False,
        settings=settings,
    )
    if activate_plan:
        apply_plan_state(
            db,
            billing,
            plan_status="active",
            plan_source="admin",
            override_reason="admin_provision",
            extra_meta={"source": "admin_provision"},
        )

    write_audit_log(
        db,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action="tenant.created",
        tenant_id=tenant.id,
        detail={
            "slug": slug_n,
            "name": name_n,
            "admin_email": email_n,
            "activate_plan": activate_plan,
            "source": audit_source,
        },
    )

    if commit:
        db.commit()
        db.refresh(tenant)
        db.refresh(admin)
    else:
        db.flush()

    logger.info(
        "organisation_created tenant_id=%s slug=%s admin=%s",
        tenant.id,
        slug_n,
        email_n,
    )
    return CreatedOrganisation(
        tenant=tenant,
        admin=admin,
        created=True,
        admin_password=generated,
    )


def ensure_organisation(
    db: Session,
    *,
    name: str,
    slug: str,
    admin_email: str,
    admin_password: str | None = None,
    activate_plan: bool = False,
    actor_user_id: UUID | str | None = None,
    actor_email: str | None = None,
    settings: Settings | None = None,
) -> CreatedOrganisation:
    """Idempotent stand-up by slug (smoke / re-runs). Does not rotate passwords."""
    settings = settings or get_settings()
    slug_n = normalize_slug(slug)
    existing = db.scalar(select(Tenant).where(Tenant.slug == slug_n))
    if existing is not None:
        membership = db.scalar(
            select(Membership).where(Membership.tenant_id == existing.id).limit(1)
        )
        admin = db.get(User, membership.user_id) if membership else None
        if admin is None:
            raise OrganisationError(f"tenant {slug_n} exists but has no admin user")
        _ensure_default_agent_config(db, existing.id)
        billing = ensure_billing_customer(
            db,
            tenant_id=existing.id,
            email=admin.email,
            create_stripe=False,
            settings=settings,
        )
        if activate_plan and billing.plan_status != "active":
            apply_plan_state(
                db,
                billing,
                plan_status="active",
                plan_source="admin",
                override_reason="admin_provision",
                extra_meta={"source": "admin_provision"},
            )
        db.commit()
        return CreatedOrganisation(tenant=existing, admin=admin, created=False)

    return create_organisation(
        db,
        name=name,
        slug=slug_n,
        admin_email=admin_email,
        admin_password=admin_password,
        activate_plan=activate_plan,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        settings=settings,
    )
