"""Create / retrieve billing customers linked 1:1 to tenants."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.billing.errors import BillingError
from api.app.db.models import BillingCustomer, Tenant, User
from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings

logger = get_logger("api.billing.customers")

__all__ = ["BillingError", "ensure_billing_customer", "get_billing_customer"]


def get_billing_customer(db: Session, tenant_id: UUID | str) -> BillingCustomer | None:
    tid = UUID(str(tenant_id))
    return db.scalar(select(BillingCustomer).where(BillingCustomer.tenant_id == tid))


def _default_email_for_tenant(db: Session, tenant_id: UUID) -> str | None:
    """Prefer an org membership user's email; fall back to None."""
    from api.app.db.models import Membership

    membership = db.scalar(
        select(Membership).where(Membership.tenant_id == tenant_id).limit(1)
    )
    if membership is None:
        return None
    user = db.get(User, membership.user_id)
    return user.email if user else None


def ensure_billing_customer(
    db: Session,
    *,
    tenant_id: UUID | str,
    email: Optional[str] = None,
    settings: Settings | None = None,
    create_external: bool = True,
    create_stripe: bool | None = None,
) -> BillingCustomer:
    """
    Ensure a ``billing_customers`` row for the tenant; create/retrieve gateway customer
    when configured.

    Idempotent: reuses existing external customer id. When the payment adapter is not
    configured and ``create_external`` is True, still ensures the local row
    (``plan_status=inactive``) without an external id — Checkout/Portal fail closed
    until keys are set.

    ``create_stripe`` is a deprecated alias for ``create_external`` (Sprint 34).
    """
    if create_stripe is not None:
        create_external = create_stripe
    settings = settings or get_settings()
    tid = UUID(str(tenant_id))
    tenant = db.get(Tenant, tid)
    if tenant is None:
        raise BillingError(f"Tenant not found: {tid}")

    row = get_billing_customer(db, tid)
    if row is None:
        from api.app.billing.plans import INACTIVE_ENTITLEMENTS

        row = BillingCustomer(
            tenant_id=tid,
            plan_status="inactive",
            entitlements=dict(INACTIVE_ENTITLEMENTS),
            meta={},
        )
        db.add(row)
        db.flush()
        logger.info("billing_customer_row_created tenant_id=%s", tid)

    if row.external_customer_id:
        return row

    if not create_external:
        return row

    from api.app.billing.provider import get_payment_provider

    provider = get_payment_provider(settings)
    if not provider.is_configured():
        logger.warning(
            "payment_provider_not_configured provider=%s tenant_id=%s — "
            "billing row without external_customer_id",
            provider.name,
            tid,
        )
        return row

    customer_email = (email or _default_email_for_tenant(db, tid) or "").strip() or None
    try:
        external_id = provider.ensure_customer(
            tenant_id=tid,
            tenant_name=tenant.name,
            tenant_slug=tenant.slug,
            email=customer_email,
            existing_external_id=None,
        )
    except BillingError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise BillingError(f"Payment ensure_customer failed: {exc}") from exc

    row.provider = provider.name
    row.external_customer_id = external_id
    meta = dict(row.meta or {})
    meta["payment_email"] = customer_email
    row.meta = meta
    db.add(row)
    db.flush()
    logger.info(
        "payment_customer_created provider=%s tenant_id=%s external_customer_id=%s",
        provider.name,
        tid,
        external_id,
    )
    return row
