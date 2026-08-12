"""Public org self-signup (Sprint 31.1). Mirrors admin provision; no Strategy/Factory."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from api.app.admin.provision import (
    CreatedOrganisation,
    OrganisationError,
    allocate_unique_slug,
    create_organisation,
    normalize_slug,
    slug_from_name,
)
from api.app.auth.tokens import create_access_token
from api.app.settings import Settings, get_settings


@dataclass
class SignupResult:
    organisation: CreatedOrganisation
    access_token: str


def register_organisation(
    db: Session,
    *,
    name: str,
    email: str,
    password: str,
    slug: str | None = None,
    display_name: str | None = None,
    settings: Settings | None = None,
) -> SignupResult:
    """
    Self-serve tenant + org admin. Plan stays inactive (pay is Sprint 19–20).
    Does not honour DEMO_ACTIVATE_PLAN.
    """
    settings = settings or get_settings()
    password_n = (password or "").strip()
    if len(password_n) < 8:
        raise OrganisationError("password must be at least 8 characters")

    raw_slug = (slug or "").strip()
    if raw_slug:
        slug_n = normalize_slug(raw_slug)
    else:
        slug_n = allocate_unique_slug(db, slug_from_name(name))

    created = create_organisation(
        db,
        name=name,
        slug=slug_n,
        admin_email=email,
        admin_password=password_n,
        admin_display_name=display_name,
        activate_plan=False,
        actor_email=(email or "").strip().lower(),
        settings=settings,
        audit_source="self_signup",
    )
    token = create_access_token(
        settings=settings,
        sub=str(created.admin.id),
        email=created.admin.email,
        role="org_admin",
        tenant_id=str(created.tenant.id),
    )
    return SignupResult(organisation=created, access_token=token)
